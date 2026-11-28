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
"""Open a scanner's passphrase-encrypted findings archive into a private folder, safely.

The Anthropic OSS Scanner attaches a `*-findings.tar.gz.gpg` (OpenPGP
symmetric encryption, passphrase in the mail) holding each finding's full
`REPORT.md`, its reproducer and its candidate patches. Everything in it is
external content: this module decrypts and unpacks it for reading, and never
runs, builds or applies anything from it.

- `open_archive` checks the OpenPGP framing (symmetric session keys, then one
  encrypted-data packet, nothing else), decrypts with the `gpg` binary under
  a throwaway `GNUPGHOME` in the temporary directory — the passphrase on a
  pipe (`--passphrase-fd 0`), never on a command line — and requires gpg's
  `DECRYPTION_OKAY` status, so a wrong passphrase or a modified file stops
  here. The plaintext is capped while it streams, then unpacked with
  `tarfile`'s `data` filter into a fresh directory after every member was
  checked: only regular files and directories, no absolute path, no `..`, a
  member count and total size under their caps.
- `discard_archive` deletes such a folder, and only such a folder.
"""

from __future__ import annotations

import lzma
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import threading
import zlib
from pathlib import Path, PurePosixPath
from typing import Any

from security_management.issue_import_from_scan.oss_scanner import openpgp_framing

# The decrypted tarball (compressed) and the unpacked tree: a real archive is a few megabytes.
MAX_DECRYPTED_BYTES = 256 * 1024 * 1024
MAX_EXTRACTED_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 20_000
GPG_TIMEOUT_SECONDS = 300
# Written at the folder's root, so `discard_archive` deletes only what `open_archive` made.
MARKER = ".magpie-scan-archive"
_SESSION_KEY_TAGS = frozenset({1, 3})  # PKESK, SKESK
_CHUNK = 1 << 16
# Extended tar headers (PAX records, GNU long names) are read whole into memory
# before a member is returned, so each one, and all of them together, are capped.
MAX_EXTENDED_HEADER_BYTES = 64 * 1024
MAX_EXTENDED_HEADERS_TOTAL = 1024 * 1024
_EXTENDED_TYPES = frozenset(
    {
        tarfile.XHDTYPE,
        tarfile.XGLTYPE,
        tarfile.SOLARIS_XHDTYPE,
        tarfile.GNUTYPE_LONGNAME,
        tarfile.GNUTYPE_LONGLINK,
    }
)
# The archive's top-level folders, as `attach_archive` reads them.
_SECTIONS = frozenset({"critical", "high", "medium", "low", "bugs-not-security"})


class ArchiveError(ValueError):
    """The archive was refused; the message says why and never quotes archive content."""


