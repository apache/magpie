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
"""Behavioural fixtures for `repro-archive`.

Each reproducible-builds.org archive rule has a positive case (the
builder applies it) and a negative case (`check` catches an archive
that violates it). `compare` is exercised on its three verdicts, and
`build` is shown to be a function of the tag alone: two builds at
different wall-clock times, with a different umask, are byte-identical,
and `.gitattributes` `export-ignore` decides what is left out.
"""

from __future__ import annotations

import gzip
import io
import os
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path

import pytest

import reproducible_archive as ra

EPOCH = 1_700_000_000


def _git(repo: Path, *args: str) -> str:
    """Run git with a hermetic identity and config: no global/system
    config (a developer's `commit.gpgsign` must not reach the fixture)
    and a fixed committer date so the expected epoch is known."""
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_DATE": f"@{EPOCH} +0000",
        "GIT_AUTHOR_DATE": f"@{EPOCH} +0000",
    }
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=env).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    (r / "src").mkdir()
    (r / "src" / "b.txt").write_text("bee\n")
    (r / "src" / "a.txt").write_text("ay\n")
    (r / "z-first").mkdir()
    (r / "z-first" / "x").write_text("x\n")
    (r / "run.sh").write_text("#!/bin/sh\n")
    (r / "run.sh").chmod(0o755)
    (r / "LICENSE").write_text("Apache-2.0\n")
    (r / ".ci.yml").write_text("ci: true\n")
    (r / ".gitattributes").write_text("/.ci.yml export-ignore\n/.gitattributes export-ignore\n")
    os.symlink("src/a.txt", r / "link")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "init")
    _git(r, "tag", "1.0.0-rc1")
    return r


def _names(data: bytes) -> list[str]:
    entries = ra.read_zip_entries(data) if zipfile.is_zipfile(io.BytesIO(data)) else ra.read_tar_entries(data)
    return [e.name for e in entries]


# ---------------------------------------------------------------- build is a function of the tag


@pytest.mark.parametrize("fmt", ra.FORMATS)
def test_build_is_byte_identical_across_time_and_umask(repo: Path, fmt: str) -> None:
    first, epoch1 = ra.build("1.0.0-rc1", repo, fmt, "proj-1.0.0")
    old = os.umask(0o077)
    try:
        time.sleep(0.01)
        second, epoch2 = ra.build("1.0.0-rc1", repo, fmt, "proj-1.0.0")
    finally:
        os.umask(old)
    assert epoch1 == epoch2 == EPOCH
    assert first == second


def test_epoch_defaults_to_committer_timestamp_and_env_overrides(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert ra.source_date_epoch("1.0.0-rc1", repo) == EPOCH
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1600000000")
    assert ra.source_date_epoch("1.0.0-rc1", repo) == 1_600_000_000
    assert ra.source_date_epoch("1.0.0-rc1", repo, override=42) == 42
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "not-a-number")
    with pytest.raises(ra.ReproError):
        ra.source_date_epoch("1.0.0-rc1", repo)


@pytest.mark.parametrize("fmt", ra.FORMATS)
def test_export_ignore_and_prefix_are_honoured(repo: Path, fmt: str) -> None:
    data, _ = ra.build("1.0.0-rc1", repo, fmt, "proj-1.0.0")
    names = _names(data)
    assert all(n.startswith("proj-1.0.0/") for n in names)
    assert "proj-1.0.0/.ci.yml" not in names
    assert "proj-1.0.0/.gitattributes" not in names
    assert "proj-1.0.0/LICENSE" in names
    assert "proj-1.0.0/link" in names


def test_worktree_attributes_preview_an_uncommitted_export_ignore(repo: Path) -> None:
    (repo / ".gitattributes").write_text("/.ci.yml export-ignore\n/.gitattributes export-ignore\n/LICENSE export-ignore\n")
    committed, _ = ra.build("HEAD", repo, "tar.gz", "p")
    preview, _ = ra.build("HEAD", repo, "tar.gz", "p", worktree_attributes=True)
    assert "p/LICENSE" in _names(committed)  # the ref's attributes still apply to a release build
    assert "p/LICENSE" not in _names(preview)  # the working-tree edit is only a preview


def test_untracked_files_never_ship(repo: Path) -> None:
    (repo / "src" / "__pycache__").mkdir()
    (repo / "src" / "__pycache__" / "a.cpython-313.pyc").write_bytes(b"\0")
    data, _ = ra.build("1.0.0-rc1", repo, "tar.gz", "p")
    assert not any("__pycache__" in n for n in _names(data))


