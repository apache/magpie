# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""The `anthropic-oss-scanner` scan-format adapter: one disclosure email, many findings.

The Anthropic OSS Scanner discloses a whole scan in a single plain-text
email (`[Anthropic OSS Scanner] Disclosing N security vulnerabilities in
<project>`): a preamble naming the target and commit, an INDEX, one
`====`-fenced block per finding grouped under `####` severity banners, and
a trailing `NOT SECURITY: N ORDINARY BUGS` list. An encrypted archive with
reproducers and candidate patches is attached; this module never decrypts
it and never runs anything from it.

- `load_body` takes the email as an `.eml` file, as the plain-text body, or
  as the JSON a Gmail connector saved (`plaintextBody`), and returns the
  text with RFC 3676 `format=flowed` undone. Gmail's text rendering re-wraps
  long lines, so every parse below is whitespace-tolerant.
- `parse` returns the scan metadata, every finding normalised to the
  `tools/scan-format/` schema with its verbatim block as evidence, the
  not-security list, and completeness `checks`: the declared total, the
  INDEX and the finding blocks must all agree, or the email was truncated.
- `materialise` writes a scan folder (`index.json` + `evidence/<id>.md`)
  that the skill reads one finding at a time.
- `save_attachments` writes the attachments out of an `.eml` byte-exact
  (sanitised names, sha256) and, for an encrypted archive, checks the
  OpenPGP packet framing so a truncated download shows — without
  decrypting it.
"""

from __future__ import annotations

import email
import email.policy
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

FORMAT = "anthropic-oss-scanner"
INDEX_FILE = "index.json"
SEVERITIES = ("critical", "high", "medium", "low")

_ID = r"ANT-\d{4}-[A-Z0-9]{6,}"
_BANNER = re.compile(r"^#{20,}\n(.+?)\n#{20,}$", re.M)
# A finding header is a fence, an `<id> [<severity>]` block holding no fence, and a
# fence. A fence-like line inside a write-up is not followed by such a header.
_HEADER_BLOCK = re.compile(rf"^={{20,}}\n({_ID}\s+\[(?:(?!^={{20,}}$).)*?)\n={{20,}}$", re.M | re.S)
_HEADER = re.compile(
    rf"^({_ID})\s+\[(\w+)\]\s+((?:CWE-\d+[,\s]+)*)(\S+)\s+(.+)$",
    re.S,
)
# A not-security entry ends in `(<path>:<line>)`; a path may hold any character but parentheses.
# A not-security entry is `<id> <title> (<path>:<line>)`; the path may itself hold
# parentheses (`app/(auth)/route.ts`), so the location is the trailing group.
_ENTRY_START = re.compile(rf"^\s*({_ID})\s+", re.M)
_ENTRY_LOCATION = re.compile(r"\s*\(((?:[^()]|\([^()]*\))+?:\d+)\)\s*\Z")
_PATCH = re.compile(rf"\b(\w+/{_ID}/patches/\d+\.patch)\b")


def _unflow(text: str, delsp: bool = False) -> str:
    """Undo RFC 3676 format=flowed: a line ending in a space continues on the next.

    Quote depth is the run of leading `>`; a flowed line joins the next only at
    the same depth, and the prefix is kept once. With `delsp=yes` the trailing
    space is the soft break itself and is deleted, so a token wrapped mid-word
    joins back without a gap.
    """
    out: list[tuple[int, str]] = []
    flowed = False
    for raw in text.split("\n"):
        depth = len(raw) - len(raw.lstrip(">"))
        line = raw[depth:]
        if line.startswith(" "):
            line = line[1:]  # space-stuffing
        if flowed and out and out[-1][0] == depth:
            prev = out[-1][1]
            out[-1] = (depth, (prev[:-1] if delsp else prev) + line)
        else:
            if flowed and delsp and out:
                # A soft break with nothing at its depth to join is just removed.
                out[-1] = (out[-1][0], out[-1][1][:-1])
            out.append((depth, line))
        flowed = line.endswith(" ") and line != "-- "
    return "\n".join(">" * d + (" " if d and s else "") + s for d, s in out)


def load_body(path: Path) -> tuple[str, dict[str, Any]]:
    """The email's plain-text body and what is known about its envelope."""
    raw = path.read_bytes()
    meta: dict[str, Any] = {"source": str(path)}
    stripped = raw.lstrip()
    if stripped.startswith(b"{"):
        data = json.loads(raw)
        body = str(data.get("plaintextBody") or "")
        meta |= {
            "subject": data.get("subject"),
            "date": data.get("date"),
            "attachments": [a.get("filename") for a in data.get("attachments") or []],
            # The connector's text rendering drops control characters (a NUL
            # or lone-surrogate payload reads as ""), which can invert a
            # finding's meaning. Re-read the payloads from the .eml.
            "lossy": True,
        }
        return body.replace("\r\n", "\n"), meta
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    if msg.get("Subject") is None and msg.get("From") is None:
        # A bare body of unknown provenance — often a client's rendering, which
        # may have dropped control characters like the connector JSON does.
        meta["lossy"] = True
        return raw.decode("utf-8", errors="replace").replace("\r\n", "\n"), meta
    part = msg.get_body(preferencelist=("plain",))
    if part is None:
        raise ValueError(f"{path}: no text/plain part — not an OSS Scanner disclosure")
    body = part.get_content().replace("\r\n", "\n")
    if str(part.get_param("format", "")).lower() == "flowed":
        body = _unflow(body, delsp=str(part.get_param("delsp", "")).lower() == "yes")
    meta |= {
        "subject": str(msg.get("Subject", "")),
        "date": str(msg.get("Date", "")),
        "message_id": str(msg.get("Message-ID", "")),
        "attachments": [p.get_filename() for p in msg.iter_attachments() if p.get_filename()],
    }
    return body, meta


