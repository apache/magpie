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
- `attach_archive` links each finding to its `REPORT.md` and candidate
  patches in an operator-decrypted archive, and `render_patch_comments`
  quotes those patches, folded, in tracker comment bodies.
"""

from __future__ import annotations

import codecs
import email
import email.policy
import hashlib
import json
import os
import re
import stat
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
# The scan's target and commit come from the email; only a plain ref may sit in a code span.
_PLAIN_REF = re.compile(r"[\w./:@+-]+")


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


def _patch_number(path: Path) -> int:
    return int(path.stem) if path.stem.isdigit() else 1 << 30


def _archive_file(path: Path) -> bool:
    """A regular file reached without a symlink, under an archive root that is already resolved.

    The archive comes from the scanner, so a symlinked `REPORT.md`, `patches/` or
    `*.patch` could point at any local file, which would then be quoted in a tracker comment.
    """
    return path.is_file() and path.resolve() == path.absolute()


def _reproducers(finding_dir: Path, patches: list[Path]) -> list[str]:
    """Every other regular file in the finding's folder: the reproducer, its build files, its inputs.

    Listed for quoting only — never run, built or installed.
    """
    if not finding_dir.is_dir() or finding_dir.is_symlink():
        return []
    skip = {finding_dir / "REPORT.md", *patches}
    found = []
    for dirpath, dirnames, filenames in os.walk(finding_dir):
        dirnames[:] = sorted(d for d in dirnames if not (Path(dirpath) / d).is_symlink())
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path not in skip and _archive_file(path):
                found.append(str(path))
    return found


def attach_archive(parsed: dict[str, Any], archive_dir: Path) -> None:
    """Point each finding at its `REPORT.md`, candidate patches and reproducer files in the opened archive.

    Never runs anything: the files are only listed, for the triage to read and
    `render_patch_comments` to quote. Reports for ids the mail does not list as a
    finding or an ordinary bug — entries the scanner sent before, or related
    ones — go to `other_reports`, so their full text is triaged too.
    """
    archive_dir = archive_dir.resolve()
    linked: set[Path] = set()
    for f in parsed["findings"]:
        linked.add(_link(f, archive_dir / f["banner_severity"].lower() / f["id"]))
    for b in parsed["not_security"]:
        linked.add(_link(b, archive_dir / "bugs-not-security" / b["id"]))
    other = []
    for report in sorted(archive_dir.glob("*/*/REPORT.md")):
        fid, section = report.parent.name, report.parent.parent.name
        if report not in linked and re.fullmatch(_ID, fid) and _archive_file(report):
            entry = {"id": fid, "section": section}
            _link(entry, report.parent)
            other.append(entry)
    parsed["other_reports"] = other


def _link(entry: dict[str, Any], folder: Path) -> Path:
    """Set *entry*'s `report_md`, `patches` and `reproducers` from its archive folder; returns the report path.

    Every entry gets them — a finding, an ordinary bug or an unlisted report — since
    any of them can be promoted to a tracker and then gets the evidence comment.
    """
    report = folder / "REPORT.md"
    entry["report_md"] = str(report) if _archive_file(report) else None
    patches = [p for p in (folder / "patches").glob("*.patch") if _archive_file(p)]
    patches = sorted(patches, key=lambda p: (_patch_number(p), p.name))
    entry["patches"] = [str(p) for p in patches]
    entry["reproducers"] = _reproducers(folder, patches)
    entry["evidence_dir"] = str(folder)
    return report


def find_entry(index: Mapping[str, Any], entry_id: str) -> dict[str, Any] | None:
    """The finding, ordinary bug or unlisted archive report with *entry_id*, from a scan folder's index."""
    for key in ("findings", "not_security", "other_reports"):
        for entry in index.get(key) or []:
            if isinstance(entry, dict) and entry.get("id") == entry_id:
                return entry
    return None


# Read no more of one archive file than a comment could ever hold.
_READ_CAP = 1 << 20