def _read_passphrase(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ArchiveError(f"{path}: the passphrase file must be a regular file")
    lines = path.read_bytes().splitlines()
    if len(lines) != 1 or not lines[0].strip():
        raise ArchiveError(f"{path}: write the passphrase alone, on one line")
    return lines[0]


def _check_framing(data: bytes) -> None:
    framing = openpgp_framing(data)
    if not framing["intact"]:
        raise ArchiveError(f"not an intact OpenPGP encrypted file: {framing['problem']}")
    tags = framing["packets"]
    if 3 not in tags[:-1] or not set(tags[:-1]) <= _SESSION_KEY_TAGS:
        raise ArchiveError(
            "not a passphrase-encrypted file: expected session-key packets, then one encrypted-data packet"
        )


def _gpg() -> str:
    found = shutil.which("gpg") or shutil.which("gpg2")
    if not found:
        raise ArchiveError("gpg is not installed (or not on PATH)")
    return found


def _decrypt(archive: Path, passphrase: bytes, home: Path, out: Path, max_bytes: int) -> None:
    """Decrypt *archive* to *out*, streaming and capped; gpg's status must say the decryption is good."""
    status_path = home / "status"
    env = {"PATH": os.environ.get("PATH", ""), "LC_ALL": "C", "GNUPGHOME": str(home)}
    argv = [
        _gpg(),
        "--homedir",
        str(home),
        "--batch",
        "--no-tty",
        "--quiet",
        "--no-autostart",
        "--no-symkey-cache",
        "--pinentry-mode",
        "loopback",
        "--passphrase-fd",
        "0",
        "--status-fd",
        "2",
        "--output",
        "-",
        "--decrypt",
        "--",
        str(archive),
    ]
    written = 0
    with status_path.open("wb") as status, out.open("wb") as sink:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=status, env=env)
        timer = threading.Timer(GPG_TIMEOUT_SECONDS, proc.kill)
        timer.start()
        try:
            assert proc.stdin is not None and proc.stdout is not None
            try:
                proc.stdin.write(passphrase + b"\n")
                proc.stdin.close()
            except BrokenPipeError:
                pass  # gpg exited early; its status and exit code below say why
            while chunk := proc.stdout.read(_CHUNK):
                written += len(chunk)
                if written > max_bytes:
                    proc.kill()
                    proc.wait()
                    raise ArchiveError(f"the decrypted archive is over {max_bytes} bytes")
                sink.write(chunk)
            code = proc.wait()
        finally:
            timer.cancel()
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    lines = status_path.read_text(encoding="utf-8", errors="replace").splitlines()
    codes = {line.split()[1] for line in lines if line.startswith("[GNUPG:] ") and len(line.split()) > 1}
    if code == 0 and "DECRYPTION_OKAY" in codes and "DECRYPTION_FAILED" not in codes:
        return
    if "DECRYPTION_FAILED" in codes:
        raise ArchiveError("gpg could not decrypt the archive: wrong passphrase, or a modified file")
    raise ArchiveError(f"gpg could not decrypt the archive (exit {code})")


def _check_member(member: tarfile.TarInfo) -> None:
    name = member.name
    shown = re.sub(r"[^\w./+-]", "_", name)[:120]
    if not name or "\x00" in name or "\\" in name:
        raise ArchiveError(f"archive member {shown!r} has an unusable name")
    if name.startswith("/") or re.match(r"[A-Za-z]:", name):
        raise ArchiveError(f"archive member {shown!r} has an absolute path")
    parts = PurePosixPath(name).parts
    if ".." in parts:
        raise ArchiveError(f"archive member {shown!r} climbs out with '..'")
    if parts and parts[0].casefold() == MARKER.casefold():
        raise ArchiveError(f"archive member {shown!r} takes the name of open-archive's own marker")
    if member.issym() or member.islnk():
        raise ArchiveError(f"archive member {shown!r} is a link")
    if not (member.isreg() or member.isdir()) or member.issparse():
        raise ArchiveError(f"archive member {shown!r} is a device, FIFO or other special file")


class _CappedTarInfo(tarfile.TarInfo):
    """Refuses an extended header over its cap before tarfile reads its payload into memory."""

    def _proc_member(self, tarfile_: tarfile.TarFile) -> tarfile.TarInfo:
        if self.type in _EXTENDED_TYPES:
            if self.size > MAX_EXTENDED_HEADER_BYTES:
                raise ArchiveError(f"the archive has an extended tar header of {self.size} bytes")
            seen = getattr(tarfile_, "_magpie_extended", 0) + self.size
            if seen > MAX_EXTENDED_HEADERS_TOTAL:
                raise ArchiveError(
                    f"the archive's extended tar headers are over {MAX_EXTENDED_HEADERS_TOTAL} bytes"
                )
            tarfile_._magpie_extended = seen  # ty: ignore[missing-attribute]
        return super()._proc_member(tarfile_)  # ty: ignore[missing-attribute]


def _extract(tarball: Path, out_dir: Path, max_bytes: int, max_members: int) -> tuple[int, int]:
    """Check every member first, then unpack with the `data` filter; returns (members, bytes)."""
    if not hasattr(tarfile, "data_filter"):
        raise ArchiveError("this Python has no tarfile extraction filters; use 3.11.4 or later")
    try:
        with tarfile.open(tarball, "r:*", tarinfo=_CappedTarInfo) as tar:
            members: list[tarfile.TarInfo] = []
            total = 0
            while (member := tar.next()) is not None:
                if len(members) >= max_members:
                    raise ArchiveError(f"the archive has more than {max_members} members")
                _check_member(member)
                total += member.size
                if total > max_bytes:
                    raise ArchiveError(f"the archive unpacks to more than {max_bytes} bytes")
                members.append(member)
            tar.extractall(out_dir, members=members, filter="data")
    except (tarfile.TarError, EOFError, OSError, zlib.error, lzma.LZMAError) as exc:
        raise ArchiveError(f"the decrypted file is not a readable tar archive: {type(exc).__name__}") from exc
    return len(members), total


