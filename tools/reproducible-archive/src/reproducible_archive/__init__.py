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
"""Build, lint and compare **reproducible source archives**.

The archive-level rules come from
<https://reproducible-builds.org/docs/archives/>. Every rule that page
lists is implemented here, once, so a Release Manager and a voter get
byte-identical output from the same tag regardless of their `git`, `tar`,
`zip` or `gzip` version:

1. **File modification times** — every member carries the same mtime,
   `SOURCE_DATE_EPOCH` (default: the committer timestamp of the ref).
2. **File ordering** — members are emitted in a locale-independent,
   per-directory sorted order (what GNU tar's `--sort=name` produces).
3. **Ownership** — uid/gid `0`, empty user/group names (`--owner=0
   --group=0 --numeric-owner`).
4. **Permissions** — modes normalised to `a=rX,u+w` (`0644` files, `0755`
   executables and directories), so the packer's umask never leaks in.
5. **PAX headers** — no `atime` / `ctime` / PID-bearing headers
   (`--pax-option=...,delete=atime,delete=ctime`).
6. **gzip** — header mtime `0` and no embedded filename (`gzip -n`).
7. **zip** — no "extra" field attributes (`zip -X`), UTC DOS timestamps
   from `SOURCE_DATE_EPOCH`, Unix create-system so modes round-trip.

The input is always `git archive --format=tar <ref>`, so only tracked
files at the ref are ever packed and the repository's `.gitattributes`
`export-ignore` rules decide what is left out. Two more inputs that
vary between machines are pinned as well: the builder's
`core.autocrlf` / `core.eol` (which `git archive` would otherwise apply
to `text` files) and the archive tool itself (this module, not the
local `tar` / `zip` / `git` version). The commit id is carried as
provenance the way `git archive` carries it — a global PAX header
`comment` in tar, the archive comment in zip.

Every archive also gets a **Software Heritage identifier** (SWHID,
ISO/IEC 18670): `swh:1:dir:<sha1>` of the expanded content, computed
as git computes a tree id, so it is intrinsic to the files — a voter
recomputes it from the staged bytes, ATR computes the same value at
compose time, and it equals `git rev-parse <ref>^{tree}` unless
`.gitattributes` altered the export — plus `swh:1:rev:<commit>` and
the origin URL as qualifiers.

The module is stdlib-only on purpose: it can be run as `python3 <this
file>` from any checkout, embedded in a CI workflow, or invoked via
`uv run`. Sub-commands: `build`, `check`, `compare`, `swhid`, `recipe`,
`epoch`. See `tools/reproducible-archive/README.md` for the contract
each one keeps.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

__version__ = "0.1.0"

FORMATS = ("tar.gz", "zip")
#: Earliest timestamp a ZIP DOS date/time field can encode (1980-01-01T00:00:00Z).
ZIP_EPOCH_MIN = 315532800
_FILE_MODE = 0o644
_EXEC_MODE = 0o755
_DIR_MODE = 0o755
_GZIP_FLAG_FEXTRA = 0x04
_GZIP_FLAG_FNAME = 0x08
_GZIP_FLAG_FCOMMENT = 0x10
_PAX_PID_NAME = re.compile(r"PaxHeaders\.\d+")
_PAX_TIME_KEYS = ("atime", "ctime", "LIBARCHIVE.creationtime", "SCHILY.dev", "SCHILY.ino", "SCHILY.nlink")


# --------------------------------------------------------------------------- model


@dataclass(frozen=True)
class Entry:
    """One archive member in a format-neutral shape."""

    name: str
    kind: str  # "file" | "dir" | "symlink"
    mode: int
    data: bytes = b""
    linkname: str = ""

    @property
    def sort_key(self) -> tuple[bytes, ...]:
        """Per-directory byte-wise order (GNU tar `--sort=name`): a
        directory sorts before every path beneath it, siblings sort by
        their raw bytes, never by the current locale."""
        return tuple(part.encode("utf-8", "surrogateescape") for part in self.name.rstrip("/").split("/"))


@dataclass
class CheckResult:
    name: str
    status: str  # "PASS" | "FAIL" | "SKIP"
    detail: str = ""


@dataclass
class Comparison:
    verdict: str  # "identical" | "content-identical" | "differs"
    sha512_a: str
    sha512_b: str
    swhid_a: str = ""
    swhid_b: str = ""
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    metadata_differences: list[str] = field(default_factory=list)


class ReproError(RuntimeError):
    """A failure the CLI reports on stderr with exit code 2."""


# --------------------------------------------------------------------------- git helpers


def _git(args: Sequence[str], repo: Path) -> bytes:
    try:
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True).stdout
    except FileNotFoundError as exc:
        raise ReproError("git is not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise ReproError(f"git {' '.join(args)} failed: {exc.stderr.decode(errors='replace').strip()}") from exc


def source_date_epoch(ref: str, repo: Path, override: int | None = None) -> int:
    """Resolve `SOURCE_DATE_EPOCH` for a ref: an explicit override wins,
    then the environment variable, then the committer timestamp of the
    ref (which is what makes two builders of the same tag agree)."""
    if override is not None:
        return int(override)
    env = os.environ.get("SOURCE_DATE_EPOCH")
    if env:
        try:
            return int(env)
        except ValueError as exc:
            raise ReproError(f"SOURCE_DATE_EPOCH is not an integer: {env!r}") from exc
    out = _git(["log", "-1", "--format=%ct", ref], repo).decode().strip()
    if not out.isdigit():
        raise ReproError(f"cannot resolve a committer timestamp for {ref!r}")
    return int(out)


def commit_of(ref: str, repo: Path) -> str:
    return _git(["rev-parse", f"{ref}^{{commit}}"], repo).decode().strip()


def git_archive_tar(ref: str, repo: Path, prefix: str, worktree_attributes: bool = False) -> bytes:
    """`git archive --format=tar` at the ref. Only tracked files are
    included and `.gitattributes` `export-ignore` rules are honoured — the
    two properties that make the archive a function of the tag alone.

    `worktree_attributes` passes `--worktree-attributes`, so a not-yet-
    committed `.gitattributes` edit is applied: what the first-release
    review uses to preview an exclusion set before committing it. A
    release build never sets it."""
    # `git archive` applies the same conversions as a checkout: committed
    # `.gitattributes` (`export-ignore`, `export-subst`, `text` / `eol`)
    # are the project's intent and stay in force, but the *builder's* own
    # `core.autocrlf` / `core.eol` must not leak into the export, so both
    # are pinned to the values a fresh clone on Linux would use.
    args = ["-c", "core.autocrlf=false", "-c", "core.eol=lf", "archive", "--format=tar"]
    if worktree_attributes:
        args.append("--worktree-attributes")
    if prefix:
        args.append(f"--prefix={prefix.rstrip('/')}/")
    args.append(ref)
    return _git(args, repo)


# --------------------------------------------------------------------------- normalisation


def normalize_mode(mode: int, kind: str) -> int:
    """`a=rX,u+w`: directories and anything executable become 0755,
    everything else 0644. Setuid/setgid/sticky bits are dropped."""
    if kind == "dir":
        return _DIR_MODE
    if kind == "symlink":
        return 0o777
    return _EXEC_MODE if mode & 0o111 else _FILE_MODE


def sort_entries(entries: Iterable[Entry]) -> list[Entry]:
    return sorted(entries, key=lambda e: e.sort_key)


def read_tar_entries(data: bytes) -> list[Entry]:
    entries: list[Entry] = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
        for member in tf:
            if member.isdir():
                entries.append(Entry(member.name.rstrip("/") + "/", "dir", member.mode))
            elif member.issym():
                entries.append(Entry(member.name, "symlink", member.mode, linkname=member.linkname))
            elif member.isfile():
                fh = tf.extractfile(member)
                payload = fh.read() if fh is not None else b""
                entries.append(Entry(member.name, "file", member.mode, data=payload))
            else:
                raise ReproError(f"unsupported member type {member.type!r} for {member.name}")
    return entries


def read_zip_entries(data: bytes) -> list[Entry]:
    entries: list[Entry] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            mode = (info.external_attr >> 16) & 0o7777
            unix_type = (info.external_attr >> 16) & 0o170000
            if info.is_dir():
                entries.append(Entry(info.filename, "dir", mode))
            elif unix_type == stat.S_IFLNK:
                entries.append(Entry(info.filename, "symlink", mode, linkname=zf.read(info).decode()))
            else:
                entries.append(Entry(info.filename, "file", mode, data=zf.read(info)))
    return entries


def read_entries(path: Path) -> list[Entry]:
    data = path.read_bytes()
    if zipfile.is_zipfile(io.BytesIO(data)):
        return read_zip_entries(data)
    return read_tar_entries(data)


# --------------------------------------------------------------------------- writers


def write_tar_gz(entries: Iterable[Entry], epoch: int, level: int = 6, commit: str | None = None) -> bytes:
    """Deterministic `.tar.gz`: sorted members, one mtime, uid/gid 0, no
    names, normalised modes, no atime/ctime PAX headers, and a gzip
    wrapper with mtime 0 and no filename (`gzip -n`). With `commit`, a
    global PAX header carries `comment=<commit>` — the provenance note
    `git archive` itself writes, readable with `tar --pax-option` aware
    tools and harmless to the rest."""
    tar_buf = io.BytesIO()
    global_headers = {"comment": commit} if commit else {}
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.PAX_FORMAT, pax_headers=global_headers) as tf:
        for entry in sort_entries(entries):
            info = tarfile.TarInfo(entry.name.rstrip("/") if entry.kind == "dir" else entry.name)
            info.mtime = epoch
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = normalize_mode(entry.mode, entry.kind)
            if entry.kind == "dir":
                info.type = tarfile.DIRTYPE
                tf.addfile(info)
            elif entry.kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = entry.linkname
                tf.addfile(info)
            else:
                info.type = tarfile.REGTYPE
                info.size = len(entry.data)
                tf.addfile(info, io.BytesIO(entry.data))
    out = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", compresslevel=level, fileobj=out, mtime=0) as gz:
        gz.write(tar_buf.getvalue())
    return out.getvalue()


def _dos_time(epoch: int) -> tuple[int, int, int, int, int, int]:
    dt = datetime.fromtimestamp(max(epoch, ZIP_EPOCH_MIN), tz=UTC)
    return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second - dt.second % 2)


def write_zip(entries: Iterable[Entry], epoch: int, level: int = 6, commit: str | None = None) -> bytes:
    """Deterministic `.zip`: sorted members, one UTC DOS timestamp, no
    extra-field attributes (`zip -X`), Unix create-system so the
    normalised modes survive the round trip, no member comments. With
    `commit`, the archive comment is the commit id — what `git archive
    --format=zip` writes there."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=level) as zf:
        if commit:
            zf.comment = commit.encode()
        for entry in sort_entries(entries):
            info = zipfile.ZipInfo(entry.name, date_time=_dos_time(epoch))
            info.create_system = 3
            info.extra = b""
            info.comment = b""
            mode = normalize_mode(entry.mode, entry.kind)
            if entry.kind == "dir":
                info.external_attr = ((stat.S_IFDIR | mode) << 16) | 0x10
                info.compress_type = zipfile.ZIP_STORED
                zf.writestr(info, b"")
            elif entry.kind == "symlink":
                info.external_attr = (stat.S_IFLNK | mode) << 16
                info.compress_type = zipfile.ZIP_STORED
                zf.writestr(info, entry.linkname.encode())
            else:
                info.external_attr = (stat.S_IFREG | mode) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, entry.data)
    return out.getvalue()