def _private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)


def _private_write(path: Path, data: bytes, *, exclusive: bool = False) -> None:
    """Owner-only from creation: scan evidence is embargoed until disclosure.

    `exclusive` refuses an existing file. Otherwise the bytes go to a fresh
    0600 temporary file that atomically replaces the target, so an existing,
    more permissive file never holds the new contents, even for a moment.
    """
    if exclusive:
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as handle:
            handle.write(data)
        return
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _flat(text: str) -> str:
    return " ".join(text.split())


def _sections(body: str) -> list[tuple[str, str]]:
    """`(banner, text)` for every `####` severity banner, in order."""
    # Only a severity / count banner bounds a section; a `####`-framed heading
    # inside a write-up's code excerpt is evidence, not a boundary.
    marks = [b for b in _BANNER.finditer(body) if _declared(_flat(b.group(1))) is not None]
    return [
        (_flat(m.group(1)), body[m.end() : marks[i + 1].start() if i + 1 < len(marks) else len(body)])
        for i, m in enumerate(marks)
    ]


def _declared(banner: str) -> tuple[str, int] | None:
    m = re.match(r"(CRITICAL|HIGH|MEDIUM|LOW|NOT SECURITY):\s+(\d+)\b", banner)
    return (m.group(1).lower(), int(m.group(2))) if m else None