def _make_private(root: Path) -> int:
    """Owner-only, and no execute bit on any file: nothing in the archive is meant to run."""
    files = 0
    for dirpath, dirnames, filenames in root.walk():
        os.chmod(dirpath, 0o700)
        for name in filenames:
            path = dirpath / name
            if stat.S_ISREG(path.lstat().st_mode):
                os.chmod(path, 0o600)
                files += 1
        dirnames[:] = [d for d in dirnames if not (dirpath / d).is_symlink()]
    return files


def _archive_root(out_dir: Path) -> Path:
    """The folder holding the severity sections: descend through lone wrapper directories."""
    root = out_dir
    while True:
        entries = [e for e in root.iterdir() if e.name != MARKER]
        if any(e.name in _SECTIONS for e in entries):
            return root
        if len(entries) == 1 and entries[0].is_dir() and not entries[0].is_symlink():
            root = entries[0]
        else:
            return root


def open_archive(
    archive: Path,
    passphrase_file: Path,
    out_dir: Path,
    *,
    max_decrypted: int = MAX_DECRYPTED_BYTES,
    max_extracted: int = MAX_EXTRACTED_BYTES,
    max_members: int = MAX_MEMBERS,
) -> dict[str, Any]:
    """Decrypt and unpack *archive* into the new folder *out_dir*; returns what to pass to `--archive-dir`."""
    if archive.is_symlink() or not archive.is_file():
        raise ArchiveError(f"{archive}: not a regular file")
    if out_dir.exists() or out_dir.is_symlink():
        raise ArchiveError(f"{out_dir} already exists: name a new folder")
    # The ciphertext is at most a little larger than the plaintext it may decrypt to.
    if archive.stat().st_size > max_decrypted:
        raise ArchiveError(f"the encrypted archive is over {max_decrypted} bytes")
    _check_framing(archive.read_bytes())
    passphrase = _read_passphrase(passphrase_file)
    home: Path | None = None
    created = False
    try:
        home = Path(tempfile.mkdtemp(prefix="magpie-gpg-"))
        os.chmod(home, 0o700)
        out_dir.mkdir(mode=0o700, parents=True)
        created = True
        tarball = home / "archive.tar"
        _decrypt(archive.resolve(), passphrase, home, tarball, max_decrypted)
        members, size = _extract(tarball, out_dir, max_extracted, max_members)
        fd = os.open(
            out_dir / MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
        with os.fdopen(fd, "w", encoding="utf-8") as marker:
            marker.write("written by security-management open-archive\n")
        files = _make_private(out_dir) - 1
    except BaseException:
        if created:
            shutil.rmtree(out_dir, ignore_errors=True)
        raise
    finally:
        if home is not None:
            shutil.rmtree(home, ignore_errors=True)
    root = _archive_root(out_dir)
    sections = sorted(e.name for e in root.iterdir() if e.is_dir() and re.fullmatch(r"[\w.-]{1,64}", e.name))
    return {
        "archive_dir": str(root),
        "folder": str(out_dir),
        "members": members,
        "files": files,
        "bytes": size,
        "sections": sections,
    }


def discard_archive(folder: Path) -> dict[str, Any]:
    """Delete a folder `open_archive` wrote; refuses anything without its marker."""
    try:
        marker = (folder / MARKER).lstat()
    except OSError:
        marker = None
    if folder.is_symlink() or not folder.is_dir() or marker is None or not stat.S_ISREG(marker.st_mode):
        raise ArchiveError(f"{folder} was not written by open-archive; not deleting it")
    shutil.rmtree(folder)
    return {"discarded": str(folder)}
