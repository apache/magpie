#!/usr/bin/env python3
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
"""Deterministic checks of a staged release candidate, as JSON.

One subcommand per mechanical step of the `release-verify-rc` skill.
Every subcommand prints a single JSON object on stdout; the skill reads
it and reports. The rules are the skill's, implemented once:

- ``inventory``  — Step 1: staging listing vs the expected artefact
  patterns → FOUND / MISSING / UNEXPECTED; a missing *optional*
  artefact is a WARN, a missing required one a FAIL.
- ``signatures`` — Step 2: ``gpg --verify`` in a throwaway GNUPGHOME
  holding only the project's *public* KEYS → PASS / KEY-NOT-IN-KEYS / FAIL.
- ``checksums``  — Step 3: digest compare → PASS / MISMATCH /
  MISSING-DIGEST. Only sha512 is required; other digests are checked
  when present; md5 never fails alone (present or mismatched → WARN).
- ``notice-license`` — Step 5: NOTICE / LICENSE presence and diff line
  counts. Whether a non-empty diff is *material* is left to the reader
  (status ``REVIEW``).
- ``binaries``   — Step 6: fixed baseline + configured globs;
  ``.pyc`` / ``__pycache__`` are always PROHIBITED.
- ``symlinks``   — Step 7: symlinks in the unpacked tree that dangle or
  resolve outside it. The
  project's own validators are echoed in the recipe, never run.
- ``version``    — Step 8: version string per manifest, exact match.
- ``verdict``    — Step 10: FAIL > WARN > PASS roll-up of step results.
- ``all``        — the above in one report.

Read-only throughout: no file outside a temporary GNUPGHOME is written,
the user's keyring is never touched, nothing is signed, and nothing
touches the network: every input is a local file. Stdlib only.
"""

from __future__ import annotations

import argparse
import configparser
import contextlib
import difflib
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

STATUSES = ("PASS", "WARN", "FAIL", "SKIP")
BASELINE_FILE_GLOBS = ("*.class", "*.jar", "*.so", "*.dylib", "*.dll", "*.exe", "*.pyc")
DIGEST_TYPES = ("sha512", "sha256", "md5")
REQUIRED_DIGEST = "sha512"
HEX_LEN = {"sha512": 128, "sha256": 64, "md5": 32}
PRIVATE_KEY_MARKER = "PRIVATE KEY BLOCK"
STEP_ORDER = (
    "inventory",
    "signatures",
    "checksums",
    "rat-license-headers",
    "notice-license",
    "binary-exclusion",
    "jvm-artefacts",  # Step 6b, produced by maven-artifact-verify
    "nexus-staging",  # Step 6c, classified by the agent from the asf-nexus probe
    "source-tree-integrity",
    "version-consistency",
    "reproducibility",
)