def _finding(header: str, text: str, banner_severity: str) -> dict[str, Any]:
    # The fields start lines; a title may itself say "Location:" mid-line.
    # The fields are the last `Location:` and `Commit:` lines; a title may itself
    # start with "Location:", and it always comes first.
    fields = re.match(r"(?s)(.*)^Location:(.*?)(?:^Commit:(.*))?\Z", header, re.M)
    head, location, commit = (
        (fields.group(1), fields.group(2), fields.group(3) or "") if fields else (header, "", "")
    )
    m = _HEADER.match(_flat(head))
    if not m:
        raise ValueError(f"unparsable finding header: {_flat(head)[:120]!r}")
    fid, severity, cwes, category, title = m.groups()
    loc = _flat(location)
    path_line, _, function = loc.partition(" in ")
    evidence = text.strip("\n")
    return {
        "id": fid,
        "title": title.strip(),
        "severity": severity.capitalize(),
        "banner_severity": banner_severity.capitalize(),
        "level": None,
        "cwe": re.findall(r"CWE-\d+", cwes),
        "category": category,
        "files": [path_line] if path_line else [],
        "function": function or None,
        "commit": _flat(commit) or None,
        # The scanner states who the attacker is in prose, in the opening
        # paragraph of the evidence; the model reads it there.
        "attacker_capability": None,
        "summary": _flat(evidence.split("\n\n", 1)[0]),
        "impact": None,
        "remediation": sorted(set(_PATCH.findall(evidence))),
        "evidence": f"{_flat(head)}\nLocation: {loc}\nCommit: {_flat(commit)}\n\n{evidence}\n",
    }


def _blocks(text: str, severity: str) -> list[dict[str, Any]]:
    """Each finding: its header block, and everything up to the next header verbatim."""
    headers = list(_HEADER_BLOCK.finditer(text))
    return [
        _finding(
            m.group(1),
            text[m.end() : headers[i + 1].start() if i + 1 < len(headers) else len(text)],
            severity,
        )
        for i, m in enumerate(headers)
    ]


def _index(body: str) -> dict[str, list[str]]:
    """The INDEX section's ids per severity, for the completeness check."""
    m = re.search(r"^INDEX\s*$(.*?)^(?:IF YOU FIX|HOW TO REPRODUCE|#{20,})", body, re.S | re.M)
    if not m:
        return {}
    out: dict[str, list[str]] = {}
    current = ""
    for line in m.group(1).split("\n"):
        sev = re.match(r"\s*(CRITICAL|HIGH|MEDIUM|LOW)\s+\(\d+\)\s*$", line)
        if sev:
            current = sev.group(1).lower()
            out[current] = []
        elif current:
            out[current] += re.findall(rf"^\s*({_ID})\b", line)
    return out


def _not_security(text: str) -> list[dict[str, Any]]:
    # The signature delimiter is `--` or the RFC 3676 `-- ` (trailing space).
    text = re.split(r"\n-- ?\n", text, maxsplit=1)[0]
    starts = list(_ENTRY_START.finditer(text))
    entries = []
    for i, m in enumerate(starts):
        chunk = text[m.end() : starts[i + 1].start() if i + 1 < len(starts) else len(text)].strip()
        loc = _ENTRY_LOCATION.search(chunk)
        if loc:
            title = chunk[: loc.start()]
            entries.append(
                {
                    "id": m.group(1),
                    "title": _flat(title),
                    "files": [_flat(loc.group(1))],
                    "not_security": True,
                }
            )
    return entries


