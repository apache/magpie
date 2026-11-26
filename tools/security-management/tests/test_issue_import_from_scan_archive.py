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
"""`issue-import-from-scan open-archive` / `discard-archive`: the scanner's encrypted archive, opened safely.

The decryption tests need the `gpg` binary to build their fixtures; without it
they are skipped, and the checks made before and after gpg are still tested by
handing `_extract` a plain tarball.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main
from security_management.issue_import_from_scan import archive

PASSPHRASE = "correct horse battery staple"
GPG = shutil.which("gpg") or shutil.which("gpg2")
needs_gpg = pytest.mark.skipif(GPG is None, reason="gpg is not installed")


def run(capsys, *argv: str) -> tuple[int, dict[str, Any]]:
    code = main(["issue-import-from-scan", *argv])
    return code, json.loads(capsys.readouterr().out)


def tarball(entries: list[tarfile.TarInfo | tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for entry in entries:
            if isinstance(entry, tarfile.TarInfo):
                tar.addfile(entry)
            else:
                name, data = entry
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o755
                tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def good_tree() -> list[tarfile.TarInfo | tuple[str, bytes]]:
    return [
        ("widget-findings/high/ANT-2026-AAAAAAA1/REPORT.md", b"# Report\n\n## Reproduction\n\nrun it\n"),
        ("widget-findings/high/ANT-2026-AAAAAAA1/repro/poc.sh", b"#!/bin/sh\necho pwned\n"),
        ("widget-findings/high/ANT-2026-AAAAAAA1/patches/1.patch", b"# a\n# fix\ndiff\n"),
    ]


def encrypt(tmp_path: Path, data: bytes, passphrase: str = PASSPHRASE) -> Path:
    """Symmetrically encrypt *data* the way the scanner does; skip when gpg cannot."""
    assert GPG is not None
    plain = tmp_path / "plain.tar.gz"
    plain.write_bytes(data)
    out = tmp_path / "findings.tar.gz.gpg"
    home = Path(tempfile.mkdtemp(prefix="magpie-gpg-test-"))
    try:
        # gpg may exit non-zero only because it could not reach an agent to cache the
        # passphrase (as in a sandbox); the file it wrote is what counts.
        subprocess.run(
            [
                GPG,
                "--homedir",
                str(home),
                "--batch",
                "--no-tty",
                "--quiet",
                "--pinentry-mode",
                "loopback",
                "--passphrase-fd",
                "0",
                "--no-symkey-cache",
                "--yes",
                "--symmetric",
                "--output",
                str(out),
                str(plain),
            ],
            input=passphrase.encode() + b"\n",
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(home, ignore_errors=True)
    if not out.is_file() or not out.stat().st_size:
        pytest.skip("gpg could not encrypt a fixture here")
    return out


def passphrase_file(tmp_path: Path, text: str = PASSPHRASE) -> Path:
    path = tmp_path / "passphrase"
    path.write_text(text + "\n")
    return path


@needs_gpg
def test_open_archive_unpacks_a_private_read_only_tree(capsys, tmp_path) -> None:
    gpg_file = encrypt(tmp_path, tarball(good_tree()))
    out = tmp_path / "opened"
    code, summary = run(
        capsys,
        "open-archive",
        "--archive",
        str(gpg_file),
        "--passphrase-file",
        str(passphrase_file(tmp_path)),
        "--out-dir",
        str(out),
    )
    assert code == 0, summary
    assert summary["archive_dir"] == str(out / "widget-findings")
    assert summary["sections"] == ["high"] and summary["members"] == 3 and summary["files"] == 3
    poc = out / "widget-findings/high/ANT-2026-AAAAAAA1/repro/poc.sh"
    assert poc.read_text() == "#!/bin/sh\necho pwned\n"
    # Owner-only, and nothing executable.
    assert stat.S_IMODE(poc.stat().st_mode) == 0o600
    assert stat.S_IMODE(out.stat().st_mode) == 0o700
    # The passphrase never went on gpg's command line, and the plaintext tarball is gone.
    assert not list(Path(tempfile.gettempdir()).glob("magpie-gpg-*/archive.tar"))
    code, _done = run(capsys, "discard-archive", "--dir", str(out))
    assert code == 0 and not out.exists()


@needs_gpg
def test_wrong_passphrase_is_refused_and_leaves_nothing(capsys, tmp_path) -> None:
    gpg_file = encrypt(tmp_path, tarball(good_tree()))
    out = tmp_path / "opened"
    code, result = run(
        capsys,
        "open-archive",
        "--archive",
        str(gpg_file),
        "--passphrase-file",
        str(passphrase_file(tmp_path, "wrong")),
        "--out-dir",
        str(out),
    )
    assert code == 2 and "wrong passphrase" in result["refused"]
    assert not out.exists()


@needs_gpg
def test_a_modified_ciphertext_is_refused(capsys, tmp_path) -> None:
    gpg_file = encrypt(tmp_path, tarball(good_tree()))
    data = bytearray(gpg_file.read_bytes())
    data[-5] ^= 0xFF
    gpg_file.write_bytes(bytes(data))
    code, result = run(
        capsys,
        "open-archive",
        "--archive",
        str(gpg_file),
        "--passphrase-file",
        str(passphrase_file(tmp_path)),
        "--out-dir",
        str(tmp_path / "o"),
    )
    assert code == 2 and "decrypt" in result["refused"]


@needs_gpg
def test_decrypted_data_that_is_not_a_tarball_is_refused(capsys, tmp_path) -> None:
    gpg_file = encrypt(tmp_path, b"just some text, not a tar archive\n")
    code, result = run(
        capsys,
        "open-archive",
        "--archive",
        str(gpg_file),
        "--passphrase-file",
        str(passphrase_file(tmp_path)),
        "--out-dir",
        str(tmp_path / "o"),
    )
    assert code == 2 and "not a readable tar archive" in result["refused"]


@needs_gpg
def test_decrypted_size_cap_stops_the_stream(tmp_path) -> None:
    # gpg compresses before encrypting: a small ciphertext that decrypts to a megabyte.
    gpg_file = encrypt(tmp_path, b"\0" * 1_000_000)
    assert gpg_file.stat().st_size < 100_000
    with pytest.raises(archive.ArchiveError, match="decrypted archive is over"):
        archive.open_archive(gpg_file, passphrase_file(tmp_path), tmp_path / "o", max_decrypted=100_000)
    assert not (tmp_path / "o").exists()


@pytest.mark.parametrize(
    "data",
    [
        b"this is not OpenPGP at all",
        # A bare literal-data packet: gpg would print it without decrypting anything.
        bytes([0xCB, 0x06]) + b"b\x00ab\x00\x00",
        # Encrypted data with no passphrase (SKESK) packet before it.
        bytes([0xD2, 0x04]) + b"abcd",
    ],
)
def test_input_that_is_not_a_passphrase_encrypted_file_is_refused(capsys, tmp_path, data) -> None:
    path = tmp_path / "findings.tar.gz.gpg"
    path.write_bytes(data)
    code, result = run(
        capsys,
        "open-archive",
        "--archive",
        str(path),
        "--passphrase-file",
        str(passphrase_file(tmp_path)),
        "--out-dir",
        str(tmp_path / "o"),
    )
    assert code == 2 and ("OpenPGP" in result["refused"] or "passphrase-encrypted" in result["refused"])
    assert not (tmp_path / "o").exists()


def test_an_existing_out_dir_is_refused(capsys, tmp_path) -> None:
    (tmp_path / "o").mkdir()
    path = tmp_path / "a.gpg"
    path.write_bytes(bytes([0x8C, 0x02, 0x04, 0x07, 0xD2, 0x04]) + b"abcd")
    code, result = run(
        capsys,
        "open-archive",
        "--archive",
        str(path),
        "--passphrase-file",
        str(passphrase_file(tmp_path)),
        "--out-dir",
        str(tmp_path / "o"),
    )
    assert code == 2 and "already exists" in result["refused"]


@pytest.mark.parametrize("text", ["", "one\ntwo"])
def test_passphrase_file_holds_one_line(tmp_path, text) -> None:
    path = tmp_path / "p"
    path.write_text(text)
    with pytest.raises(archive.ArchiveError, match="one line"):
        archive._read_passphrase(path)


def member(name: str, kind: bytes = tarfile.REGTYPE, link: str = "") -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = link
    return info


@pytest.mark.parametrize(
    ("entry", "problem"),
    [
        (("../escape.txt", b"x"), "'..'"),
        (("high/../../escape.txt", b"x"), "'..'"),
        (("/etc/passwd", b"x"), "absolute"),
        (member("high/link", tarfile.SYMTYPE, "/etc/passwd"), "link"),
        (member("high/hard", tarfile.LNKTYPE, "high/x"), "link"),
        (member("high/dev", tarfile.CHRTYPE), "device"),
        (member("high/fifo", tarfile.FIFOTYPE), "device"),
    ],
)
def test_unsafe_members_refuse_the_whole_archive(tmp_path, entry, problem) -> None:
    plain = tmp_path / "a.tar.gz"
    plain.write_bytes(tarball([("high/ok.txt", b"fine"), entry]))
    out = tmp_path / "o"
    out.mkdir()
    with pytest.raises(archive.ArchiveError, match=problem):
        archive._extract(plain, out, archive.MAX_EXTRACTED_BYTES, archive.MAX_MEMBERS)
    # Nothing is unpacked until every member passed.
    assert list(out.iterdir()) == []
    assert not (tmp_path / "escape.txt").exists()


def test_oversize_and_too_many_members_are_refused(tmp_path) -> None:
    plain = tmp_path / "a.tar.gz"
    plain.write_bytes(tarball([(f"high/{n}.txt", b"x" * 100) for n in range(5)]))
    out = tmp_path / "o"
    out.mkdir()
    with pytest.raises(archive.ArchiveError, match="more than 250 bytes"):
        archive._extract(plain, out, 250, 100)
    with pytest.raises(archive.ArchiveError, match="more than 3 members"):
        archive._extract(plain, out, 10_000, 3)
    assert list(out.iterdir()) == []


def test_a_good_tarball_extracts_under_the_data_filter(tmp_path) -> None:
    plain = tmp_path / "a.tar.gz"
    plain.write_bytes(tarball(good_tree()))
    out = tmp_path / "o"
    out.mkdir()
    assert archive._extract(plain, out, 10_000, 100)[0] == 3
    assert (out / "widget-findings/high/ANT-2026-AAAAAAA1/REPORT.md").is_file()
    assert archive._archive_root(out) == out / "widget-findings"


def test_discard_refuses_a_folder_open_archive_did_not_write(capsys, tmp_path) -> None:
    keep = tmp_path / "keep"
    keep.mkdir()
    (keep / "file").write_text("x")
    code, _result = run(capsys, "discard-archive", "--dir", str(keep))
    assert code == 2 and (keep / "file").exists()
    assert os.path.isdir(keep)


def pax_member(name: str, value_size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.pax_headers = {"comment": "x" * value_size}
    return info


def pax_tarball(entries: list[tarfile.TarInfo]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.PAX_FORMAT) as tar:
        for info in entries:
            tar.addfile(info, io.BytesIO(b""))
    return buffer.getvalue()


def test_an_oversized_extended_header_is_refused_before_it_is_read(tmp_path) -> None:
    plain = tmp_path / "a.tar.gz"
    plain.write_bytes(pax_tarball([pax_member("high/a.txt", archive.MAX_EXTENDED_HEADER_BYTES + 1)]))
    out = tmp_path / "o"
    out.mkdir()
    with pytest.raises(archive.ArchiveError, match="extended tar header of"):
        archive._extract(plain, out, archive.MAX_EXTRACTED_BYTES, archive.MAX_MEMBERS)
    assert list(out.iterdir()) == []


def test_extended_headers_are_capped_in_total(tmp_path) -> None:
    per = archive.MAX_EXTENDED_HEADER_BYTES - 1024
    count = archive.MAX_EXTENDED_HEADERS_TOTAL // per + 2
    plain = tmp_path / "a.tar.gz"
    plain.write_bytes(pax_tarball([pax_member(f"high/{n}.txt", per) for n in range(count)]))
    out = tmp_path / "o"
    out.mkdir()
    with pytest.raises(archive.ArchiveError, match="extended tar headers are over"):
        archive._extract(plain, out, archive.MAX_EXTRACTED_BYTES, archive.MAX_MEMBERS)


def test_tarfile_still_calls_the_header_hook_the_cap_relies_on(tmp_path, monkeypatch) -> None:
    # The extended-header cap overrides tarfile's private `TarInfo._proc_member`.
    # If a Python release renames it or stops calling it, the override is never
    # reached and the cap silently disappears: this test fails first.
    assert "_proc_member" in vars(tarfile.TarInfo), (
        "tarfile.TarInfo no longer defines _proc_member: the extended-header cap in archive.py is not applied"
    )
    calls: list[str] = []
    original = archive._CappedTarInfo._proc_member

    def spy(self, tarfile_):
        calls.append(self.name)
        return original(self, tarfile_)

    monkeypatch.setattr(archive._CappedTarInfo, "_proc_member", spy)
    plain = tmp_path / "a.tar.gz"
    plain.write_bytes(pax_tarball([pax_member("high/a.txt", 100)]))
    out = tmp_path / "o"
    out.mkdir()
    archive._extract(plain, out, 10_000, 100)
    assert calls, "tarfile did not call _CappedTarInfo._proc_member: the extended-header cap is not applied"


def test_an_oversized_gnu_long_name_is_refused(tmp_path) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        tar.addfile(tarfile.TarInfo("high/" + "n" * (archive.MAX_EXTENDED_HEADER_BYTES + 1)), io.BytesIO(b""))
    plain = tmp_path / "a.tar.gz"
    plain.write_bytes(buffer.getvalue())
    out = tmp_path / "o"
    out.mkdir()
    with pytest.raises(archive.ArchiveError, match="extended tar header of"):
        archive._extract(plain, out, archive.MAX_EXTRACTED_BYTES, archive.MAX_MEMBERS)
    assert list(out.iterdir()) == []


def test_a_small_extended_header_is_fine(tmp_path) -> None:
    plain = tmp_path / "a.tar.gz"
    plain.write_bytes(pax_tarball([pax_member("high/a.txt", 100)]))
    out = tmp_path / "o"
    out.mkdir()
    assert archive._extract(plain, out, 10_000, 100)[0] == 1


@pytest.mark.parametrize("suffix", ["gz", "xz"])
def test_a_corrupt_compressed_stream_is_a_clean_refusal(tmp_path, suffix) -> None:
    buffer = io.BytesIO()
    tar = (
        tarfile.open(fileobj=buffer, mode="w:gz")
        if suffix == "gz"
        else tarfile.open(fileobj=buffer, mode="w:xz")
    )
    with tar:
        for n in range(20):
            payload = (f"line {n} of a reproducible payload\n" * 200).encode()
            info = tarfile.TarInfo(f"high/{n}.bin")
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    data = bytearray(buffer.getvalue())
    # Right after the 10-byte gzip header, 0xff is a reserved deflate block type; xz breaks mid-stream.
    middle = 10 if suffix == "gz" else len(data) // 2
    data[middle : middle + 64] = b"\xff" * 64
    plain = tmp_path / "a.tar"
    plain.write_bytes(bytes(data))
    out = tmp_path / "o"
    out.mkdir()
    with pytest.raises(archive.ArchiveError, match="not a readable tar archive"):
        archive._extract(plain, out, archive.MAX_EXTRACTED_BYTES, archive.MAX_MEMBERS)


@pytest.mark.parametrize("name", [archive.MARKER, archive.MARKER.upper(), f"{archive.MARKER}/inner.txt"])
def test_a_member_named_like_the_marker_is_refused(tmp_path, name) -> None:
    plain = tmp_path / "a.tar.gz"
    plain.write_bytes(tarball([(name, b"x")]))
    out = tmp_path / "o"
    out.mkdir()
    with pytest.raises(archive.ArchiveError, match="marker"):
        archive._extract(plain, out, archive.MAX_EXTRACTED_BYTES, archive.MAX_MEMBERS)


def test_an_oversized_encrypted_file_is_refused_before_it_is_read(tmp_path) -> None:
    path = tmp_path / "a.gpg"
    path.write_bytes(bytes([0x8C, 0x02, 0x04, 0x07, 0xD2, 0x04]) + b"abcd")
    with pytest.raises(archive.ArchiveError, match="encrypted archive is over"):
        archive.open_archive(path, passphrase_file(tmp_path), tmp_path / "o", max_decrypted=8)
    assert not (tmp_path / "o").exists()


def test_gpg_exiting_early_is_a_refusal_not_a_broken_pipe(tmp_path, monkeypatch) -> None:
    true = shutil.which("true")
    if true is None:
        pytest.skip("no `true` binary")
    monkeypatch.setattr(archive, "_gpg", lambda: true)
    home = tmp_path / "home"
    home.mkdir()
    archive_file = tmp_path / "a.gpg"
    archive_file.write_bytes(b"x")
    with pytest.raises(archive.ArchiveError, match="could not decrypt"):
        archive._decrypt(archive_file, b"p" * (1 << 20), home, tmp_path / "out.tar", 1000)


def test_no_gnupghome_is_left_when_the_out_dir_cannot_be_made(tmp_path, monkeypatch) -> None:
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    blocker = tmp_path / "file"
    blocker.write_text("not a folder")
    path = tmp_path / "a.gpg"
    path.write_bytes(bytes([0x8C, 0x02, 0x04, 0x07, 0xD2, 0x04]) + b"abcd")
    with pytest.raises(OSError):
        archive.open_archive(path, passphrase_file(tmp_path), blocker / "o")
    assert list(temp.iterdir()) == []


def test_discard_refuses_a_symlinked_marker(capsys, tmp_path) -> None:
    keep = tmp_path / "keep"
    keep.mkdir()
    (keep / "file").write_text("x")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_text("x")
    (keep / archive.MARKER).symlink_to(elsewhere)
    code, _result = run(capsys, "discard-archive", "--dir", str(keep))
    assert code == 2 and (keep / "file").exists()