def build(
    ref: str,
    repo: Path,
    fmt: str,
    prefix: str,
    epoch: int | None = None,
    worktree_attributes: bool = False,
) -> tuple[bytes, int]:
    """Produce the archive bytes for `ref` and the epoch they were built with."""
    if fmt not in FORMATS:
        raise ReproError(f"unsupported format {fmt!r}; expected one of {', '.join(FORMATS)}")
    resolved_epoch = source_date_epoch(ref, repo, epoch)
    commit = commit_of(ref, repo)
    entries = read_tar_entries(git_archive_tar(ref, repo, prefix, worktree_attributes))
    if not entries:
        raise ReproError(f"git archive {ref} produced no entries")
    if fmt == "zip":
        if resolved_epoch < ZIP_EPOCH_MIN:
            raise ReproError(f"SOURCE_DATE_EPOCH {resolved_epoch} predates 1980; ZIP cannot encode it")
        return write_zip(entries, resolved_epoch, commit=commit), resolved_epoch
    return write_tar_gz(entries, resolved_epoch, commit=commit), resolved_epoch


# --------------------------------------------------------------------------- check


def _sha512(data: bytes) -> str:
    return hashlib.sha512(data).hexdigest()


def _check_order(names: Sequence[str]) -> CheckResult:
    keyed = [Entry(n, "file", 0).sort_key for n in names]
    if keyed == sorted(keyed):
        return CheckResult("file-ordering", "PASS", "members are in per-directory byte order")
    for i in range(1, len(keyed)):
        if keyed[i] < keyed[i - 1]:
            return CheckResult("file-ordering", "FAIL", f"{names[i]!r} sorts before {names[i - 1]!r}")
    return CheckResult("file-ordering", "FAIL", "members are not sorted")