def parse(body: str) -> dict[str, Any]:
    flat = _flat(body)
    target = re.search(r"security scan of (\S+) at commit ([0-9a-f]{7,40})", flat)
    total = re.search(r"This scan produced (\d+) findings", flat)
    ordinary = re.search(r"came across (\d+) ordinary bugs", flat)
    archive = re.search(r"\(([\w.-]+\.tar\.gz\.gpg)\)", flat)
    findings: list[dict[str, Any]] = []
    not_security: list[dict[str, Any]] = []
    declared: dict[str, int] = {}
    for banner, text in _sections(body):
        d = _declared(banner)
        if d is None:
            continue
        declared[d[0]] = d[1]
        if d[0] == "not security":
            not_security = _not_security(text)
        else:
            findings += _blocks(text, d[0])
    index = _index(body)
    problems: list[str] = []
    got = Counter(f["banner_severity"].lower() for f in findings)
    for sev, n in declared.items():
        have = len(not_security) if sev == "not security" else got[sev]
        if have != n:
            problems.append(f"{sev}: banner declares {n}, parsed {have}")
    if not total:
        problems.append("no preamble total — the start of the mail is missing")
    if not index:
        problems.append("no INDEX — the start of the mail is missing")
    if total and int(total.group(1)) != len(findings):
        problems.append(f"preamble declares {total.group(1)} findings, parsed {len(findings)}")
    indexed = {i for ids in index.values() for i in ids}
    blocks = {f["id"] for f in findings}
    if index and indexed != blocks:
        problems.append(
            f"INDEX and finding blocks differ: only in INDEX {sorted(indexed - blocks)}, "
            f"only in blocks {sorted(blocks - indexed)}"
        )
    if len(blocks) != len(findings):
        problems.append("duplicate finding ids")
    for f in findings:
        if f["severity"] != f["banner_severity"]:
            problems.append(f"{f['id']}: [{f['severity'].lower()}] under the {f['banner_severity']} banner")
    if ordinary and int(ordinary.group(1)) != len(not_security):
        problems.append(f"preamble declares {ordinary.group(1)} ordinary bugs, parsed {len(not_security)}")
    for f in findings:
        if not f["evidence"].split("\n\n", 1)[1].strip():
            problems.append(f"{f['id']}: no write-up after its header")
    # The mail ends with the scanner's signature block; without it the tail is gone.
    if not re.search(r"^--\s*\n\s*oss-scanner\b", body, re.M):
        problems.append("no closing signature — the mail is cut off after the last parsed section")
    if not findings:
        problems.append("no finding blocks found — not an Anthropic OSS Scanner disclosure, or truncated")
    return {
        "format": FORMAT,
        "scan": {
            "target": target.group(1) if target else None,
            "commit": target.group(2) if target else None,
            "declared_total": int(total.group(1)) if total else None,
            "declared": declared,
            "archive": archive.group(1) if archive else None,
        },
        "findings": findings,
        "not_security": not_security,
        "checks": {"complete": not problems, "problems": problems},
    }


# Symmetrically encrypted data: SED (9), SEIPD (18), AEAD (20).
_OPENPGP_DATA = frozenset({9, 18, 20})


def openpgp_framing(data: bytes) -> dict[str, Any]:
    """Walk the OpenPGP packet headers of an encrypted file without decrypting it.

    A whole file is a run of packets that tiles it exactly and ends in an
    encrypted-data packet; a short download leaves the last declared length
    running past the end, or stops before the data. This detects truncation,
    not tampering: the integrity check proper is gpg's MDC, at decryption.
    """
    i, tags = 0, list[int]()
    try:
        while i < len(data):
            head = data[i]
            if not head & 0x80:
                return {"intact": False, "packets": tags, "problem": f"no packet header at byte {i}"}
            if head & 0x40:  # new format: one length, or a chain of partial lengths
                tag, i = head & 0x3F, i + 1
                while True:
                    o = data[i]
                    if o < 192:
                        n, i, partial = o, i + 1, False
                    elif o < 224:
                        n, i, partial = ((o - 192) << 8) + data[i + 1] + 192, i + 2, False
                    elif o == 255:
                        n, i, partial = int.from_bytes(data[i + 1 : i + 5], "big"), i + 5, False
                    else:
                        n, i, partial = 1 << (o & 0x1F), i + 1, True
                    i += n
                    if not partial:
                        break
            else:  # old format
                tag, width = (head >> 2) & 0xF, (1, 2, 4)[head & 3] if head & 3 != 3 else 0
                if not width:
                    return {"intact": False, "packets": tags, "problem": "indeterminate-length packet"}
                i += 1 + width + int.from_bytes(data[i + 1 : i + 1 + width], "big")
            tags.append(tag)
    except IndexError:
        return {"intact": False, "packets": tags, "problem": "truncated packet header"}
    if not tags:
        return {"intact": False, "packets": tags, "problem": "empty file"}
    if tags[-1] not in _OPENPGP_DATA:
        return {"intact": False, "packets": tags, "problem": "no encrypted-data packet at the end"}
    if i != len(data):
        return {"intact": False, "packets": tags, "problem": f"declared {i} bytes, file has {len(data)}"}
    return {"intact": True, "packets": tags, "problem": None}