# ---------------------------------------------------------------- each reproducible-builds.org rule


def test_tar_gz_applies_every_rule(repo: Path) -> None:
    data, _ = ra.build("1.0.0-rc1", repo, "tar.gz", "p")
    # 6. gzip -n: mtime 0, no FNAME flag.
    assert data[:2] == b"\x1f\x8b" and data[4:8] == b"\0\0\0\0" and not data[3] & 0x08
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(data)), mode="r:") as tf:
        members = tf.getmembers()
    names = [m.name for m in members]
    # 2. ordering: per-directory byte order — `p/src` and its children before `p/z-first`,
    #    `p/LICENSE` (uppercase) before `p/link` (lowercase), `a.txt` before `b.txt`.
    assert names.index("p/LICENSE") < names.index("p/link")
    assert names.index("p/src/a.txt") < names.index("p/src/b.txt") < names.index("p/z-first")
    for m in members:
        assert m.mtime == EPOCH  # 1. one mtime
        assert (m.uid, m.gid, m.uname, m.gname) == (0, 0, "", "")  # 3. ownership
        assert not set(m.pax_headers) & set(ra._PAX_TIME_KEYS)  # 5. no atime/ctime
    by_name = {m.name: m for m in members}
    assert by_name["p/run.sh"].mode == 0o755  # 4. a=rX,u+w keeps the executable bit
    assert by_name["p/LICENSE"].mode == 0o644
    assert by_name["p/src"].mode == 0o755 and by_name["p/src"].isdir()
    assert by_name["p/link"].issym() and by_name["p/link"].linkname == "src/a.txt"
    assert all(r.status != "FAIL" for r in ra.check_tar(data, EPOCH))


def test_zip_applies_every_rule(repo: Path) -> None:
    data, _ = ra.build("1.0.0-rc1", repo, "zip", "p")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        infos = zf.infolist()
        assert zf.comment == ra.commit_of("1.0.0-rc1", repo).encode()  # provenance, as git archive writes it
        link = zf.read("p/link")
    assert link == b"src/a.txt"
    for info in infos:
        assert info.extra == b"" and info.comment == b""  # 7. zip -X
        assert info.date_time == ra._dos_time(EPOCH)  # 1. UTC timestamp from the epoch
        assert info.create_system == 3
    modes = {i.filename: (i.external_attr >> 16) & 0o7777 for i in infos}
    assert modes["p/run.sh"] == 0o755 and modes["p/LICENSE"] == 0o644 and modes["p/src/"] == 0o755
    assert all(r.status != "FAIL" for r in ra.check_zip(data, EPOCH))


def test_zip_rejects_pre_1980_epoch(repo: Path) -> None:
    with pytest.raises(ra.ReproError, match="1980"):
        ra.build("1.0.0-rc1", repo, "zip", "p", epoch=1)


@pytest.mark.parametrize("fmt", ra.FORMATS)
def test_symlink_mode_is_platform_independent(fmt: str) -> None:
    """`lstat` reports a symlink as 0755 on macOS and 0777 on Linux; the
    packed mode, the SWHID and `compare` must not see the difference."""
    base = [ra.Entry("p/", "dir", 0o755), ra.Entry("p/target", "file", 0o644, data=b"x\n")]
    macos = [*base, ra.Entry("p/link", "symlink", 0o755, linkname="target")]
    linux = [*base, ra.Entry("p/link", "symlink", 0o777, linkname="target")]
    write = ra.write_zip if fmt == "zip" else ra.write_tar_gz
    assert write(macos, EPOCH) == write(linux, EPOCH)
    assert ra.swhid_dir_of_entries(macos, "p") == ra.swhid_dir_of_entries(linux, "p")
    packed = ra.read_zip_entries(write(macos, EPOCH)) if fmt == "zip" else ra.read_tar_entries(write(macos, EPOCH))
    assert [e.mode for e in packed if e.kind == "symlink"] == [0o777]


def test_normalize_mode() -> None:
    assert ra.normalize_mode(0o600, "file") == 0o644
    assert ra.normalize_mode(0o700, "file") == 0o755
    assert ra.normalize_mode(0o4755, "file") == 0o755
    assert ra.normalize_mode(0o700, "dir") == 0o755
    assert ra.normalize_mode(0o777, "symlink") == 0o777