def _check_modes(modes: Sequence[tuple[str, str, int]]) -> CheckResult:
    bad = [f"{name} ({kind}) mode {mode:04o}" for name, kind, mode in modes if kind != "symlink" and normalize_mode(mode, kind) != mode]
    if bad:
        return CheckResult("permissions", "FAIL", "; ".join(bad[:5]) + (" …" if len(bad) > 5 else ""))
    return CheckResult("permissions", "PASS", "every mode is a=rX,u+w")


def _check_single_mtime(mtimes: Sequence[int], epoch: int | None) -> CheckResult:
    distinct = sorted(set(mtimes))
    if len(distinct) > 1:
        return CheckResult("modification-times", "FAIL", f"{len(distinct)} distinct mtimes (e.g. {distinct[0]} and {distinct[-1]})")
    if epoch is not None and distinct and distinct[0] != epoch:
        return CheckResult("modification-times", "FAIL", f"mtime {distinct[0]} != SOURCE_DATE_EPOCH {epoch}")
    return CheckResult("modification-times", "PASS", f"single mtime {distinct[0] if distinct else 'n/a'}")


def _raw_tar_pax_names(data: bytes) -> list[str]:
    """Names of PAX/GNU extended-header blocks, read from the raw stream
    (tarfile hides them), so a `PaxHeaders.<pid>` name can be caught."""
    names: list[str] = []
    off = 0
    while off + 512 <= len(data):
        block = data[off : off + 512]
        if block == b"\0" * 512:
            break
        name = block[0:100].split(b"\0", 1)[0].decode("utf-8", "surrogateescape")
        typeflag = block[156:157]
        size_field = block[124:136].split(b"\0", 1)[0].strip()
        size = int(size_field, 8) if size_field else 0
        if typeflag in (b"x", b"g", b"L", b"K"):
            names.append(name)
        off += 512 + ((size + 511) // 512) * 512
    return names


def check_tar(data: bytes, epoch: int | None = None) -> list[CheckResult]:
    results: list[CheckResult] = []
    is_gz = data[:2] == b"\x1f\x8b"
    if is_gz:
        flags, mtime = data[3], int.from_bytes(data[4:8], "little")
        problems = []
        if mtime != 0:
            problems.append(f"header mtime {mtime}")
        if flags & _GZIP_FLAG_FNAME:
            problems.append("embedded filename")
        if flags & _GZIP_FLAG_FEXTRA:
            problems.append("extra field")
        if flags & _GZIP_FLAG_FCOMMENT:
            problems.append("comment")
        results.append(
            CheckResult("gzip-header", "FAIL", ", ".join(problems)) if problems else CheckResult("gzip-header", "PASS", "mtime 0, no filename (gzip -n)")
        )
        raw = gzip.decompress(data)
    else:
        results.append(CheckResult("gzip-header", "SKIP", "not gzip-compressed"))
        raw = data
    names: list[str] = []
    modes: list[tuple[str, str, int]] = []
    mtimes: list[int] = []
    owners: list[str] = []
    pax_hits: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tf:
        for m in tf:
            kind = "dir" if m.isdir() else "symlink" if m.issym() else "file"
            names.append(m.name)
            modes.append((m.name, kind, m.mode))
            mtimes.append(int(m.mtime))
            if m.uid or m.gid or m.uname or m.gname:
                owners.append(f"{m.name} uid={m.uid} gid={m.gid} uname={m.uname!r} gname={m.gname!r}")
            for key in _PAX_TIME_KEYS:
                if key in m.pax_headers:
                    pax_hits.append(f"{m.name}: {key}")
    results.append(_check_order(names))
    results.append(_check_single_mtime(mtimes, epoch))
    results.append(CheckResult("ownership", "FAIL", "; ".join(owners[:5])) if owners else CheckResult("ownership", "PASS", "uid/gid 0, no user/group names"))
    results.append(_check_modes(modes))
    pid_names = [n for n in _raw_tar_pax_names(raw) if _PAX_PID_NAME.search(n)]
    pax_hits.extend(f"PID-bearing header name {n}" for n in pid_names)
    results.append(
        CheckResult("pax-headers", "FAIL", "; ".join(pax_hits[:5])) if pax_hits else CheckResult("pax-headers", "PASS", "no atime/ctime/PID headers")
    )
    results.append(CheckResult("zip-extra-fields", "SKIP", "not a zip"))
    return results


def check_zip(data: bytes, epoch: int | None = None) -> list[CheckResult]:
    results: list[CheckResult] = [CheckResult("gzip-header", "SKIP", "not a tar.gz")]
    names: list[str] = []
    modes: list[tuple[str, str, int]] = []
    stamps: list[tuple[int, int, int, int, int, int]] = []
    extras: list[str] = []
    owners: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        if zf.comment and not re.fullmatch(rb"[0-9a-f]{40}", zf.comment):
            extras.append("archive comment present (only a commit id, as git archive writes, is expected)")
        for info in zf.infolist():
            names.append(info.filename)
            unix_type = (info.external_attr >> 16) & 0o170000
            kind = "dir" if info.is_dir() else "symlink" if unix_type == stat.S_IFLNK else "file"
            modes.append((info.filename, kind, (info.external_attr >> 16) & 0o7777))
            stamps.append(info.date_time)
            if info.extra:
                extras.append(f"{info.filename}: {len(info.extra)}-byte extra field")
            if info.comment:
                extras.append(f"{info.filename}: member comment")
            if info.create_system != 3:
                owners.append(f"{info.filename}: create_system {info.create_system} (expected 3 = Unix)")
    results.append(_check_order(names))
    distinct = sorted(set(stamps))
    if len(distinct) > 1:
        results.append(CheckResult("modification-times", "FAIL", f"{len(distinct)} distinct timestamps"))
    elif epoch is not None and distinct and distinct[0] != _dos_time(epoch):
        results.append(CheckResult("modification-times", "FAIL", f"timestamp {distinct[0]} != SOURCE_DATE_EPOCH {epoch} (UTC)"))
    else:
        results.append(CheckResult("modification-times", "PASS", f"single timestamp {distinct[0] if distinct else 'n/a'}"))
    results.append(
        CheckResult("ownership", "FAIL", "; ".join(owners[:5])) if owners else CheckResult("ownership", "PASS", "Unix create-system on every member")
    )
    results.append(_check_modes(modes))
    results.append(CheckResult("pax-headers", "SKIP", "not a tar"))
    results.append(
        CheckResult("zip-extra-fields", "FAIL", "; ".join(extras[:5]))
        if extras
        else CheckResult("zip-extra-fields", "PASS", "no extra fields or comments (zip -X)")
    )
    return results


def check(path: Path, epoch: int | None = None, swhid: str | None = None) -> list[CheckResult]:
    """Lint `path` against the checklist; with `swhid`, also require the
    archive content's `swh:1:dir:` to equal it (the value recorded on the
    planning issue, or the one ATR shows for the candidate)."""
    data = path.read_bytes()
    results = check_zip(data, epoch) if zipfile.is_zipfile(io.BytesIO(data)) else check_tar(data, epoch)
    if swhid:
        actual = swhid_of_archive(path)
        results.append(
            CheckResult("swhid", "PASS", f"content is {actual}")
            if actual == swhid.split(";", 1)[0]
            else CheckResult("swhid", "FAIL", f"content is {actual}, expected {swhid.split(';', 1)[0]}")
        )
    return results


# --------------------------------------------------------------------------- compare


def _member_digest(entry: Entry) -> tuple[str, str, int, str]:
    return (entry.kind, hashlib.sha256(entry.data).hexdigest(), normalize_mode(entry.mode, entry.kind), entry.linkname)


def compare(path_a: Path, path_b: Path) -> Comparison:
    """Three verdicts, in decreasing strength:

    * `identical` — byte-for-byte the same file (the bar ASF automated
      release signing sets for validation on trusted hardware);
    * `content-identical` — every member's bytes, type, normalised mode
      and link target match, only archive metadata (timestamps, owners,
      ordering, extra fields, compression) differs — what a voter with a
      different `git`/`tar` version gets from a plain `git archive`;
    * `differs` — members were added, removed or changed.
    """
    data_a, data_b = path_a.read_bytes(), path_b.read_bytes()
    sha_a, sha_b = _sha512(data_a), _sha512(data_b)
    swh_a, swh_b = swhid_of_archive(path_a), swhid_of_archive(path_b)
    if data_a == data_b:
        return Comparison("identical", sha_a, sha_b, swh_a, swh_b)
    ents_a = {e.name.rstrip("/"): e for e in read_entries(path_a)}
    ents_b = {e.name.rstrip("/"): e for e in read_entries(path_b)}
    added = sorted(set(ents_b) - set(ents_a))
    removed = sorted(set(ents_a) - set(ents_b))
    changed = sorted(n for n in set(ents_a) & set(ents_b) if _member_digest(ents_a[n]) != _member_digest(ents_b[n]))
    if added or removed or changed:
        return Comparison("differs", sha_a, sha_b, swh_a, swh_b, added, removed, changed)
    meta: list[str] = []
    if [e.name for e in read_entries(path_a)] != [e.name for e in read_entries(path_b)]:
        meta.append("member order differs")
    fails_a = {r.name for r in check(path_a) if r.status == "FAIL"}
    fails_b = {r.name for r in check(path_b) if r.status == "FAIL"}
    for name in sorted(fails_a | fails_b):
        meta.append(f"reproducibility check {name} fails on {'both' if name in fails_a and name in fails_b else 'A' if name in fails_a else 'B'}")
    if not meta:
        meta.append("compression or container bytes differ (same members, same modes)")
    return Comparison("content-identical", sha_a, sha_b, swh_a, swh_b, metadata_differences=meta)


# --------------------------------------------------------------------------- SWHID


def _git_object_sha1(kind: str, payload: bytes) -> bytes:
    # git and SWH object ids are SHA-1 by definition; this is an identifier, not a security hash.
    return hashlib.sha1(f"{kind} {len(payload)}\0".encode() + payload).digest()


def _tree_sort_key(name: bytes, is_dir: bool) -> bytes:
    # git orders tree entries by name, comparing a directory as if its name
    # ended in "/", so "a" (dir) sorts after "a-b" (file) but before "a.c".
    return name + b"/" if is_dir else name


def swhid_dir_of_entries(entries: Iterable[Entry], strip_prefix: str | None = None) -> str:
    """The Software Heritage directory identifier (`swh:1:dir:<sha1>`) of
    the content in `entries`.

    SWH computes a directory identifier exactly as git computes a tree
    object id — blob objects for files (`100644` / `100755`) and symlinks
    (`120000`, the link target as content), tree objects for directories
    (`40000`), entries sorted by name with git's directory rule — so the
    value is intrinsic to the bytes: a voter recomputes it from the
    staged archive without git, ATR computes it at compose time, and it
    equals `git rev-parse <ref>^{tree}` unless `export-ignore` altered
    the export. Reference: https://docs.softwareheritage.org/devel/swh-model/persistent-identifiers.html
    """
    root: dict[str, object] = {}
    prefix = (strip_prefix or "").rstrip("/")
    for entry in entries:
        name = entry.name.rstrip("/")
        if prefix:
            if name == prefix:
                continue
            if not name.startswith(prefix + "/"):
                raise ReproError(f"entry {entry.name!r} is outside the prefix {prefix!r}")
            name = name[len(prefix) + 1 :]
        if not name:
            continue
        parts = name.split("/")
        node = root
        for part in parts[:-1]:
            child = node.setdefault(part, {})
            if not isinstance(child, dict):
                raise ReproError(f"{name!r}: {part!r} is both a file and a directory")
            node = child
        if entry.kind == "dir":
            node.setdefault(parts[-1], {})
        else:
            node[parts[-1]] = entry

    def tree_id(node: dict[str, object]) -> bytes:
        rows: list[tuple[bytes, bytes]] = []
        for name, child in node.items():
            bname = name.encode("utf-8", "surrogateescape")
            if isinstance(child, dict):
                rows.append((_tree_sort_key(bname, True), b"40000 " + bname + b"\0" + tree_id(child)))
            else:
                assert isinstance(child, Entry)
                if child.kind == "symlink":
                    mode, blob = b"120000", child.linkname.encode("utf-8", "surrogateescape")
                else:
                    mode, blob = (b"100755" if child.mode & 0o111 else b"100644"), child.data
                rows.append((_tree_sort_key(bname, False), mode + b" " + bname + b"\0" + _git_object_sha1("blob", blob)))
        rows.sort(key=lambda r: r[0])
        return _git_object_sha1("tree", b"".join(r[1] for r in rows))

    return "swh:1:dir:" + tree_id(root).hex()


def archive_top_level_prefix(entries: Sequence[Entry]) -> str | None:
    """The single top-level directory every entry lives under (a `git
    archive --prefix` archive), or None when entries sit at the root."""
    tops = {e.name.rstrip("/").split("/", 1)[0] for e in entries if e.name.rstrip("/")}
    if len(tops) != 1:
        return None
    top = tops.pop()
    return top if all(e.name.rstrip("/") == top or e.name.startswith(top + "/") for e in entries) else None


def swhid_of_archive(path: Path) -> str:
    """`swh:1:dir:` of an archive's content, with a single top-level
    prefix directory (e.g. `apache-foo-1.0.0/`) stripped, so the value
    describes the tree a voter unpacks and ATR expands."""
    entries = read_entries(path)
    return swhid_dir_of_entries(entries, archive_top_level_prefix(entries))


def swhid_rev(ref: str, repo: Path) -> str:
    return "swh:1:rev:" + commit_of(ref, repo)


def swhid_repo_dir(ref: str, repo: Path) -> str:
    """`swh:1:dir:` of the *whole* repository tree at the ref (`git
    rev-parse <ref>^{tree}`); equals the archive's only when nothing is
    `export-ignore`d."""
    return "swh:1:dir:" + _git(["rev-parse", f"{ref}^{{tree}}"], repo).decode().strip()


def qualified_swhid(core: str, origin: str | None = None, anchor: str | None = None) -> str:
    """Add the contextual qualifiers SWH defines: the origin URL the tree
    was archived from and the revision it is anchored to."""
    out = core
    if origin:
        out += f";origin={origin}"
    if anchor:
        out += f";anchor={anchor}"
    return out


# --------------------------------------------------------------------------- recipe


def recipe(ref: str, fmt: str, prefix: str, out: str) -> str:
    """The equivalent shell recipe, straight from reproducible-builds.org
    (GNU tar >= 1.28, Info-ZIP `zip`), for a Release Manager who prefers
    to run the standard tools rather than this module."""
    if fmt not in FORMATS:
        raise ReproError(f"unsupported format {fmt!r}; expected one of {', '.join(FORMATS)}")
    p = prefix.rstrip("/")
    lines = [
        "# Reproducible source archive — every step from",
        "# https://reproducible-builds.org/docs/archives/ applied to `git archive`.",
        f"export SOURCE_DATE_EPOCH=\"$(git log -1 --format=%ct '{ref}')\"",
        "rm -rf build && mkdir build",
        f"git archive --format=tar --prefix='{p}/' '{ref}' | tar -xf - -C build",
        "# 1. one modification time for every file (SOURCE_DATE_EPOCH)",
        'find build -print0 | xargs -0r touch --no-dereference --date="@${SOURCE_DATE_EPOCH}"',
    ]
    if fmt == "tar.gz":
        lines += [
            "# 2. sorted names  3. uid/gid 0  4. a=rX,u+w  5. no atime/ctime PAX headers  6. gzip -n",
            'tar --sort=name --mtime="@${SOURCE_DATE_EPOCH}" --owner=0 --group=0 --numeric-owner \\',
            "    --mode=a=rX,u+w \\",
            "    --pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime \\",
            f"    -C build -cf - '{p}' | gzip -6 -n > '{out}'",
        ]
    else:
        lines += [
            "# 2. sorted names (C locale)  4. a=rX,u+w  7. no extra fields (zip -X), UTC timestamps",
            "chmod -R a=rX,u+w build",
            f"(cd build && find '{p}' -print0 | LC_ALL=C sort -z | tr '\\0' '\\n' \\",
            f"   | TZ=UTC zip -X -q -@ '../{out}')",
        ]
    lines += [
        "# Verify the result against the checklist, and record its SWHID next to the commit:",
        f"python3 tools/reproducible-archive/src/reproducible_archive/__init__.py check '{out}' --epoch \"${{SOURCE_DATE_EPOCH}}\"",
        f"python3 tools/reproducible-archive/src/reproducible_archive/__init__.py swhid '{out}' --ref '{ref}'",
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- CLI


def _print_checks(results: list[CheckResult], as_json: bool) -> int:
    if as_json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        for r in results:
            print(f"{r.status:4} {r.name:20} {r.detail}")
    return 1 if any(r.status == "FAIL" for r in results) else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repro-archive", description=__doc__.split("\n\n")[0])
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="build a reproducible archive from a git ref")
    p_build.add_argument("--ref", required=True, help="tag, branch or commit to archive")
    p_build.add_argument("--repo", default=".", help="repository path (default: .)")
    p_build.add_argument("--format", dest="fmt", choices=FORMATS, default="tar.gz")
    p_build.add_argument("--prefix", required=True, help="top-level directory inside the archive")
    p_build.add_argument("-o", "--output", required=True, help="output file")
    p_build.add_argument("--epoch", type=int, default=None, help="SOURCE_DATE_EPOCH override")
    p_build.add_argument("--origin", default=None, help="URL of the git repository, recorded as the SWHID origin qualifier")
    p_build.add_argument(
        "--worktree-attributes",
        action="store_true",
        help="apply the working tree's .gitattributes instead of the ref's (preview an export-ignore edit; never for a release build)",
    )

    p_check = sub.add_parser("check", help="lint an archive against the reproducible-builds.org checklist")
    p_check.add_argument("archive")
    p_check.add_argument("--epoch", type=int, default=None, help="expected SOURCE_DATE_EPOCH")
    p_check.add_argument("--swhid", default=None, help="expected swh:1:dir:… of the archive content (qualifiers are ignored)")
    p_check.add_argument("--json", action="store_true")

    p_swh = sub.add_parser("swhid", help="print Software Heritage identifiers for an archive's content or a git ref")
    p_swh.add_argument("archive", nargs="?", help="archive whose content swh:1:dir: to compute")
    p_swh.add_argument("--ref", default=None, help="git ref: print swh:1:rev: and the repository tree's swh:1:dir:")
    p_swh.add_argument("--repo", default=".")
    p_swh.add_argument("--origin", default=None, help="repository URL for the origin qualifier")

    p_cmp = sub.add_parser("compare", help="compare two archives (identical / content-identical / differs)")
    p_cmp.add_argument("archive_a")
    p_cmp.add_argument("archive_b")
    p_cmp.add_argument("--json", action="store_true")
    p_cmp.add_argument("--require-identical", action="store_true", help="exit 1 unless byte-identical")

    p_rec = sub.add_parser("recipe", help="print the equivalent GNU tar / zip shell recipe")
    p_rec.add_argument("--ref", required=True)
    p_rec.add_argument("--format", dest="fmt", choices=FORMATS, default="tar.gz")
    p_rec.add_argument("--prefix", required=True)
    p_rec.add_argument("-o", "--output", required=True)

    p_epoch = sub.add_parser("epoch", help="print SOURCE_DATE_EPOCH for a ref")
    p_epoch.add_argument("--ref", required=True)
    p_epoch.add_argument("--repo", default=".")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "build":
            repo = Path(args.repo)
            data, epoch = build(args.ref, repo, args.fmt, args.prefix, args.epoch, args.worktree_attributes)
            out_path = Path(args.output)
            out_path.write_bytes(data)
            commit = commit_of(args.ref, repo)
            rev = swhid_rev(args.ref, repo)
            archive_dir = swhid_of_archive(out_path)
            repo_dir = swhid_repo_dir(args.ref, repo)
            print(f"wrote {args.output}")
            print(f"commit {commit}")
            print(f"SOURCE_DATE_EPOCH {epoch}")
            print(f"sha512 {_sha512(data)}")
            print(f"swhid_rev {qualified_swhid(rev, args.origin)}")
            print(f"swhid_dir {qualified_swhid(archive_dir, args.origin, rev)}")
            if archive_dir == repo_dir:
                print("swhid_dir_note identical to the repository tree at the commit (nothing export-ignored)")
            else:
                print(f"swhid_dir_note differs from the repository tree {repo_dir} (export-ignore / export-subst / eol attributes applied)")
            if args.origin:
                print(f"origin {args.origin}")
            return 0
        if args.cmd == "check":
            return _print_checks(check(Path(args.archive), args.epoch, args.swhid), args.json)
        if args.cmd == "swhid":
            if not args.archive and not args.ref:
                raise ReproError("give an archive, --ref, or both")
            anchor: str | None = swhid_rev(args.ref, Path(args.repo)) if args.ref else None
            if anchor:
                print(f"swhid_rev {qualified_swhid(anchor, args.origin)}")
                print(f"swhid_repo_dir {qualified_swhid(swhid_repo_dir(args.ref, Path(args.repo)), args.origin, anchor)}")
            if args.archive:
                print(f"swhid_dir {qualified_swhid(swhid_of_archive(Path(args.archive)), args.origin, anchor)}")
            return 0
        if args.cmd == "compare":
            result = compare(Path(args.archive_a), Path(args.archive_b))
            if args.json:
                print(json.dumps(asdict(result), indent=2))
            else:
                print(f"verdict {result.verdict}")
                print(f"sha512 A {result.sha512_a}")
                print(f"sha512 B {result.sha512_b}")
                print(f"swhid  A {result.swhid_a}")
                print(f"swhid  B {result.swhid_b}")
                for label, items in (
                    ("added", result.added),
                    ("removed", result.removed),
                    ("changed", result.changed),
                    ("metadata", result.metadata_differences),
                ):
                    for item in items:
                        print(f"{label:9} {item}")
            if result.verdict == "differs":
                return 2
            return 1 if args.require_identical and result.verdict != "identical" else 0
        if args.cmd == "recipe":
            sys.stdout.write(recipe(args.ref, args.fmt, args.prefix, args.output))
            return 0
        if args.cmd == "epoch":
            print(source_date_epoch(args.ref, Path(args.repo)))
            return 0
    except ReproError as exc:
        print(f"repro-archive: {exc}", file=sys.stderr)
        return 2
    return 0  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