def _safe_name(name: str, taken: set[str]) -> str:
    """The sender chose the filename: keep its last path component only, and never collide."""
    base = re.sub(r"[^\w.+-]", "_", Path(name.replace("\\", "/")).name).lstrip(".") or "attachment"
    candidate, n = base, 1
    while candidate in taken:
        n += 1
        candidate = f"{n}-{base}"
    taken.add(candidate)
    return candidate


def save_attachments(path: Path, out_dir: Path) -> list[dict[str, Any]]:
    """Write every attachment of the `.eml` at *path* to *out_dir*; never opens or decrypts one."""
    raw = path.read_bytes()
    if raw.lstrip().startswith(b"{"):
        raise ValueError(
            f"{path}: a saved Gmail connector result carries no attachment bytes — "
            "fetch the message as .eml (oauth-draft-fetch-message) to get them"
        )
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    _private_dir(out_dir)
    saved: list[dict[str, Any]] = []
    # Never overwrite: an earlier run's files are taken names too.
    taken: set[str] = {entry.name for entry in out_dir.iterdir()}
    for part in msg.iter_attachments():
        payload = part.get_payload(decode=True)
        data = payload if isinstance(payload, bytes) else b""
        name = _safe_name(part.get_filename() or "attachment", taken)
        target = out_dir / name
        _private_write(target, data, exclusive=True)
        entry: dict[str, Any] = {
            "filename": part.get_filename(),
            "path": str(target),
            "content_type": part.get_content_type(),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if name.endswith((".gpg", ".pgp")):
            entry["openpgp"] = openpgp_framing(data)
        saved.append(entry)
    return saved


def attach_archive(parsed: Mapping[str, Any], archive_dir: Path) -> None:
    """Point each finding at its `REPORT.md` in an operator-decrypted archive (never runs `repro`)."""
    for f in parsed["findings"]:
        report = archive_dir / f["banner_severity"].lower() / f["id"] / "REPORT.md"
        f["report_md"] = str(report) if report.is_file() else None
    for b in parsed["not_security"]:
        report = archive_dir / "bugs-not-security" / b["id"] / "REPORT.md"
        b["report_md"] = str(report) if report.is_file() else None


def materialise(parsed: Mapping[str, Any], meta: Mapping[str, Any], out_dir: Path) -> dict[str, Any]:
    """Write `index.json` + `evidence/<id>.md`; return the summary to print (no evidence text)."""
    evidence_dir = out_dir / "evidence"
    _private_dir(out_dir)
    _private_dir(evidence_dir)
    index_findings = []
    for f in parsed["findings"]:
        path = evidence_dir / f"{f['id']}.md"
        _private_write(path, f["evidence"].encode("utf-8"))
        index_findings.append({k: v for k, v in f.items() if k != "evidence"} | {"evidence_file": str(path)})
    index = {
        "format": FORMAT,
        "email": dict(meta),
        "scan": parsed["scan"],
        "findings": index_findings,
        "not_security": parsed["not_security"],
        "checks": parsed["checks"],
    }
    _private_write(out_dir / INDEX_FILE, (json.dumps(index, indent=2) + "\n").encode("utf-8"))
    by_severity = Counter(f["severity"] for f in parsed["findings"])
    return {
        "format": FORMAT,
        "scan_folder": str(out_dir),
        "index": str(out_dir / INDEX_FILE),
        "scan": parsed["scan"],
        "findings": len(parsed["findings"]),
        "by_severity": {s.capitalize(): by_severity[s.capitalize()] for s in SEVERITIES},
        "not_security": len(parsed["not_security"]),
        "checks": parsed["checks"],
    }


def detect(folder: Path) -> str | None:
    """`anthropic-oss-scanner` if *folder* is a scan folder `materialise` wrote."""
    index = folder / INDEX_FILE
    if not index.is_file():
        return None
    try:
        data = json.loads(index.read_text(encoding="utf-8"))
        return FORMAT if isinstance(data, dict) and data.get("format") == FORMAT else None
    except (OSError, ValueError):
        return None