class InputError(Exception):
    """Bad input: reported as ``{"error": ...}`` with exit code 2."""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _match_artefact(name: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def _found_artefacts(names: Sequence[str], patterns: Sequence[str]) -> list[str]:
    """Matching names, in the order of the patterns that match them (the config's order)."""
    found: list[str] = []
    for pattern in patterns:
        found += [n for n in sorted(names) if fnmatch.fnmatchcase(n, pattern) and n not in found]
    return found


def _patterns(args: argparse.Namespace) -> list[str]:
    """Required then optional artefact patterns: every staged artefact is signed and checksummed."""
    return [*args.expect, *(getattr(args, "expect_optional", None) or [])]


def _dir_names(directory: Path) -> list[str]:
    if not directory.is_dir():
        raise InputError(f"not a directory: {directory}")
    return sorted(p.name for p in directory.iterdir() if p.is_file())


def _rel(path: Path, top: Path) -> str:
    return path.relative_to(top).as_posix()


def _translate_glob(pattern: str) -> str:
    """`**/` and `**` collapse to `*`; `fnmatch` and `find -path` let `*` cross `/`."""
    pattern = pattern.strip().lstrip("/")
    if pattern.startswith("./"):
        pattern = pattern[2:]
    return pattern.replace("**/", "").replace("**", "*")


def _glob_hits(rel: str, pattern: str) -> bool:
    """`find -name` semantics for a bare glob, `find -path` for one with a `/`."""
    if "/" not in pattern.strip().lstrip("/"):
        return fnmatch.fnmatchcase(rel.rsplit("/", 1)[-1], pattern.strip())
    return fnmatch.fnmatchcase(rel, _translate_glob(pattern))


def _shq(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


# ---------------------------------------------------------------------------
# Step 1 — inventory
# ---------------------------------------------------------------------------


def inventory(names: Sequence[str], patterns: Sequence[str], digests: Sequence[str], source: str, optional: Sequence[str] = ()) -> dict[str, Any]:
    """Classify a staging listing against the expected artefact patterns.

    ``patterns`` are required artefacts (missing → FAIL); ``optional`` ones
    are the entries ``release-build.md`` marks optional (missing → WARN).
    """
    every = [*patterns, *optional]
    companions = (".asc", *(f".{d}" for d in dict.fromkeys(["sha512", *digests])))
    found = _found_artefacts(names, every)
    missing = [p for p in patterns if not any(fnmatch.fnmatchcase(n, p) for n in names)]
    missing_optional = [p for p in optional if not any(fnmatch.fnmatchcase(n, p) for n in names)]
    unexpected = []
    for name in sorted(names):
        if name in found:
            continue
        base = next((name[: -len(s)] for s in companions if name.endswith(s)), None)
        if base is not None and _match_artefact(base, every):
            continue
        unexpected.append(name)
    status = "FAIL" if missing else "WARN" if unexpected or missing_optional else "PASS"
    return {
        "step": "inventory",
        "status": status,
        "found": found,
        "missing": missing,
        "missing_optional": missing_optional,
        "unexpected": unexpected,
        "source": source,
    }


def cmd_inventory(args: argparse.Namespace) -> dict[str, Any]:
    if args.dir:
        return inventory(_dir_names(Path(args.dir)), args.expect, args.digest, str(args.dir), args.expect_optional or [])
    lines = Path(args.listing).read_text().splitlines()
    names = [ln.strip().rsplit("/", 1)[-1] for ln in lines if ln.strip() and not ln.strip().endswith("/")]
    return inventory(names, args.expect, args.digest, str(args.listing), args.expect_optional or [])


# ---------------------------------------------------------------------------
# Step 2 — signatures
# ---------------------------------------------------------------------------


def _read_public_keys(source: str) -> bytes:
    data = Path(source).read_bytes()
    if PRIVATE_KEY_MARKER in data.decode("utf-8", "replace"):
        raise InputError(f"{source} contains private key material; refusing to continue (golden rule 5)")
    return data


@contextlib.contextmanager
def _gnupghome() -> Iterator[Path]:
    """A throwaway GNUPGHOME: public keys only, no agent, no keyboxd, no network."""
    home = Path(tempfile.mkdtemp(prefix="rv-gpg-"))
    try:
        home.chmod(0o700)
        (home / "common.conf").write_text("")  # stops gpg >= 2.4.1 from enabling keyboxd
        (home / "gpg.conf").write_text("no-auto-key-retrieve\nno-auto-key-import\n")
        yield home
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _gpg(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    gpg = shutil.which("gpg")
    if gpg is None:
        raise InputError("gpg not found on PATH")
    proc = subprocess.run(
        [gpg, "--batch", "--no-tty", "--no-autostart", "--homedir", str(home), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GNUPGHOME": str(home), "LC_ALL": "C"},
    )
    # gpg names its home directory in some messages; the report may be posted
    # to the planning issue, so local paths never reach it.
    proc.stderr = proc.stderr.replace(str(home), "<gnupghome>")
    return proc


def _import(home: Path, data: bytes, label: str) -> None:
    src = home / "import.asc"
    src.write_bytes(data)
    proc = _gpg(home, "--import", str(src))
    src.unlink()
    if "imported:" not in proc.stderr and "unchanged:" not in proc.stderr:
        raise InputError(f"could not import keys from {label}: {proc.stderr.strip()}")


def _fingerprints(home: Path) -> set[str]:
    proc = _gpg(home, "--with-colons", "--fingerprint", "--fingerprint", "--list-keys")
    return {line.split(":")[9].upper() for line in proc.stdout.splitlines() if line.startswith("fpr:")}


STALE_SIGNATURE_STATUS = {
    "REVKEYSIG": "signature made by a revoked key",
    "EXPKEYSIG": "signature made by an expired key",
    "EXPSIG": "the signature itself has expired",
}


def verify_one(home: Path, artefact: Path, keys_fprs: set[str]) -> dict[str, Any]:
    sig = artefact.with_name(artefact.name + ".asc")
    result: dict[str, Any] = {
        "file": artefact.name,
        "sig_file": sig.name,
        "classification": "FAIL",
        "fingerprint": None,
        "key_in_keys": False,
    }
    if not sig.is_file():
        result["detail"] = "signature file missing"
        return result
    proc = _gpg(home, "--status-fd", "1", "--verify", str(sig), str(artefact))
    status = [ln[len("[GNUPG:] ") :].split() for ln in proc.stdout.splitlines() if ln.startswith("[GNUPG:] ")]
    validsig = next((s for s in status if s[0] == "VALIDSIG"), None)
    # gpg still exits 0 with VALIDSIG for these; the release must not pass on them.
    stale = next((s[0] for s in status if s[0] in STALE_SIGNATURE_STATUS), None)
    if stale is not None:
        result["fingerprint"] = validsig[-1].upper() if validsig else None
        result["detail"] = STALE_SIGNATURE_STATUS[stale]
        return result
    if proc.returncode == 0 and validsig is not None:
        signing, primary = validsig[1].upper(), validsig[-1].upper()
        in_keys = signing in keys_fprs or primary in keys_fprs
        result.update(fingerprint=primary, key_in_keys=in_keys, classification="PASS" if in_keys else "KEY-NOT-IN-KEYS")
        if not in_keys:
            result["detail"] = "good signature, but the signing key is not in KEYS"
        return result
    tokens = {s[0]: s for s in status}
    if "BADSIG" in tokens:
        result["detail"] = "BAD signature"
    elif "NO_PUBKEY" in tokens:
        result["detail"] = f"no public key for {tokens['NO_PUBKEY'][1]}: the signing key is not in KEYS"
    else:
        lines = [ln for ln in proc.stderr.strip().splitlines() if ln.strip()]
        result["detail"] = lines[-1] if lines else f"gpg exited {proc.returncode}"
    return result


def signatures(directory: Path, patterns: Sequence[str], keys: str, keys_url: str | None, extra_keys: Sequence[str]) -> dict[str, Any]:
    artefacts = _found_artefacts(_dir_names(directory), patterns)
    keys_data = _read_public_keys(keys)
    extra = [(k, _read_public_keys(k)) for k in extra_keys]
    with _gnupghome() as home:
        _import(home, keys_data, keys)
        keys_fprs = _fingerprints(home)
        if not keys_fprs:
            raise InputError(f"no public keys found in {keys}")
        for label, data in extra:
            _import(home, data, label)
        results = [verify_one(home, directory / name, keys_fprs) for name in artefacts]
    lines = [f"curl -s {_shq(keys_url)} | gpg --import" if keys_url else f"gpg --import {_shq(Path(keys).name)}"]
    lines += [f"gpg --verify {_shq(r['sig_file'])} {_shq(r['file'])}" for r in results]
    status = "PASS" if results and all(r["classification"] == "PASS" for r in results) else "FAIL"
    return {
        "step": "signatures",
        "status": status,
        "results": results,
        "keys_fingerprints": sorted(keys_fprs),
        "paste_recipe": "\n".join(lines),
    }


def cmd_signatures(args: argparse.Namespace) -> dict[str, Any]:
    return signatures(Path(args.dir), _patterns(args), args.keys, args.keys_url, args.extra_key or [])


# ---------------------------------------------------------------------------
# Step 3 — checksums
# ---------------------------------------------------------------------------


def parse_digest_file(text: str, kind: str) -> str | None:
    """The hex digest in a ``sha512sum``, BSD-tag or ``gpg --print-md`` file."""
    want = HEX_LEN[kind]
    bsd = re.search(r"\)\s*=\s*([0-9A-Fa-f]+)\s*$", text.strip())
    if bsd and len(bsd.group(1)) == want:
        return bsd.group(1).lower()
    first = text.strip().split()
    if first and re.fullmatch(rf"[0-9A-Fa-f]{{{want}}}", first[0]):
        return first[0].lower()
    if ":" in text:
        packed = re.sub(r"\s+", "", text.split(":", 1)[1])
        if re.fullmatch(rf"[0-9A-Fa-f]{{{want}}}", packed):
            return packed.lower()
    return None


def _digest_of(path: Path, kind: str) -> str:
    h = hashlib.new(kind)
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def checksums(directory: Path, patterns: Sequence[str], digests: Sequence[str]) -> dict[str, Any]:
    """Compare digest files with the artefacts.

    ``sha512`` is the only required digest: absent → MISSING-DIGEST, a FAIL.
    Every other known digest is optional and checked when its file is
    present; a MISMATCH on one FAILs, except ``md5``, which never fails
    alone — its presence or its mismatch is a WARN.
    """
    names = _dir_names(directory)
    artefacts = _found_artefacts(names, patterns)
    md5_present = any(n.endswith(".md5") for n in names)
    results: list[dict[str, Any]] = []
    recipe: list[str] = []
    status = "PASS" if artefacts else "FAIL"
    for name in artefacts:
        entries: list[dict[str, Any]] = []
        present = [k for k in DIGEST_TYPES if (directory / f"{name}.{k}").is_file()]
        kinds = list(dict.fromkeys([REQUIRED_DIGEST, *(d for d in digests if d in present), *present]))
        for kind in kinds:
            dfile = directory / f"{name}.{kind}"
            if kind != "md5":
                recipe.append(f"{kind}sum --check {_shq(dfile.name)}")
            if not dfile.is_file():
                entries.append({"type": kind, "classification": "MISSING-DIGEST"})
                status = "FAIL"
                continue
            recorded = parse_digest_file(dfile.read_text(errors="replace"), kind)
            entry: dict[str, Any] = {"type": kind, "classification": "PASS" if recorded == _digest_of(directory / name, kind) else "MISMATCH"}
            if recorded is None:
                entry["detail"] = "digest file could not be parsed"
            if entry["classification"] == "MISMATCH":
                if kind == "md5":
                    entry["detail"] = entry.get("detail", "md5 mismatch") + "; md5 never fails alone (WARN)"
                else:
                    status = "FAIL"
            entries.append(entry)
        results.append({"file": name, "digests": entries})
    if status == "PASS" and md5_present:
        status = "WARN"
    return {"step": "checksums", "status": status, "results": results, "deprecated_md5_present": md5_present, "paste_recipe": "\n".join(recipe)}


def cmd_checksums(args: argparse.Namespace) -> dict[str, Any]:
    return checksums(Path(args.dir), _patterns(args), args.digest)


# ---------------------------------------------------------------------------
# Step 5 — NOTICE / LICENSE
# ---------------------------------------------------------------------------


def _diff(current: Path, previous: Path, name: str) -> tuple[int, str]:
    old = previous.read_text(errors="replace").splitlines(keepends=True) if previous.is_file() else []
    new = current.read_text(errors="replace").splitlines(keepends=True)
    lines = list(difflib.unified_diff(old, new, fromfile=f"previous/{name}", tofile=f"rc/{name}"))
    changed = sum(1 for ln in lines if ln[:1] in "+-" and not ln.startswith(("+++", "---")))
    return changed, "".join(lines)


def notice_license(tree: Path, previous: Path | None) -> dict[str, Any]:
    if not tree.is_dir():
        raise InputError(f"not a directory: {tree}")
    out: dict[str, Any] = {"step": "notice-license", "status": None}
    present = {}
    for name in ("NOTICE", "LICENSE"):
        key = name.lower()
        present[key] = (tree / name).is_file()
        out[f"{key}_present"] = present[key]
    for name in ("NOTICE", "LICENSE"):
        key = name.lower()
        if previous is not None and present[key]:
            lines, text = _diff(tree / name, previous / name, name)
            out[f"{key}_diff_lines"], out[f"{key}_diff"] = lines, text
        else:
            out[f"{key}_diff_lines"], out[f"{key}_diff"] = None, None
    out["previous"] = str(previous) if previous is not None else None
    if not all(present.values()):
        out["status"] = "FAIL"
        absent = " and ".join(n for n in ("NOTICE", "LICENSE") if not present[n.lower()])
        out["detail"] = (
            f"{absent} absent from the root of the current RC artefact ({tree.name}); "
            "this RC is defective whatever any previous release contains. "
            "Diff line counts are null because there is no file to diff."
        )
    elif previous is None or (out["notice_diff_lines"] == 0 and out["license_diff_lines"] == 0):
        out["status"] = "PASS"
    else:
        out["status"] = "REVIEW"
    return out


def cmd_notice_license(args: argparse.Namespace) -> dict[str, Any]:
    return notice_license(Path(args.tree), Path(args.previous) if args.previous else None)


# ---------------------------------------------------------------------------
# Step 6 — binary exclusion
# ---------------------------------------------------------------------------


def _walk(top: Path) -> Iterator[tuple[Path, list[str], list[str]]]:
    for root, dirs, files in os.walk(top, followlinks=False):
        dirs.sort()
        yield Path(root), dirs, sorted(files)


def binary_find_recipe(dirname: str, extra: Sequence[str]) -> str:
    preds = [f"-name {_shq(g)}" for g in BASELINE_FILE_GLOBS]
    for glob in extra:
        g = glob.strip()
        if g in BASELINE_FILE_GLOBS or not g:
            continue
        preds.append(f"-path {_shq(dirname + '/' + _translate_glob(g))}" if "/" in g.lstrip("/") else f"-name {_shq(g)}")
    return f"find {_shq(dirname)} \\( -type f \\( " + " -o ".join(preds) + " \\) -o -type d -name '__pycache__' \\) -print"


def binaries(tree: Path, prohibit: Sequence[str], accept: Sequence[str], recipe_dir: str | None) -> dict[str, Any]:
    if not tree.is_dir():
        raise InputError(f"not a directory: {tree}")
    prohibited: list[str] = []
    expected: list[str] = []
    for root, dirs, files in _walk(tree):
        for d in dirs:
            if d == "__pycache__" and not (root / d).is_symlink():
                prohibited.append(_rel(root / d, tree))
        for f in files:
            path = root / f
            if path.is_symlink() or not path.is_file():
                continue
            rel = _rel(path, tree)
            hit_baseline = any(fnmatch.fnmatchcase(f, g) for g in BASELINE_FILE_GLOBS)
            if not hit_baseline and not any(_glob_hits(rel, g) for g in prohibit):
                continue
            if fnmatch.fnmatchcase(f, "*.pyc") or not any(_glob_hits(rel, g) for g in accept):
                prohibited.append(rel)
            else:
                expected.append(rel)
    return {
        "step": "binary-exclusion",
        "status": "FAIL" if prohibited else "PASS",
        "prohibited_found": sorted(prohibited),
        "expected_binaries": sorted(expected),
        "paste_recipe": binary_find_recipe(recipe_dir or tree.name, prohibit),
    }


def cmd_binaries(args: argparse.Namespace) -> dict[str, Any]:
    return binaries(Path(args.tree), args.prohibit or [], args.accept or [], args.recipe_dir)


# ---------------------------------------------------------------------------
# Step 7 — symlinks (dangling or escaping the archive)
# ---------------------------------------------------------------------------


SYMLINK_RECIPE = (
    "top=$(pwd -P); find . -type l | while IFS= read -r l; do "
    'if [ ! -e "$l" ]; then echo "dangling: $l"; '
    'else case "$(realpath "$l")" in "$top"|"$top"/*) ;; *) echo "outside: $l";; esac; fi; done'
)


def symlinks(tree: Path, validators: Sequence[str], recipe_dir: str | None) -> dict[str, Any]:
    """Every symlink must resolve to an existing path inside the unpacked archive."""
    if not tree.is_dir():
        raise InputError(f"not a directory: {tree}")
    top = tree.resolve()
    links: list[Path] = []
    for root, dirs, files in _walk(tree):
        links += [root / n for n in (*dirs, *files) if (root / n).is_symlink()]
    dangling: list[str] = []
    outside: list[str] = []
    for link in links:
        target = Path(os.path.realpath(link))
        if not target.exists():
            dangling.append(_rel(link, tree))
        elif target != top and top not in target.parents:
            outside.append(_rel(link, tree))
    if dangling or outside:
        status = "FAIL"
    elif validators:
        status = "REVIEW"
    else:
        status = "PASS" if links else "SKIP"
    recipe = [f"cd {_shq(recipe_dir or tree.name)}", SYMLINK_RECIPE, *validators]
    return {
        "step": "source-tree-integrity",
        "status": status,
        "symlinks_present": len(links),
        "dangling_symlinks": sorted(dangling),
        "outside_symlinks": sorted(outside),
        "validator_failures": [],
        "validators_to_run": list(validators),
        "paste_recipe": "\n".join(recipe),
    }


def cmd_symlinks(args: argparse.Namespace) -> dict[str, Any]:
    return symlinks(Path(args.tree), args.validator or [], args.recipe_dir)


# ---------------------------------------------------------------------------
# Step 8 — version consistency
# ---------------------------------------------------------------------------


def expected_version(rc_tag: str) -> str:
    m = re.fullmatch(r"(.+)-rc\d+", rc_tag)
    return m.group(1) if m else rc_tag


def _first_group(pattern: str, text: str, flags: int = re.MULTILINE) -> str | None:
    m = re.search(pattern, text, flags)
    if not m:
        return None
    return (m.group(1) if m.groups() else m.group(0)).strip()


def extract_version(path: Path, regex: str | None = None) -> tuple[str | None, str | None]:
    """(version, detail) for one manifest file; version is None when not found."""
    if not path.is_file():
        return None, "file not found"
    text = path.read_text(errors="replace")
    if regex:
        found = _first_group(regex, text)
        return found, None if found else "pattern did not match"
    name = path.name
    if name == "setup.cfg":
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read_string(text)
        value = cfg.get("metadata", "version", fallback=None)
        if value and value.strip().startswith(("attr:", "file:")):
            return None, f"dynamic version ({value.strip()})"
        return (value.strip(), None) if value else (None, "no [metadata] version")
    if name in ("pyproject.toml", "Cargo.toml"):
        data = tomllib.loads(text)
        if name == "Cargo.toml":
            value = data.get("package", {}).get("version")
        else:
            project = data.get("project", {})
            if "version" in project.get("dynamic", []):
                return None, "dynamic version ([project] dynamic)"
            value = project.get("version") or data.get("tool", {}).get("poetry", {}).get("version")
        return (value, None) if isinstance(value, str) else (None, "no version key")
    if name == "pom.xml":
        if "<!DOCTYPE" in text or "<!ENTITY" in text:
            return None, "pom.xml declares a DOCTYPE/ENTITY; not parsed"
        root = ET.fromstring(text)
        ns = root.tag[: root.tag.index("}") + 1] if root.tag.startswith("{") else ""
        node = root.find(f"{ns}version")
        return (node.text.strip(), None) if node is not None and node.text else (None, "no <project><version> (inherited from parent?)")
    if name == "package.json":
        value = json.loads(text).get("version")
        return (value, None) if isinstance(value, str) else (None, "no version key")
    if name.endswith(".py"):
        pattern = r"""^\s*version\s*=\s*['"]([^'"]+)['"]""" if name == "setup.py" else r"""^__version__\s*(?::\s*[\w.]+\s*)?=\s*['"]([^'"]+)['"]"""
        found = _first_group(pattern, text)
        return found, None if found else "no version assignment"
    if name.endswith(".properties"):
        found = _first_group(r"^\s*version\s*[=:]\s*(\S+)\s*$", text)
        return found, None if found else "no version property"
    if name in ("build.gradle", "build.gradle.kts"):
        found = _first_group(r"""^\s*version\s*=?\s*['"]([^'"]+)['"]""", text)
        return found, None if found else "no version assignment"
    if name in ("Chart.yaml", "Chart.yml"):
        found = _first_group(r"""^version:\s*['"]?([^'"\s]+)""", text)
        return found, None if found else "no version key"
    if name in ("VERSION", "version.txt", "VERSION.txt"):
        line = next((ln.strip() for ln in text.splitlines() if ln.strip()), None)
        return line, None if line else "empty file"
    return None, "no known extraction pattern for this file type; pass PATH=REGEX"


def version_consistency(tree: Path, expected: str, manifests: Sequence[str]) -> dict[str, Any]:
    results = []
    for spec in manifests:
        rel, _, regex = spec.partition("=")
        try:
            found, detail = extract_version(tree / rel, regex or None)
        except (ValueError, tomllib.TOMLDecodeError, ET.ParseError, configparser.Error) as exc:
            found, detail = None, f"could not parse: {exc}"
        entry: dict[str, Any] = {"file": rel, "extracted": found, "match": found == expected}
        if detail:
            entry["detail"] = detail
        results.append(entry)
    ok = bool(results) and all(r["match"] and r["extracted"] is not None for r in results)
    return {"step": "version-consistency", "status": "PASS" if ok else "FAIL", "expected_version": expected, "results": results}


def cmd_version(args: argparse.Namespace) -> dict[str, Any]:
    expected = args.expected or expected_version(args.rc_tag)
    return version_consistency(Path(args.tree), expected, args.manifest)


# ---------------------------------------------------------------------------
# Step 10 — verdict
# ---------------------------------------------------------------------------


def _parse_overrides(values: Sequence[str]) -> dict[str, str]:
    out = {}
    for v in values:
        step, sep, status = v.partition("=")
        if not sep or status not in STATUSES:
            raise InputError(f"--status wants STEP=PASS|WARN|FAIL|SKIP, got {v!r}")
        out[step] = status
    return out


def verdict(steps: Sequence[dict[str, Any]], overrides: dict[str, str]) -> dict[str, Any]:
    """Roll step statuses up: any FAIL → FAIL; else any WARN → PASS-WITH-WARNINGS; else PASS.

    SKIP is neutral — it neither passes nor warns — and every skipped step
    is listed in ``skip_steps`` so the report can name it.

    A tool-computed status is final; ``overrides`` only resolve steps the
    tool could not decide (``REVIEW``) or did not run (RAT, reproducibility).
    """
    summary: dict[str, str] = {}
    ignored = []
    for s in steps:
        summary[s["step"]] = s["status"]
    for step, status in overrides.items():
        if summary.get(step, "REVIEW") == "REVIEW":
            summary[step] = status
        else:
            ignored.append(f"{step}={status} (tool status {summary[step]} is final)")
    ordered = sorted(summary, key=lambda k: STEP_ORDER.index(k) if k in STEP_ORDER else len(STEP_ORDER))
    statuses = [summary[k] for k in ordered]
    unresolved = [k for k in ordered if summary[k] == "REVIEW"]
    if "FAIL" in statuses:
        overall: str | None = "FAIL"
    elif unresolved:
        overall = None
    elif "WARN" in statuses:
        overall = "PASS-WITH-WARNINGS"
    else:
        overall = "PASS"
    out: dict[str, Any] = {
        "step": "verdict",
        "overall": overall,
        "step_summary": [{"step": k, "status": summary[k]} for k in ordered],
        "fail_steps": [k for k in ordered if summary[k] == "FAIL"],
        "warn_steps": [k for k in ordered if summary[k] == "WARN"],
        "skip_steps": [k for k in ordered if summary[k] == "SKIP"],
        "unresolved": unresolved,
    }
    if ignored:
        out["ignored_overrides"] = ignored
    return out


def _load_steps(paths: Sequence[str]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for p in paths:
        data = json.loads(Path(p).read_text())
        items = data.get("steps", [data]) if isinstance(data, dict) else data
        steps += [s for s in items if isinstance(s, dict) and "step" in s and "status" in s and s["step"] != "verdict"]
    return steps


def cmd_verdict(args: argparse.Namespace) -> dict[str, Any]:
    return verdict(_load_steps(args.results), _parse_overrides(args.status or []))


# ---------------------------------------------------------------------------
# all
# ---------------------------------------------------------------------------


def cmd_all(args: argparse.Namespace) -> dict[str, Any]:
    staging, tree = Path(args.dir), Path(args.tree)
    steps = [
        inventory(_dir_names(staging), args.expect, args.digest, str(staging), args.expect_optional or []),
        signatures(staging, _patterns(args), args.keys, args.keys_url, args.extra_key or []),
        checksums(staging, _patterns(args), args.digest),
        notice_license(tree, Path(args.previous) if args.previous else None),
        binaries(tree, args.prohibit or [], args.accept or [], args.recipe_dir),
        symlinks(tree, args.validator or [], args.recipe_dir),
        version_consistency(tree, args.expected or expected_version(args.rc_tag), args.manifest),
    ]
    return {"tool": "release-verify", "steps": steps, "verdict": verdict(steps, _parse_overrides(args.status or []))}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _add_expect(p: argparse.ArgumentParser) -> None:
    p.add_argument("--expect", action="append", required=True, metavar="GLOB", help="required artefact filename pattern (repeatable); missing → FAIL")
    p.add_argument(
        "--expect-optional",
        action="append",
        metavar="GLOB",
        help="artefact release-build.md marks optional (repeatable); missing → WARN, staged → checked like the rest",
    )


def _add_digest(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--digest",
        action="append",
        choices=DIGEST_TYPES[:2],
        metavar="TYPE",
        help="digest type of the Digest set (repeatable): sha512 is always required, others are checked when present",
    )


def _add_keys(p: argparse.ArgumentParser) -> None:
    p.add_argument("--keys", required=True, help="local copy of the project KEYS file (public keys only)")
    p.add_argument("--keys-url", help="KEYS URL the voter fetches in paste_recipe")
    p.add_argument("--extra-key", action="append", metavar="FILE", help="public key that is NOT a trust anchor, to tell KEY-NOT-IN-KEYS from FAIL")


def _add_tree_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--recipe-dir", help="directory name to print in paste_recipe (default: the tree's basename)")


def _add_version(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--expected", help="expected version string")
    g.add_argument("--rc-tag", help="RC tag; the -rcN suffix is stripped")
    p.add_argument("--manifest", action="append", required=True, metavar="PATH[=REGEX]", help="manifest file relative to --tree (repeatable)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="release-verify", description=(__doc__ or "").split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("inventory", help="Step 1: staging listing vs expected artefacts")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--dir", help="local copy of the staging directory")
    src.add_argument("--listing", help="file with one staged filename per line (e.g. svn ls output)")
    _add_expect(p)
    _add_digest(p)
    p.set_defaults(func=cmd_inventory)

    p = sub.add_parser("signatures", help="Step 2: gpg --verify against the project KEYS only")
    p.add_argument("--dir", required=True, help="local copy of the staging directory")
    _add_expect(p)
    _add_keys(p)
    p.set_defaults(func=cmd_signatures)

    p = sub.add_parser("checksums", help="Step 3: digest files vs the artefacts")
    p.add_argument("--dir", required=True, help="local copy of the staging directory")
    _add_expect(p)
    _add_digest(p)
    p.set_defaults(func=cmd_checksums)

    p = sub.add_parser("notice-license", help="Step 5: NOTICE / LICENSE presence and diff")
    p.add_argument("--tree", required=True, help="unpacked source artefact")
    p.add_argument("--previous", help="directory holding the previous release's NOTICE and LICENSE")
    p.set_defaults(func=cmd_notice_license)

    p = sub.add_parser("binaries", help="Step 6: prohibited binaries in the unpacked source")
    p.add_argument("--tree", required=True, help="unpacked source artefact")
    p.add_argument("--prohibit", action="append", metavar="GLOB", help="additional prohibited glob from the Binary-exclude list")
    p.add_argument("--accept", action="append", metavar="GLOB", help="known-accepted exception from the Binary-exclude list")
    _add_tree_opts(p)
    p.set_defaults(func=cmd_binaries)

    p = sub.add_parser("symlinks", help="Step 7: symlinks that dangle or resolve outside the unpacked source")
    p.add_argument("--tree", required=True, help="unpacked source artefact")
    p.add_argument("--validator", action="append", metavar="CMD", help="source-tree validator; printed in the recipe, never run")
    _add_tree_opts(p)
    p.set_defaults(func=cmd_symlinks)

    p = sub.add_parser("version", help="Step 8: version string in every manifest, exact match")
    p.add_argument("--tree", required=True, help="unpacked source artefact")
    _add_version(p)
    p.set_defaults(func=cmd_version)

    p = sub.add_parser("verdict", help="Step 10: roll step results up into the overall verdict")
    p.add_argument("results", nargs="+", help="JSON files: step results or an `all` report")
    p.add_argument("--status", action="append", metavar="STEP=STATUS", help="status of a step the tool did not decide (repeatable)")
    p.set_defaults(func=cmd_verdict)

    p = sub.add_parser("all", help="Steps 1-3, 5-8 and the verdict in one report")
    p.add_argument("--dir", required=True, help="local copy of the staging directory")
    p.add_argument("--tree", required=True, help="unpacked source artefact")
    _add_expect(p)
    _add_digest(p)
    _add_keys(p)
    p.add_argument("--previous", help="directory holding the previous release's NOTICE and LICENSE")
    p.add_argument("--prohibit", action="append", metavar="GLOB")
    p.add_argument("--accept", action="append", metavar="GLOB")
    p.add_argument("--validator", action="append", metavar="CMD")
    _add_tree_opts(p)
    _add_version(p)
    p.add_argument("--status", action="append", metavar="STEP=STATUS", help="status of a step the tool did not decide (repeatable)")
    p.set_defaults(func=cmd_all)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(args, "digest") and not args.digest:
        args.digest = ["sha512"]
    try:
        result = args.func(args)
    except (InputError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