def test_sort_order_matches_gnu_tar_sort_name() -> None:
    names = ["a-b/x", "a/", "a/z", "a/b/c", "B", "a/b"]
    ordered = [e.name for e in ra.sort_entries(ra.Entry(n, "file", 0) for n in names)]
    assert ordered == ["B", "a/", "a/b", "a/b/c", "a/z", "a-b/x"]


# ---------------------------------------------------------------- check catches the classic mistakes


def _sloppy_tar_gz(tmp_path: Path) -> Path:
    """What `tar czf` from a working tree produces: wall-clock mtimes,
    the packer's uid, a filename in the gzip header, unsorted members."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tf:
        for name, mtime in (("p/b.txt", 1_700_000_100), ("p/a.txt", 1_700_000_200)):
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.uid, info.gid, info.uname, info.mode = 1, mtime, 1000, 1000, "rm", 0o664
            info.pax_headers = {"atime": "1700000300", "ctime": "1700000300"}
            tf.addfile(info, io.BytesIO(b"x"))
    out = tmp_path / "sloppy.tar.gz"
    with out.open("wb") as fh, gzip.GzipFile(filename="sloppy.tar", mode="wb", fileobj=fh, mtime=1_700_000_400) as gz:
        gz.write(raw.getvalue())
    return out


def test_check_flags_every_rule_violation_in_tar(tmp_path: Path) -> None:
    results = {r.name: r for r in ra.check(_sloppy_tar_gz(tmp_path), EPOCH)}
    assert results["gzip-header"].status == "FAIL" and "filename" in results["gzip-header"].detail
    assert results["file-ordering"].status == "FAIL"
    assert results["modification-times"].status == "FAIL"
    assert results["ownership"].status == "FAIL"
    assert results["permissions"].status == "FAIL"
    assert results["pax-headers"].status == "FAIL"
    assert results["zip-extra-fields"].status == "SKIP"


def test_check_flags_pid_bearing_pax_header_name(tmp_path: Path) -> None:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tf:
        hdr = tarfile.TarInfo("p/PaxHeaders.12345/a.txt")
        hdr.type = tarfile.XHDTYPE
        hdr.size = 0
        tf.addfile(hdr)
        info = tarfile.TarInfo("p/a.txt")
        info.size, info.mtime = 1, EPOCH
        tf.addfile(info, io.BytesIO(b"x"))
    out = tmp_path / "pid.tar"
    out.write_bytes(raw.getvalue())
    results = {r.name: r for r in ra.check(out, EPOCH)}
    assert results["pax-headers"].status == "FAIL" and "PID" in results["pax-headers"].detail
    assert results["gzip-header"].status == "SKIP"


def test_check_flags_zip_extra_fields_and_mixed_timestamps(tmp_path: Path) -> None:
    out = tmp_path / "sloppy.zip"
    with zipfile.ZipFile(out, "w") as zf:
        i1 = zipfile.ZipInfo("p/b.txt", date_time=(2024, 1, 1, 0, 0, 0))
        i1.extra = b"UT\x05\x00\x01\x00\x00\x00\x00"
        i1.create_system = 0
        zf.writestr(i1, b"x")
        i2 = zipfile.ZipInfo("p/a.txt", date_time=(2024, 1, 2, 0, 0, 0))
        i2.external_attr = 0o600 << 16
        zf.writestr(i2, b"y")
    results = {r.name: r for r in ra.check(out, EPOCH)}
    assert results["zip-extra-fields"].status == "FAIL"
    assert results["modification-times"].status == "FAIL"
    assert results["file-ordering"].status == "FAIL"
    assert results["ownership"].status == "FAIL"
    assert results["permissions"].status == "FAIL"
    assert results["pax-headers"].status == "SKIP"


def test_check_passes_for_built_archives_and_epoch_mismatch_fails(repo: Path, tmp_path: Path) -> None:
    for fmt in ra.FORMATS:
        data, _ = ra.build("1.0.0-rc1", repo, fmt, "p")
        out = tmp_path / f"good.{fmt}"
        out.write_bytes(data)
        assert not [r for r in ra.check(out, EPOCH) if r.status == "FAIL"]
        assert [r.name for r in ra.check(out, EPOCH + 2) if r.status == "FAIL"] == ["modification-times"]


# ---------------------------------------------------------------- compare's three verdicts


def test_compare_identical(repo: Path, tmp_path: Path) -> None:
    data, _ = ra.build("1.0.0-rc1", repo, "tar.gz", "p")
    a, b = tmp_path / "a.tar.gz", tmp_path / "b.tar.gz"
    a.write_bytes(data)
    b.write_bytes(data)
    result = ra.compare(a, b)
    assert result.verdict == "identical" and result.sha512_a == result.sha512_b


def test_compare_content_identical_when_only_metadata_differs(repo: Path, tmp_path: Path) -> None:
    good, _ = ra.build("1.0.0-rc1", repo, "tar.gz", "p")
    a = tmp_path / "a.tar.gz"
    a.write_bytes(good)
    # Same members, but packed with wall-clock mtimes and the packer's uid.
    entries = ra.read_tar_entries(good)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as tf:
        for e in reversed(entries):
            info = tarfile.TarInfo(e.name.rstrip("/"))
            info.mtime, info.uid, info.gid, info.mode = 1_800_000_000, 501, 20, e.mode
            if e.kind == "dir":
                info.type = tarfile.DIRTYPE
                tf.addfile(info)
            elif e.kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = e.linkname
                tf.addfile(info)
            else:
                info.size = len(e.data)
                tf.addfile(info, io.BytesIO(e.data))
    b = tmp_path / "b.tar.gz"
    b.write_bytes(raw.getvalue())
    result = ra.compare(a, b)
    assert result.verdict == "content-identical"
    assert not (result.added or result.removed or result.changed)
    assert any("order" in m for m in result.metadata_differences)
    assert any("ownership" in m and "B" in m for m in result.metadata_differences)


def test_compare_differs_across_formats_and_lists_changes(repo: Path, tmp_path: Path) -> None:
    tgz, _ = ra.build("1.0.0-rc1", repo, "tar.gz", "p")
    a = tmp_path / "a.tar.gz"
    a.write_bytes(tgz)
    (repo / "src" / "a.txt").write_text("changed\n")
    (repo / "NEW").write_text("new\n")
    (repo / "z-first" / "x").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "drift")
    zipped, _ = ra.build("HEAD", repo, "zip", "p")
    b = tmp_path / "b.zip"
    b.write_bytes(zipped)
    result = ra.compare(a, b)
    assert result.verdict == "differs"
    assert result.added == ["p/NEW"]
    assert result.removed == ["p/z-first", "p/z-first/x"]  # the now-empty dir goes too
    assert result.changed == ["p/src/a.txt"]


# ---------------------------------------------------------------- recipe + CLI


def test_recipe_carries_every_reproducible_builds_flag() -> None:
    tar_recipe = ra.recipe("1.0.0-rc1", "tar.gz", "p/", "out.tar.gz")
    for needle in (
        "SOURCE_DATE_EPOCH",
        "git archive --format=tar --prefix='p/' '1.0.0-rc1'",
        "touch --no-dereference",
        "--sort=name",
        "--owner=0 --group=0 --numeric-owner",
        "--mode=a=rX,u+w",
        "--pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime",
        "gzip -6 -n",
    ):
        assert needle in tar_recipe
    zip_recipe = ra.recipe("1.0.0-rc1", "zip", "p", "out.zip")
    assert "LC_ALL=C sort" in zip_recipe and "zip -X" in zip_recipe and "TZ=UTC" in zip_recipe
    with pytest.raises(ra.ReproError):
        ra.recipe("x", "7z", "p", "o")


# ---------------------------------------------------------------- SWHID (Software Heritage identifiers)


def _git_write_tree(directory: Path) -> str:
    """git's own tree id of a directory's content — the reference our
    in-memory computation must match."""
    _git(directory, "init", "-q")
    _git(directory, "-c", "core.autocrlf=false", "add", "-A")
    return _git(directory, "write-tree").strip()


def test_swhid_equals_git_tree_when_nothing_is_export_ignored(repo: Path) -> None:
    (repo / ".gitattributes").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "no attributes")
    data, _ = ra.build("HEAD", repo, "tar.gz", "p")
    out = repo.parent / "plain.tar.gz"
    out.write_bytes(data)
    assert ra.swhid_of_archive(out) == "swh:1:dir:" + _git(repo, "rev-parse", "HEAD^{tree}").strip()
    assert ra.swhid_of_archive(out) == ra.swhid_repo_dir("HEAD", repo)


def test_swhid_of_export_ignored_archive_matches_git_over_the_extracted_tree(repo: Path, tmp_path: Path) -> None:
    data, _ = ra.build("1.0.0-rc1", repo, "tar.gz", "p")
    out = tmp_path / "a.tar.gz"
    out.write_bytes(data)
    with tarfile.open(out) as tf:
        tf.extractall(tmp_path / "x", filter="data")
    expected = "swh:1:dir:" + _git_write_tree(tmp_path / "x" / "p")
    assert ra.swhid_of_archive(out) == expected
    # export-ignore stripped .ci.yml, so this is NOT the repository tree
    assert ra.swhid_of_archive(out) != ra.swhid_repo_dir("1.0.0-rc1", repo)


def test_swhid_is_format_independent_and_identical_across_formats(repo: Path, tmp_path: Path) -> None:
    tgz, _ = ra.build("1.0.0-rc1", repo, "tar.gz", "p")
    zipped, _ = ra.build("1.0.0-rc1", repo, "zip", "other-prefix")
    a, b = tmp_path / "a.tar.gz", tmp_path / "b.zip"
    a.write_bytes(tgz)
    b.write_bytes(zipped)
    assert ra.swhid_of_archive(a) == ra.swhid_of_archive(b)  # prefix and container play no part
    result = ra.compare(a, b)
    assert result.verdict == "differs"  # the prefix differs, so the member names do
    assert result.swhid_a == result.swhid_b  # …but the content identifiers agree


def test_swhid_rev_and_qualifiers(repo: Path) -> None:
    rev = ra.swhid_rev("1.0.0-rc1", repo)
    assert rev == "swh:1:rev:" + ra.commit_of("1.0.0-rc1", repo)
    q = ra.qualified_swhid("swh:1:dir:" + "0" * 40, "https://github.com/apache/foo", rev)
    assert q == f"swh:1:dir:{'0' * 40};origin=https://github.com/apache/foo;anchor={rev}"


def test_tar_carries_commit_as_global_pax_comment(repo: Path) -> None:
    data, _ = ra.build("1.0.0-rc1", repo, "tar.gz", "p")
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        assert tf.pax_headers.get("comment") == ra.commit_of("1.0.0-rc1", repo)
    assert not [r for r in ra.check_tar(data, EPOCH) if r.status == "FAIL"]


def test_check_swhid_assertion(repo: Path, tmp_path: Path) -> None:
    data, _ = ra.build("1.0.0-rc1", repo, "zip", "p")
    out = tmp_path / "a.zip"
    out.write_bytes(data)
    good = ra.swhid_of_archive(out)
    assert [r.status for r in ra.check(out, EPOCH, good + ";origin=https://example.org/r") if r.name == "swhid"] == ["PASS"]
    assert [r.status for r in ra.check(out, EPOCH, "swh:1:dir:" + "f" * 40) if r.name == "swhid"] == ["FAIL"]


def test_cli_swhid_and_build_output(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "s.tar.gz"
    assert ra.main(["build", "--ref", "1.0.0-rc1", "--repo", str(repo), "--prefix", "p", "-o", str(out), "--origin", "https://github.com/apache/foo"]) == 0
    stdout = capsys.readouterr().out
    assert "swhid_rev swh:1:rev:" in stdout and ";origin=https://github.com/apache/foo" in stdout
    assert "swhid_dir swh:1:dir:" in stdout and ";anchor=swh:1:rev:" in stdout
    assert "swhid_dir_note differs from the repository tree" in stdout  # .ci.yml is export-ignored
    assert ra.main(["swhid", str(out), "--ref", "1.0.0-rc1", "--repo", str(repo)]) == 0
    stdout = capsys.readouterr().out
    assert "swhid_rev " in stdout and "swhid_repo_dir " in stdout and "swhid_dir " in stdout
    assert ra.main(["swhid"]) == 2


def test_cli_round_trip(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "proj-1.0.0-source.tar.gz"
    assert ra.main(["build", "--ref", "1.0.0-rc1", "--repo", str(repo), "--prefix", "proj-1.0.0", "-o", str(out)]) == 0
    stdout = capsys.readouterr().out
    assert f"SOURCE_DATE_EPOCH {EPOCH}" in stdout and "sha512 " in stdout
    assert ra.main(["check", str(out), "--epoch", str(EPOCH), "--json"]) == 0
    assert ra.main(["compare", str(out), str(out), "--require-identical"]) == 0
    assert ra.main(["epoch", "--ref", "1.0.0-rc1", "--repo", str(repo)]) == 0
    assert capsys.readouterr().out.strip().endswith(str(EPOCH))
    assert ra.main(["check", str(_sloppy_tar_gz(tmp_path))]) == 1
    assert ra.main(["build", "--ref", "nope", "--repo", str(repo), "--prefix", "p", "-o", str(tmp_path / "x")]) == 2
    assert "repro-archive:" in capsys.readouterr().err