def _read_archive_bytes(path: Path) -> tuple[bytes, int]:
    """Up to `_READ_CAP` bytes and the file's size, refusing a symlink or anything but a regular file."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"{path} is not a regular file")
        return handle.read(_READ_CAP), info.st_size


def _read_text(path: Path) -> str | None:
    """The file as text, or None for a binary one (NUL bytes, or not UTF-8)."""
    data, _ = _read_archive_bytes(path)
    if b"\x00" in data:
        return None
    try:
        # A file cut at the read cap may end inside a character; only a complete read is final.
        return codecs.getincrementaldecoder("utf-8")().decode(data, final=len(data) < _READ_CAP)
    except UnicodeDecodeError:
        return None


# GitHub refuses a comment over 65,536 characters; keep headroom for its own counting.
COMMENT_LIMIT = 65_000
# The skill-comment marker (tools/github/status-rollup.md), so sync's pre-flight
# reads the evidence comment as skill-authored rather than as human activity.
PATCH_COMMENT_MARKER = "<!-- apache-magpie: scan-evidence v1 -->"
# A block cut to less than this is listed as omitted instead.
_MIN_BLOCK = 400
_REPRO_HEADING = re.compile(r"reproduc|proof[ -]of[ -]concept|\bpoc\b|steps to", re.I)
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def _escape(text: str) -> str:
    """Safe inside `<summary>` and prose: no HTML, and no bare `@name` that would notify someone."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"(?<![\w`])(@[\w.-]+)", r"`\1`", text)


def _patch_summary(patch: str, n: int) -> str:
    """The patch's one-line header (its second `#` line), safe inside `<summary>`."""
    lines = patch.splitlines()
    text = lines[1].lstrip("#").strip() if len(lines) > 1 and lines[1].startswith("#") else ""
    return f"Candidate patch {n} — {_escape(text)}" if text else f"Candidate patch {n}"


def _shown_path(path: Path, base: Path) -> str:
    """The file's path inside the finding's folder, as plain characters in code span."""
    try:
        rel = path.relative_to(base).as_posix()
    except ValueError:
        rel = path.name
    return "`" + re.sub(r"[^\w./+-]", "_", rel)[:160] + "`"


def _headings(report: str) -> list[tuple[int, int, str]]:
    """`(offset, level, text)` of each Markdown heading, skipping lines inside fenced code blocks.

    A `# comment` in a shell, Python, YAML or Dockerfile snippet is not a heading.
    """
    heads: list[tuple[int, int, str]] = []
    fence: tuple[str, int] | None = None
    offset = 0
    for line in report.splitlines(keepends=True):
        opener = _FENCE.match(line)
        if fence is None and opener:
            fence = (opener.group(1)[0], len(opener.group(1)))
        elif fence is not None:
            closer = _FENCE.match(line)
            if (
                closer
                and closer.group(1)[0] == fence[0]
                and len(closer.group(1)) >= fence[1]
                and not closer.group(2).strip()
            ):
                fence = None
        else:
            m = _HEADING.match(line.rstrip("\n"))
            if m:
                heads.append((offset, len(m.group(1)), m.group(2)))
        offset += len(line)
    return heads


def _repro_section(report: str) -> tuple[str, str]:
    """`(title, text)`: the report's reproduction section, else the whole report."""
    heads = _headings(report)
    for i, (start, level, text) in enumerate(heads):
        if _REPRO_HEADING.search(text):
            end = next((h[0] for h in heads[i + 1 :] if h[1] <= level), len(report))
            return "Reproduction steps (from the scanner's REPORT.md)", report[start:end]
    return "The scanner's REPORT.md (it has no separate reproduction section)", report


class _Block:
    """One `<details>` block: a summary, the quoted text, and the fence's info string."""

    def __init__(self, summary: str, text: str | None, lang: str = "", note: str = "") -> None:
        self.summary, self.text, self.lang, self.note = summary, text, lang, note

    def fence(self) -> str:
        longest = max((len(run) for run in re.findall(r"`+", self.text or "")), default=0)
        return "`" * max(5, longest + 1)

    def render(self, text: str | None = None, cut_note: str = "") -> str:
        body = self.text if text is None else text
        if body is None:
            inner = [self.note]
        else:
            fence = self.fence()
            inner = [f"{fence}{self.lang}", body.rstrip("\n"), fence]
            if cut_note:
                inner += ["", cut_note]
        return "\n".join([f"<details><summary>{self.summary}</summary>", "", *inner, "", "</details>", ""])

    def fit(self, room: int) -> str:
        """The block in at most *room* characters: whole, cut at a line with a note, or listed as omitted."""
        whole = self.render()
        if len(whole) <= room or self.text is None:
            return whole
        total = len(self.text)
        note = (
            f"_Truncated for the comment limit: the first {{shown}} of {total} characters,"
            " so this is incomplete. The full file is in the local decrypted archive._"
        )
        keep = room - len(self.render("", note.format(shown=total)))
        if keep >= _MIN_BLOCK:
            cut = self.text[:keep]
            cut = cut.rsplit("\n", 1)[0] if "\n" in cut else cut
            block = self.render(cut, note.format(shown=len(cut)))
            if len(block) <= room:
                return block
        return self.omitted()

    def omitted(self) -> str:
        return f"- {self.summary}: omitted for the comment limit; read it in the local decrypted archive.\n"


def _blocks_for(finding: Mapping[str, Any]) -> list[_Block]:
    blocks: list[_Block] = []
    report = finding.get("report_md")
    if report:
        text = _read_text(Path(report))
        if text is not None:
            title, section = _repro_section(text)
            blocks.append(_Block(title, section, "markdown"))
    patches = [Path(p) for p in finding.get("patches") or []]
    repros = [Path(p) for p in finding.get("reproducers") or []]
    parents = [str(p.parent) for p in [*patches, *repros]]
    if finding.get("evidence_dir"):
        base = Path(finding["evidence_dir"])
    elif report:
        base = Path(report).parent
    else:
        base = Path(os.path.commonpath(parents)) if parents else Path("/")
    for path in repros:
        size = _read_archive_bytes(path)[1]
        text = _read_text(path)
        summary = f"Reproducer file {_shown_path(path, base)} — untested, do not run"
        note = f"Binary file, {size} bytes: not quoted. It is in the local decrypted archive."
        blocks.append(_Block(summary, text, "", note))
    for n, path in enumerate(patches, 1):
        text = _read_text(path)
        if text is None:
            size = _read_archive_bytes(path)[1]
            summary = f"Candidate patch {n} {_shown_path(path, base)} — untested, do not apply as-is"
            note = (
                f"Binary or non-UTF-8 patch, {size} bytes: not quoted. It is in the local decrypted archive."
            )
            blocks.append(_Block(summary, None, "", note))
            continue
        blocks.append(_Block(f"{_patch_summary(text, n)} — untested, do not apply as-is", text, "diff"))
    return blocks


def _allot(sizes: list[int], room: int) -> list[int]:
    """Share *room* among blocks: small ones whole, the rest an equal share of what is left."""
    shares = [0] * len(sizes)
    left, pending = room, sorted(range(len(sizes)), key=lambda i: sizes[i])
    while pending:
        share = left // len(pending)
        i = pending[0]
        if sizes[i] > share:
            for j in pending:
                shares[j] = share
            break
        shares[i] = sizes[i]
        left -= sizes[i]
        pending.pop(0)
    return shares


def render_patch_comments(
    finding: Mapping[str, Any],
    scan: Mapping[str, Any],
    limit: int = COMMENT_LIMIT,
    verdict: str | None = None,
) -> list[str]:
    """The ONE private-tracker comment quoting a finding's reproduction steps, reproducers and patches.

    Each item is folded in its own `<details>` block, marked untested, and the
    operator-confirmed triage verdict is stated first. Returns `[]` when the
    archive has nothing for the finding. The body stays within *limit*: when the
    items do not fit, the larger ones are cut at a line with a note saying so,
    and one too large to show usefully is listed as omitted.
    """
    blocks = _blocks_for(finding)
    if not blocks:
        return []
    fid = finding["id"]
    refs = (str(v) for v in (scan.get("target"), scan.get("commit")) if v)
    where = " at ".join(f"`{v}`" for v in refs if _PLAIN_REF.fullmatch(v))
    head = [
        PATCH_COMMENT_MARKER,
        f"**Scanner evidence — `{fid}`**",
        "",
        "> [!WARNING]",
        f"> Machine-generated material from the scan{f' of {where}' if where else ''}, quoted from its encrypted archive."
        " None of it has been tested or reviewed by the team.",
        "> Do not run the reproducers or apply the patches outside an isolated, throwaway environment;"
        " they are here to read, as a starting point for `security-issue-fix`.",
        "> They spell out the security impact: keep them on this private tracker and never copy them into a public PR.",
        "",
    ]
    if verdict:
        head += [f"**Triage verdict:** {_escape(' '.join(verdict.split()))[:1500]}", ""]
    header = "\n".join(head) + "\n"
    whole = [b.render() for b in blocks]
    if len(header) + sum(len(w) + 1 for w in whole) <= limit:
        return [header + "\n".join(whole)]
    footer = "\n_Some items were cut or omitted to stay under GitHub's comment limit._\n"
    room = limit - len(header) - len(footer) - len(blocks)
    shares = _allot([len(w) for w in whole], room)
    fitted = [b.fit(s) for b, s in zip(blocks, shares, strict=True)]
    dropped = 0
    while True:
        tail = f"- {dropped} more item(s) omitted for the comment limit.\n" if dropped else ""
        body = header + "\n".join(fitted) + tail + footer
        if len(body) <= limit or not fitted:
            break
        fitted.pop()
        dropped += 1
    if len(body) > limit:
        raise ValueError(f"{fid}: the comment header alone is over the limit")
    return [body]


def write_patch_comments(
    finding: Mapping[str, Any], scan: Mapping[str, Any], out_dir: Path, verdict: str | None = None
) -> list[dict[str, Any]]:
    """Write `render_patch_comments`' body as `<id>.md`, owner-only."""
    bodies = render_patch_comments(finding, scan, verdict=verdict)
    _private_dir(out_dir)
    written = []
    for body in bodies:
        path = out_dir / f"{finding['id']}.md"
        _private_write(path, body.encode("utf-8"))
        written.append({"path": str(path), "chars": len(body)})
    return written


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
    if "other_reports" in parsed:
        index["other_reports"] = parsed["other_reports"]
    _private_write(out_dir / INDEX_FILE, (json.dumps(index, indent=2) + "\n").encode("utf-8"))
    by_severity = Counter(f["severity"] for f in parsed["findings"])
    summary: dict[str, Any] = {
        "format": FORMAT,
        "scan_folder": str(out_dir),
        "index": str(out_dir / INDEX_FILE),
        "scan": parsed["scan"],
        "findings": len(parsed["findings"]),
        "by_severity": {s.capitalize(): by_severity[s.capitalize()] for s in SEVERITIES},
        "not_security": len(parsed["not_security"]),
        "checks": parsed["checks"],
    }
    if "other_reports" in parsed:
        entries = [*parsed["findings"], *parsed["not_security"]]
        summary["archive"] = {
            "reports": sum(1 for e in entries if e.get("report_md")),
            "missing_reports": sum(1 for e in entries if not e.get("report_md")),
            "patches": sum(len(e.get("patches") or []) for e in entries),
            "reproducer_files": sum(len(e.get("reproducers") or []) for e in entries),
            "other_reports": len(parsed["other_reports"]),
        }
    return summary


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
