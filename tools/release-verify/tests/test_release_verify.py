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
"""Behavioural fixtures for `release-verify`.

Each subcommand is exercised on the pass case and on every failure
class the `release-verify-rc` skill names for its step. The signature
tests use static fixtures (public keys and detached signatures only,
see ``fixtures/gpg/generate.py``) so they need `gpg` but not
`gpg-agent`; one extra test generates a throwaway key in a temporary
GNUPGHOME and is skipped where an agent cannot start.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import release_verify as rv

GPG_FIXTURES = Path(__file__).parent / "fixtures" / "gpg"
SRC = "apache-foo-2.11.0-source-release.tar.gz"
BIN = "apache-foo-2.11.0-bin.tar.gz"
PATTERNS = ["apache-foo-2.11.0-source-release.tar.gz", "apache-foo-2.11.0-bin.tar.gz"]
needs_gpg = pytest.mark.skipif(shutil.which("gpg") is None, reason="gpg not installed")


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> dict:
    rc = rv.main(list(argv))
    out = json.loads(capsys.readouterr().out)
    out["_rc"] = rc
    return out


def write_digests(directory: Path, name: str, kinds: tuple[str, ...] = ("sha512", "sha256")) -> None:
    data = (directory / name).read_bytes()
    for kind in kinds:
        (directory / f"{name}.{kind}").write_text(f"{hashlib.new(kind, data).hexdigest()}  {name}\n")


@pytest.fixture
def staging(tmp_path: Path) -> Path:
    d = tmp_path / "staging"
    d.mkdir()
    for name in (SRC, BIN):
        (d / name).write_bytes(name.encode())
        (d / f"{name}.asc").write_text("sig")
        write_digests(d, name)
    return d


# ---------------------------------------------------------------- inventory


def test_inventory_pass(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "inventory", "--dir", str(staging), "--expect", PATTERNS[0], "--expect", PATTERNS[1], "--digest", "sha512", "--digest", "sha256")
    assert out["status"] == "PASS"
    assert out["found"] == [SRC, BIN]  # config order, not alphabetical
    assert out["missing"] == [] and out["missing_optional"] == [] and out["unexpected"] == []


def test_inventory_missing_is_fail(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (staging / BIN).unlink()
    out = run(capsys, "inventory", "--dir", str(staging), "--expect", PATTERNS[0], "--expect", PATTERNS[1], "--digest", "sha512", "--digest", "sha256")
    assert out["status"] == "FAIL"
    assert out["missing"] == [BIN]


def test_inventory_missing_optional_is_warn(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (staging / BIN).unlink()
    out = run(capsys, "inventory", "--dir", str(staging), "--expect", PATTERNS[0], "--expect-optional", PATTERNS[1], "--digest", "sha512", "--digest", "sha256")
    assert out["status"] == "WARN"
    assert out["missing"] == [] and out["missing_optional"] == [BIN]
    assert out["unexpected"] == []  # the orphaned .asc / digests still belong to an expected pattern


def test_inventory_optional_present_is_found(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "inventory", "--dir", str(staging), "--expect", PATTERNS[0], "--expect-optional", PATTERNS[1], "--digest", "sha512", "--digest", "sha256")
    assert out["status"] == "PASS"
    assert out["found"] == [SRC, BIN] and out["missing_optional"] == []


def test_inventory_unexpected_is_warn(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (staging / "notes.txt").write_text("x")
    (staging / f"{SRC}.md5").write_text("x")
    out = run(capsys, "inventory", "--dir", str(staging), "--expect", "apache-foo-*.tar.gz", "--digest", "sha512", "--digest", "sha256")
    assert out["status"] == "WARN"
    assert out["unexpected"] == ["apache-foo-2.11.0-source-release.tar.gz.md5", "notes.txt"]


def test_inventory_from_listing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    listing = tmp_path / "ls.txt"
    listing.write_text("a.tar.gz\na.tar.gz.asc\nsub/\n")
    out = run(capsys, "inventory", "--listing", str(listing), "--expect", "a.tar.gz", "--expect", "b.zip")
    assert out["status"] == "FAIL" and out["missing"] == ["b.zip"]
    assert out["found"] == ["a.tar.gz"] and out["unexpected"] == []


# ---------------------------------------------------------------- checksums


def test_checksums_pass(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "checksums", "--dir", str(staging), "--expect", PATTERNS[0], "--expect", PATTERNS[1], "--digest", "sha512", "--digest", "sha256")
    assert out["status"] == "PASS"
    assert out["deprecated_md5_present"] is False
    assert [d["classification"] for r in out["results"] for d in r["digests"]] == ["PASS"] * 4
    assert "sha512sum --check 'apache-foo-2.11.0-bin.tar.gz.sha512'" in out["paste_recipe"]


def test_checksums_mismatch_is_fail(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (staging / f"{BIN}.sha512").write_text("0" * 128 + f"  {BIN}\n")
    out = run(capsys, "checksums", "--dir", str(staging), "--expect", PATTERNS[0], "--expect", PATTERNS[1], "--digest", "sha512", "--digest", "sha256")
    assert out["status"] == "FAIL"
    bin_result = next(r for r in out["results"] if r["file"] == BIN)
    assert bin_result["digests"] == [{"type": "sha512", "classification": "MISMATCH"}, {"type": "sha256", "classification": "PASS"}]


def test_checksums_missing_sha512_is_fail(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (staging / f"{SRC}.sha512").unlink()
    out = run(capsys, "checksums", "--dir", str(staging), "--expect", PATTERNS[0], "--digest", "sha256")
    assert out["status"] == "FAIL"
    assert out["results"][0]["digests"][0] == {"type": "sha512", "classification": "MISSING-DIGEST"}


def test_checksums_missing_optional_digest_is_not_checked(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (staging / f"{SRC}.sha256").unlink()
    out = run(capsys, "checksums", "--dir", str(staging), "--expect", PATTERNS[0], "--digest", "sha512", "--digest", "sha256")
    assert out["status"] == "PASS"
    assert out["results"][0]["digests"] == [{"type": "sha512", "classification": "PASS"}]


def test_checksums_present_optional_digest_is_checked(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "checksums", "--dir", str(staging), "--expect", PATTERNS[0])  # sha256 not in the Digest set, but staged
    assert out["status"] == "PASS"
    assert [d["type"] for d in out["results"][0]["digests"]] == ["sha512", "sha256"]


def test_checksums_sha256_mismatch_is_fail(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (staging / f"{SRC}.sha256").write_text("0" * 64 + f"  {SRC}\n")
    out = run(capsys, "checksums", "--dir", str(staging), "--expect", PATTERNS[0], "--digest", "sha512", "--digest", "sha256")
    assert out["status"] == "FAIL"
    assert out["results"][0]["digests"][1] == {"type": "sha256", "classification": "MISMATCH"}


def test_checksums_md5_file_is_warn(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_digests(staging, SRC, ("md5",))
    out = run(capsys, "checksums", "--dir", str(staging), "--expect", PATTERNS[0], "--digest", "sha512")
    assert out["status"] == "WARN"
    assert out["deprecated_md5_present"] is True
    assert {"type": "md5", "classification": "PASS"} in out["results"][0]["digests"]
    assert "md5sum" not in out["paste_recipe"]


def test_checksums_md5_mismatch_is_warn_never_fail(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (staging / f"{SRC}.md5").write_text("0" * 32 + f"  {SRC}\n")
    out = run(capsys, "checksums", "--dir", str(staging), "--expect", PATTERNS[0], "--digest", "sha512")
    assert out["status"] == "WARN"
    md5 = next(d for d in out["results"][0]["digests"] if d["type"] == "md5")
    assert md5["classification"] == "MISMATCH" and "never fails alone" in md5["detail"]


def test_checksums_optional_artefact_is_checked(staging: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (staging / f"{BIN}.sha512").write_text("0" * 128 + f"  {BIN}\n")
    out = run(capsys, "checksums", "--dir", str(staging), "--expect", PATTERNS[0], "--expect-optional", PATTERNS[1])
    assert out["status"] == "FAIL"
    assert [r["file"] for r in out["results"]] == [SRC, BIN]


def test_digest_file_formats() -> None:
    hexd = hashlib.sha512(b"x").hexdigest()
    upper = hexd.upper()
    gpg_style = f"file.tar.gz: {' '.join(upper[i : i + 8] for i in range(0, 64, 8))}\n {' '.join(upper[i : i + 8] for i in range(64, 128, 8))}\n"
    assert rv.parse_digest_file(f"{hexd}  file.tar.gz\n", "sha512") == hexd
    assert rv.parse_digest_file(f"SHA512 (file.tar.gz) = {hexd}\n", "sha512") == hexd
    assert rv.parse_digest_file(gpg_style, "sha512") == hexd
    assert rv.parse_digest_file("garbage", "sha512") is None


# ---------------------------------------------------------------- notice / license


def make_tree(root: Path, notice: str | None = "Apache Foo 2.11.0\nCopyright\n", license_text: str | None = "Apache License\n") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if notice is not None:
        (root / "NOTICE").write_text(notice)
    if license_text is not None:
        (root / "LICENSE").write_text(license_text)
    return root


def test_notice_license_version_only_diff_needs_review(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = make_tree(tmp_path / "rc")
    prev = make_tree(tmp_path / "prev", notice="Apache Foo 2.10.0\nCopyright\n")
    out = run(capsys, "notice-license", "--tree", str(tree), "--previous", str(prev))
    assert out["status"] == "REVIEW"
    assert (out["notice_diff_lines"], out["license_diff_lines"]) == (2, 0)
    assert "-Apache Foo 2.10.0" in out["notice_diff"]


def test_notice_license_no_previous_is_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "notice-license", "--tree", str(make_tree(tmp_path / "rc")))
    assert out["status"] == "PASS"
    assert out["notice_diff_lines"] is None and out["license_diff_lines"] is None


def test_notice_license_identical_is_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "notice-license", "--tree", str(make_tree(tmp_path / "rc")), "--previous", str(make_tree(tmp_path / "p")))
    assert out["status"] == "PASS" and out["notice_diff_lines"] == 0


def test_notice_missing_is_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "notice-license", "--tree", str(make_tree(tmp_path / "rc", notice=None)))
    assert out["status"] == "FAIL"
    assert out["notice_present"] is False and out["license_present"] is True
    assert out["detail"].startswith("NOTICE absent from the root of the current RC artefact (rc)")


# ---------------------------------------------------------------- binaries


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0")


def test_binaries_clean_tree_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = tmp_path / "apache-foo-2.11.0-source-release"
    touch(tree / "src" / "foo.py")
    out = run(capsys, "binaries", "--tree", str(tree), "--accept", "*.class", "--accept", "*.jar")
    assert out["status"] == "PASS"
    assert out["prohibited_found"] == [] and out["expected_binaries"] == []
    assert out["paste_recipe"].startswith("find 'apache-foo-2.11.0-source-release' \\( -type f \\( -name '*.class'")
    assert "-type d -name '__pycache__'" in out["paste_recipe"]


def test_binaries_prohibited_and_accepted(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = tmp_path / "rc"
    touch(tree / "vendor" / "lib.jar")
    touch(tree / "third-party" / "native.so")
    touch(tree / "assets" / "vendor" / "x" / "app.min.js")
    out = run(capsys, "binaries", "--tree", str(tree), "--accept", "third-party/native.so", "--prohibit", "assets/vendor/**/*.min.js")
    assert out["status"] == "FAIL"
    assert out["prohibited_found"] == ["assets/vendor/x/app.min.js", "vendor/lib.jar"]
    assert out["expected_binaries"] == ["third-party/native.so"]
    assert "-path 'rc/assets/vendor/*.min.js'" in out["paste_recipe"]


def test_pyc_and_pycache_are_never_accepted(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = tmp_path / "rc"
    touch(tree / "foo" / "__pycache__" / "core.cpython-312.pyc")
    out = run(capsys, "binaries", "--tree", str(tree), "--accept", "*.pyc", "--accept", "**/__pycache__")
    assert out["status"] == "FAIL"
    assert out["prohibited_found"] == ["foo/__pycache__", "foo/__pycache__/core.cpython-312.pyc"]
    assert out["expected_binaries"] == []


# ---------------------------------------------------------------- symlinks


def test_symlinks_dangling_is_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = tmp_path / "rc"
    touch(tree / "docs" / "real.md")
    os.symlink("real.md", tree / "docs" / "ok.md")
    os.symlink("../stripped/template.md", tree / "docs" / "broken.md")
    out = run(capsys, "symlinks", "--tree", str(tree))
    assert out["status"] == "FAIL"
    assert out["dangling_symlinks"] == ["docs/broken.md"]
    assert out["outside_symlinks"] == []
    assert out["symlinks_present"] == 2


def test_symlink_to_existing_path_outside_archive_is_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = tmp_path / "rc"
    touch(tree / "a.md")
    touch(tmp_path / "outside.md")
    os.symlink("../outside.md", tree / "escape.md")
    os.symlink(str(tmp_path / "outside.md"), tree / "absolute.md")
    os.symlink("escape.md", tree / "chained.md")
    os.symlink(".", tree / "self")
    out = run(capsys, "symlinks", "--tree", str(tree))
    assert out["status"] == "FAIL"
    assert out["dangling_symlinks"] == []
    assert out["outside_symlinks"] == ["absolute.md", "chained.md", "escape.md"]


def test_symlinks_resolving_pass_and_none_skip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = tmp_path / "rc"
    touch(tree / "a.md")
    assert run(capsys, "symlinks", "--tree", str(tree))["status"] == "SKIP"
    os.symlink("a.md", tree / "b.md")
    assert run(capsys, "symlinks", "--tree", str(tree))["status"] == "PASS"


def test_symlinks_validators_are_left_to_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = tmp_path / "rc"
    touch(tree / "a.md")
    out = run(capsys, "symlinks", "--tree", str(tree), "--validator", "make check-links")
    assert out["status"] == "REVIEW"
    assert out["validators_to_run"] == ["make check-links"]
    assert out["paste_recipe"].splitlines() == ["cd 'rc'", rv.SYMLINK_RECIPE, "make check-links"]


def test_symlink_recipe_flags_dangling_and_outside(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = tmp_path / "rc"
    touch(tree / "a.md")
    touch(tmp_path / "outside.md")
    os.symlink("a.md", tree / "ok.md")
    os.symlink("../outside.md", tree / "escape.md")
    os.symlink("gone.md", tree / "broken.md")
    recipe = run(capsys, "symlinks", "--tree", str(tree))["paste_recipe"].splitlines()[1]
    out = subprocess.run(["sh", "-c", recipe], cwd=tree, capture_output=True, text=True, check=True).stdout
    assert sorted(out.splitlines()) == ["dangling: ./broken.md", "outside: ./escape.md"]


# ---------------------------------------------------------------- version


def test_version_consistent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = tmp_path / "rc"
    touch(tree / "x")
    (tree / "setup.cfg").write_text("[metadata]\nname = foo\nversion = 2.11.0\n")
    (tree / "foo").mkdir()
    (tree / "foo" / "__init__.py").write_text('__version__ = "2.11.0"\n')
    out = run(capsys, "version", "--tree", str(tree), "--rc-tag", "2.11.0-rc1", "--manifest", "setup.cfg", "--manifest", "foo/__init__.py")
    assert out["status"] == "PASS"
    assert out["expected_version"] == "2.11.0"
    assert out["results"] == [
        {"file": "setup.cfg", "extracted": "2.11.0", "match": True},
        {"file": "foo/__init__.py", "extracted": "2.11.0", "match": True},
    ]


def test_version_dev_suffix_is_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tree = tmp_path / "rc"
    (tree / "foo").mkdir(parents=True)
    (tree / "foo" / "__init__.py").write_text('__version__ = "2.11.0.dev0"\n')
    out = run(capsys, "version", "--tree", str(tree), "--expected", "2.11.0", "--manifest", "foo/__init__.py", "--manifest", "missing.cfg")
    assert out["status"] == "FAIL"
    assert out["results"][0]["extracted"] == "2.11.0.dev0" and out["results"][0]["match"] is False
    assert out["results"][1]["extracted"] is None


@pytest.mark.parametrize(
    ("name", "content", "expected"),
    [
        ("pyproject.toml", '[project]\nname = "x"\nversion = "1.2.3"\n', "1.2.3"),
        ("Cargo.toml", '[package]\nname = "x"\nversion = "1.2.3"\n', "1.2.3"),
        ("package.json", '{"name": "x", "version": "1.2.3"}', "1.2.3"),
        (
            "pom.xml",
            '<project xmlns="http://maven.apache.org/POM/4.0.0"><parent><version>9</version></parent><version>1.2.3-SNAPSHOT</version></project>',
            "1.2.3-SNAPSHOT",
        ),
        ("gradle.properties", "group=x\nversion=1.2.3\n", "1.2.3"),
        ("Chart.yaml", "apiVersion: v2\nversion: 1.2.3\n", "1.2.3"),
        ("VERSION", "\n1.2.3\n", "1.2.3"),
        ("setup.py", 'setup(\n    name="x",\n    version="1.2.3",\n)\n', "1.2.3"),
    ],
)
def test_manifest_formats(tmp_path: Path, name: str, content: str, expected: str) -> None:
    (tmp_path / name).write_text(content)
    assert rv.extract_version(tmp_path / name) == (expected, None)


def test_unknown_format_needs_pattern(tmp_path: Path) -> None:
    (tmp_path / "meta.txt").write_text("release: 1.2.3\n")
    assert rv.extract_version(tmp_path / "meta.txt")[0] is None
    assert rv.extract_version(tmp_path / "meta.txt", r"release: (\S+)") == ("1.2.3", None)


def test_dynamic_version_is_null(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\ndynamic = ["version"]\n')
    assert rv.extract_version(tmp_path / "pyproject.toml")[0] is None


# ---------------------------------------------------------------- verdict


def test_verdict_order() -> None:
    steps = [{"step": "inventory", "status": "PASS"}, {"step": "checksums", "status": "WARN"}]
    assert rv.verdict(steps, {})["overall"] == "PASS-WITH-WARNINGS"
    assert rv.verdict([*steps, {"step": "signatures", "status": "FAIL"}], {})["overall"] == "FAIL"
    out = rv.verdict([{"step": "inventory", "status": "PASS"}, {"step": "source-tree-integrity", "status": "SKIP"}], {"reproducibility": "SKIP"})
    assert out["overall"] == "PASS"
    assert out["skip_steps"] == ["source-tree-integrity", "reproducibility"]
    assert out["warn_steps"] == [] and out["fail_steps"] == []


def test_verdict_review_needs_resolution_and_fail_is_final() -> None:
    steps = [{"step": "notice-license", "status": "REVIEW"}, {"step": "signatures", "status": "FAIL"}]
    out = rv.verdict(steps[:1], {})
    assert out["overall"] is None and out["unresolved"] == ["notice-license"]
    assert rv.verdict(steps[:1], {"notice-license": "WARN"})["overall"] == "PASS-WITH-WARNINGS"
    out = rv.verdict(steps, {"signatures": "PASS", "notice-license": "PASS"})
    assert out["overall"] == "FAIL"
    assert out["ignored_overrides"] == ["signatures=PASS (tool status FAIL is final)"]


def test_verdict_reads_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "a.json").write_text(json.dumps({"step": "inventory", "status": "PASS"}))
    (tmp_path / "b.json").write_text(json.dumps({"steps": [{"step": "checksums", "status": "PASS"}]}))
    out = run(capsys, "verdict", str(tmp_path / "a.json"), str(tmp_path / "b.json"), "--status", "rat-license-headers=PASS")
    assert out["overall"] == "PASS"
    assert [s["step"] for s in out["step_summary"]] == ["inventory", "checksums", "rat-license-headers"]


def test_bad_status_override_is_error(capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "verdict", "/nonexistent.json", "--status", "x=MAYBE")
    assert out["_rc"] == 2


# ---------------------------------------------------------------- signatures


def gpg_staging(tmp_path: Path) -> Path:
    d = tmp_path / "staging"
    d.mkdir()
    for name in ("artefact.tar.gz", "artefact.tar.gz.asc", "other.tar.gz", "other.tar.gz.asc"):
        shutil.copy(GPG_FIXTURES / name, d / name)
    return d


def fingerprints() -> dict[str, str]:
    return dict(line.split() for line in (GPG_FIXTURES / "FINGERPRINTS").read_text().splitlines())


@needs_gpg
def test_signature_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d = gpg_staging(tmp_path)
    out = run(
        capsys, "signatures", "--dir", str(d), "--expect", "artefact.tar.gz", "--keys", str(GPG_FIXTURES / "KEYS"), "--keys-url", "https://example.org/KEYS"
    )
    assert out["status"] == "PASS"
    assert out["results"] == [
        {"file": "artefact.tar.gz", "sig_file": "artefact.tar.gz.asc", "classification": "PASS", "fingerprint": fingerprints()["rm"], "key_in_keys": True}
    ]
    assert out["paste_recipe"] == "curl -s 'https://example.org/KEYS' | gpg --import\ngpg --verify 'artefact.tar.gz.asc' 'artefact.tar.gz'"


@needs_gpg
def test_tampered_artefact_is_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d = gpg_staging(tmp_path)
    (d / "artefact.tar.gz").write_bytes(b"tampered\n")
    out = run(capsys, "signatures", "--dir", str(d), "--expect", "artefact.tar.gz", "--keys", str(GPG_FIXTURES / "KEYS"))
    assert out["status"] == "FAIL"
    r = out["results"][0]
    assert (r["classification"], r["fingerprint"], r["key_in_keys"]) == ("FAIL", None, False)
    assert r["detail"] == "BAD signature"


@needs_gpg
def test_unknown_key_is_fail_and_known_outsider_is_key_not_in_keys(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d = gpg_staging(tmp_path)
    out = run(capsys, "signatures", "--dir", str(d), "--expect", "other.tar.gz", "--keys", str(GPG_FIXTURES / "KEYS"))
    assert out["status"] == "FAIL"
    assert out["results"][0]["classification"] == "FAIL"
    assert "not in KEYS" in out["results"][0]["detail"]
    out = run(
        capsys, "signatures", "--dir", str(d), "--expect", "other.tar.gz", "--keys", str(GPG_FIXTURES / "KEYS"), "--extra-key", str(GPG_FIXTURES / "OTHER.pub")
    )
    r = out["results"][0]
    assert out["status"] == "FAIL"
    assert (r["classification"], r["fingerprint"], r["key_in_keys"]) == ("KEY-NOT-IN-KEYS", fingerprints()["other"], False)


@needs_gpg
def test_missing_signature_is_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d = gpg_staging(tmp_path)
    (d / "artefact.tar.gz.asc").unlink()
    out = run(capsys, "signatures", "--dir", str(d), "--expect", "artefact.tar.gz", "--keys", str(GPG_FIXTURES / "KEYS"))
    assert out["results"][0]["detail"] == "signature file missing" and out["status"] == "FAIL"


def test_private_key_material_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    keys = tmp_path / "KEYS"
    # Built at runtime so the repository's private-key detector does not flag the fixture.
    block = "PGP " + "PRIVATE KEY BLOCK"
    keys.write_text(f"-----BEGIN {block}-----\nxx\n-----END {block}-----\n")
    out = run(capsys, "signatures", "--dir", str(tmp_path), "--expect", "x", "--keys", str(keys))
    assert out["_rc"] == 2 and "private key" in out["error"]


@needs_gpg
def test_user_keyring_is_never_touched(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "user-gnupg"
    home.mkdir(mode=0o700)
    monkeypatch.setenv("GNUPGHOME", str(home))
    run(capsys, "signatures", "--dir", str(gpg_staging(tmp_path)), "--expect", "artefact.tar.gz", "--keys", str(GPG_FIXTURES / "KEYS"))
    assert list(home.iterdir()) == []


@needs_gpg
def test_freshly_generated_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """End to end with a key gpg made itself; needs a gpg-agent, so skips where one cannot start."""
    gen = Path(os.environ.get("TMPDIR", "/tmp")) / f"rvk-{os.getpid()}"
    gen.mkdir(mode=0o700)
    try:
        base = ["gpg", "--batch", "--homedir", str(gen), "--pinentry-mode", "loopback", "--passphrase", ""]
        made = subprocess.run([*base, "--quick-gen-key", "Throwaway <t@example.org>", "ed25519", "sign", "never"], capture_output=True, check=False)
        if made.returncode != 0:
            pytest.skip(f"cannot generate a key here: {made.stderr.decode().strip().splitlines()[-1:]}")
        d = tmp_path / "staging"
        d.mkdir()
        (d / "a.tar.gz").write_bytes(b"payload")
        subprocess.run([*base, "--armor", "--detach-sign", "--output", str(d / "a.tar.gz.asc"), str(d / "a.tar.gz")], check=True, capture_output=True)
        keys = tmp_path / "KEYS"
        keys.write_bytes(subprocess.run(["gpg", "--homedir", str(gen), "--armor", "--export"], check=True, capture_output=True).stdout)
    finally:
        subprocess.run(["gpgconf", "--homedir", str(gen), "--kill", "all"], capture_output=True, check=False)
        shutil.rmtree(gen, ignore_errors=True)
    out = run(capsys, "signatures", "--dir", str(d), "--expect", "a.tar.gz", "--keys", str(keys))
    assert out["status"] == "PASS"


# ---------------------------------------------------------------- all


@needs_gpg
def test_all_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d = gpg_staging(tmp_path)
    write_digests(d, "artefact.tar.gz", ("sha512",))
    tree = make_tree(tmp_path / "artefact")
    (tree / "VERSION").write_text("2.11.0\n")
    out = run(
        capsys, "all", "--dir", str(d), "--tree", str(tree), "--expect", "artefact.tar.gz", "--keys", str(GPG_FIXTURES / "KEYS"),
        "--rc-tag", "2.11.0-rc1", "--manifest", "VERSION", "--status", "rat-license-headers=PASS", "--status", "reproducibility=SKIP",
    )  # fmt: skip
    statuses = {s["step"]: s["status"] for s in out["steps"]}
    # other.tar.gz / .asc are staged but not expected → inventory WARN
    assert statuses == {
        "inventory": "WARN",
        "signatures": "PASS",
        "checksums": "PASS",
        "notice-license": "PASS",
        "binary-exclusion": "PASS",
        "source-tree-integrity": "SKIP",
        "version-consistency": "PASS",
    }
    assert out["verdict"]["overall"] == "PASS-WITH-WARNINGS"
    assert out["verdict"]["warn_steps"] == ["inventory"]
    assert out["verdict"]["skip_steps"] == ["source-tree-integrity", "reproducibility"]


def test_verdict_includes_jvm_artefacts_in_step_order() -> None:
    steps = [
        {"step": "version-consistency", "status": "PASS"},
        {"step": "jvm-artefacts", "status": "FAIL"},
        {"step": "binary-exclusion", "status": "PASS"},
    ]
    out = rv.verdict(steps, {})
    assert out["overall"] == "FAIL"
    assert out["fail_steps"] == ["jvm-artefacts"]
    assert [s["step"] for s in out["step_summary"]] == ["binary-exclusion", "jvm-artefacts", "version-consistency"]


# --- Security: recipes, local paths and stale signatures ---------------------


def test_recipes_quote_hostile_file_names(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    hostile = "x$(touch pwned)`id`;rm -rf ~.tar.gz"
    (tmp_path / hostile).write_bytes(b"payload")
    (tmp_path / f"{hostile}.sha512").write_text(hashlib.sha512(b"payload").hexdigest() + "  " + hostile + "\n")
    out = run(capsys, "checksums", "--dir", str(tmp_path), "--expect", "x*.tar.gz", "--digest", "sha512")
    line = next(ln for ln in out["paste_recipe"].splitlines() if "sha512sum" in ln)
    assert line == "sha512sum --check " + rv._shq(f"{hostile}.sha512")
    assert "$(" not in line.replace(rv._shq(f"{hostile}.sha512"), "")


def test_binary_and_symlink_recipes_quote_the_directory() -> None:
    assert rv.binary_find_recipe("rc;id", []).startswith("find 'rc;id' ")


def test_local_keys_path_never_reaches_the_recipe() -> None:
    assert rv._shq(Path("/Users/someone/secret/KEYS").name) == "'KEYS'"


def _fake_verify(monkeypatch: pytest.MonkeyPatch, status: list[str], returncode: int = 0) -> None:
    def fake(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
        stdout = "".join(f"[GNUPG:] {line}\n" for line in status)
        return subprocess.CompletedProcess(args, returncode, stdout, "")

    monkeypatch.setattr(rv, "_gpg", fake)


VALIDSIG = "VALIDSIG " + "A" * 40 + " 2026-01-01 1767225600 0 4 0 22 10 00 " + "B" * 40


@pytest.mark.parametrize(
    ("token", "detail"),
    [("REVKEYSIG", "revoked key"), ("EXPKEYSIG", "expired key"), ("EXPSIG", "signature itself has expired")],
)
def test_stale_signature_never_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, token: str, detail: str) -> None:
    artefact = tmp_path / "a.tar.gz"
    artefact.write_bytes(b"x")
    (tmp_path / "a.tar.gz.asc").write_text("sig")
    _fake_verify(monkeypatch, [f"{token} " + "B" * 16 + " Someone", VALIDSIG])
    result = rv.verify_one(tmp_path, artefact, {"B" * 40})
    assert result["classification"] == "FAIL"
    assert detail in result["detail"]


def test_good_signature_still_passes_with_fake_gpg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artefact = tmp_path / "a.tar.gz"
    artefact.write_bytes(b"x")
    (tmp_path / "a.tar.gz.asc").write_text("sig")
    _fake_verify(monkeypatch, ["GOODSIG " + "B" * 16 + " Someone", VALIDSIG])
    assert rv.verify_one(tmp_path, artefact, {"B" * 40})["classification"] == "PASS"


def test_gpg_home_path_is_redacted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "rv-gpg-abc"

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 2, "", f"gpg: keybox '{home}/pubring.kbx' created\n")

    monkeypatch.setattr(rv.shutil, "which", lambda _: "/usr/bin/gpg")
    monkeypatch.setattr(rv.subprocess, "run", fake_run)
    proc = rv._gpg(home, "--list-keys")
    assert str(home) not in proc.stderr
    assert "<gnupghome>/pubring.kbx" in proc.stderr


# ---------------------------------------------------------------- list-keys (release-keys-sync)


FPR = "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD"


def colons(algo: str = "1", bits: str = "4096", curve: str = "", expires: str = "", validity: str = "-") -> str:
    pub = ["pub", validity, bits, algo, "KEYID", "1647302400", expires] + [""] * 9 + [curve, "", "0", ""]
    return "\n".join(
        [
            "tru::1:1791072876:0:3:1:5",
            ":".join(pub),
            f"fpr:::::::::{FPR}:",
            "uid:-::::1647302400::HASH::Brendan Ngan <bngan@apache.org>::::::::::0:",
            "uid:r::::1647302400::HASH::Old Name <old@example.org>::::::::::0:",
            "sub:-:4096:1:SUBID:1647302400::::::e::::::23:",
            "fpr:::::::::FFFF0000FFFF0000FFFF0000FFFF0000FFFF0000:",
        ]
    )


def test_parse_colons_reads_the_primary_key_without_gpg() -> None:
    (key,) = rv.parse_colons(colons())
    assert key == {
        "fingerprint": FPR,
        "validity": "-",
        "algo_id": "1",
        "algorithm": "RSA",
        "bits": 4096,
        "curve": "",
        "created": "2022-03-15",
        "expiry": None,
        "caps": "",
        "uids": ["Brendan Ngan <bngan@apache.org>"],  # the revoked uid is left out
        "subkey_fingerprints": ["FFFF0000FFFF0000FFFF0000FFFF0000FFFF0000"],
        "subkeys": [
            {
                "fingerprint": "FFFF0000FFFF0000FFFF0000FFFF0000FFFF0000",
                "validity": "-",
                "algo_id": "1",
                "algorithm": "RSA",
                "bits": 4096,
                "curve": "",
                "created": "2022-03-15",
                "expiry": None,
                "caps": "e",
            }
        ],
    }


def test_parse_colons_curve_iso_expiry_and_validity() -> None:
    (key,) = rv.parse_colons(colons("22", "255", "ed25519", "20260715T000000", "r"))
    assert (key["algorithm"], key["curve"], key["expiry"], key["validity"]) == ("EdDSA", "ed25519", "2026-07-15", "r")


def test_list_keys_empty_file_lists_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty = tmp_path / "fetched.asc"
    empty.write_text("")
    out = run(capsys, "list-keys", "--file", str(empty))
    assert out["_rc"] == 0 and out["keys"] == [] and out["file"] == "fetched.asc"


def test_list_keys_refuses_private_key_material(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    keys = tmp_path / "KEYS"
    block = "PGP " + "PRIVATE KEY BLOCK"
    keys.write_text(f"-----BEGIN {block}-----\nxx\n-----END {block}-----\n")
    out = run(capsys, "list-keys", "--file", str(keys))
    assert out["_rc"] == 2 and "private key" in out["error"]


@needs_gpg
def test_list_keys_reads_every_key_in_keys(capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "list-keys", "--file", str(GPG_FIXTURES / "KEYS"))
    assert out["_rc"] == 0 and out["file"] == "KEYS"
    assert [k["fingerprint"] for k in out["keys"]] == [fingerprints()["rm"]]
    assert out["keys"][0]["uids"] and out["keys"][0]["algorithm"] == "EdDSA"


@needs_gpg
def test_list_keys_reads_a_fetched_key(capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "list-keys", "--file", str(GPG_FIXTURES / "OTHER.pub"))
    assert [k["fingerprint"] for k in out["keys"]] == [fingerprints()["other"]]


@needs_gpg
def test_list_keys_garbage_file_lists_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Formerly keys-sync's GpgTest: a file that holds no key yields no key, not an error."""
    junk = tmp_path / "junk.asc"
    junk.write_text("not a key\n")
    out = run(capsys, "list-keys", "--file", str(junk))
    assert out["_rc"] == 0 and out["keys"] == [] and out["detail"]


@needs_gpg
def test_list_keys_never_touches_the_user_keyring(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "user-gnupg"
    home.mkdir()
    monkeypatch.setenv("GNUPGHOME", str(home))
    run(capsys, "list-keys", "--file", str(GPG_FIXTURES / "KEYS"))
    assert list(home.iterdir()) == []


# ---------------------------------------------------------------- list-keys: gpg failures are errors, never "no key"
# Ported from keys-sync's test_check_key.py (#1634): the gpg run moved here.

NO_DATA = "[GNUPG:] NODATA 1\n[GNUPG:] IMPORT_RES " + " ".join(["0"] * 15) + "\n"


def _public_key() -> str:
    return (GPG_FIXTURES / "OTHER.pub").read_text(encoding="ascii")


@needs_gpg
def test_list_keys_directory_input_is_an_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "list-keys", "--file", str(tmp_path))
    assert out["_rc"] == 2 and "regular file" in out["error"]


@needs_gpg
@pytest.mark.parametrize(
    "mangle",
    [
        lambda key: key[:160],  # truncated armour
        lambda key: key.split("\n\n", 1)[0] + "\n",  # header only
        lambda key: key + key[:160],  # a second, truncated block
        lambda key: re.sub(r"\n=[A-Za-z0-9+/]{4}\n", "\n=AAAA\n", key),  # a corrupted armour checksum
    ],
)
def test_list_keys_malformed_armoured_public_key_is_an_error(tmp_path: Path, capsys: pytest.CaptureFixture[str], mangle: Any) -> None:
    path = tmp_path / "malformed key.asc"
    path.write_text(mangle(_public_key()), encoding="ascii")
    out = run(capsys, "list-keys", "--file", str(path))
    assert out["_rc"] == 2 and "gpg --import failed (exit 2)" in out["error"]


@needs_gpg
def test_list_keys_unicode_text_imports_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "not a key.asc"
    path.write_text("这不是公钥\n", encoding="utf-8")
    out = run(capsys, "list-keys", "--file", str(path))
    assert out["_rc"] == 0 and out["keys"] == []


@needs_gpg
def test_list_keys_reads_a_binary_public_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    body = _public_key().split("\n\n", 1)[1].split("\n=", 1)[0]
    path = tmp_path / "public key.gpg"
    path.write_bytes(base64.b64decode(body))
    out = run(capsys, "list-keys", "--file", str(path))
    assert [k["fingerprint"] for k in out["keys"]] == [fingerprints()["other"]]


@needs_gpg
def test_list_keys_reports_capabilities_and_subkeys(capsys: pytest.CaptureFixture[str]) -> None:
    (key,) = run(capsys, "list-keys", "--file", str(GPG_FIXTURES / "OTHER.pub"))["keys"]
    assert key["caps"] and all(set(s) >= {"fingerprint", "caps", "algorithm"} for s in key["subkeys"])
    assert [s["fingerprint"] for s in key["subkeys"]] == key["subkey_fingerprints"]


@needs_gpg
def test_list_keys_imports_the_bytes_read_before_the_file_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "public key.asc"
    path.write_text(_public_key(), encoding="ascii")
    real = rv._gpg

    def swap(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if "--import" in args:
            path.write_text("not a key\n", encoding="utf-8")
        return real(home, *args)

    monkeypatch.setattr(rv, "_gpg", swap)
    assert [k["fingerprint"] for k in rv.list_keys(str(path))["keys"]] == [fingerprints()["other"]]


def test_parse_colons_reads_signing_subkeys() -> None:
    text = "\n".join(
        [
            "pub:-:255:22:KEYID:1647302400::::::cSC:::::ed25519:",
            f"fpr:::::::::{FPR}:",
            "uid:-::::1647302400::HASH::Example RM <rm@example.invalid>::::::::::0:",
            "sub:-:4096:1:SUBID:1647302400::::::s:::::::",
            "fpr:::::::::FFFF0000FFFF0000FFFF0000FFFF0000FFFF0000:",
        ]
    )
    (key,) = rv.parse_colons(text)
    assert (key["fingerprint"], key["caps"]) == (FPR, "cSC")
    assert [(s["fingerprint"], s["caps"], s["bits"]) for s in key["subkeys"]] == [("FFFF0000FFFF0000FFFF0000FFFF0000FFFF0000", "s", 4096)]


class _FakeGpg:
    """Stands in for `_gpg`, answering each call with the next scripted result."""

    def __init__(self, *results: subprocess.CompletedProcess[str] | OSError) -> None:
        self.results = list(results)
        self.homes: list[Path] = []

    def __call__(self, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
        self.homes.append(home)
        result = self.results.pop(0)
        if isinstance(result, OSError):
            raise result
        return result


def _done(code: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, stdout, stderr)


@pytest.fixture
def junk(tmp_path: Path) -> Path:
    path = tmp_path / "public key.asc"
    path.write_text("not a key\n", encoding="utf-8")
    return path


def _list(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], path: Path, *results: subprocess.CompletedProcess[str] | OSError
) -> tuple[dict, _FakeGpg]:
    fake = _FakeGpg(*results)
    monkeypatch.setattr(rv, "_gpg", fake)
    out = run(capsys, "list-keys", "--file", str(path))
    for home in fake.homes:
        assert not home.exists(), f"temporary keyring survived: {home}"
    return out, fake


def _assert_error(out: dict, stage: str) -> None:
    assert out["_rc"] == 2 and set(out) == {"error", "_rc"} and f"gpg {stage}" in out["error"]


def test_list_keys_import_failure_is_not_hidden_by_an_empty_keyring(junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    out, fake = _list(monkeypatch, capsys, junk, _done(2, stderr="permission denied"), _done(0))
    _assert_error(out, "--import")
    assert "exit 2" in out["error"] and "permission denied" in out["error"]
    assert len(fake.results) == 1  # the listing never ran


def test_list_keys_listing_failure_discards_partial_output(junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    out, _ = _list(monkeypatch, capsys, junk, _done(0), _done(2, colons(), "cannot read keyring"))
    _assert_error(out, "--list-keys")
    assert "cannot read keyring" in out["error"]


@pytest.mark.parametrize("suffix", ["", "[GNUPG:] FAILURE gpg-exit 33554433\n"])
def test_list_keys_only_no_data_is_no_key(junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], suffix: str) -> None:
    out, fake = _list(monkeypatch, capsys, junk, _done(2, NO_DATA + suffix), _done(0, "tru::1:0:0:\n"))
    assert out["_rc"] == 0 and out["keys"] == [] and not fake.results


@pytest.mark.parametrize(
    "status",
    [
        "ERROR add_keyblock_resource 33587281",
        "IMPORT_PROBLEM 4",
        f"IMPORT_OK 1 {FPR}",
        "IMPORTED KEYID Test key",
        "FAILURE import 33554433",
        "FAILURE gpg-exit 33554445",
    ],
)
def test_list_keys_no_data_never_hides_another_failure(junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], status: str) -> None:
    out, _ = _list(monkeypatch, capsys, junk, _done(2, NO_DATA + f"[GNUPG:] {status}\n"))
    _assert_error(out, "--import")


@pytest.mark.parametrize(
    "summary",
    [
        "",
        "[GNUPG:] IMPORT_RES 0 0\n",
        "[GNUPG:] IMPORT_RES " + " ".join(["0"] * 14 + ["1"]) + "\n",
        "[GNUPG:] IMPORT_RES " + " ".join(["0"] * 14 + ["unknown"]) + "\n",
    ],
)
def test_list_keys_no_data_needs_a_complete_zero_import_summary(
    junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], summary: str
) -> None:
    out, _ = _list(monkeypatch, capsys, junk, _done(2, "[GNUPG:] NODATA 1\n" + summary))
    _assert_error(out, "--import")


@pytest.mark.parametrize("status", ["", "[GNUPG:] IMPORT_RES " + " ".join(["0"] * 15), "[GNUPG:] NODATA 99\n" + NO_DATA])
def test_list_keys_unrecognised_or_missing_no_data_is_an_error(
    junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], status: str
) -> None:
    out, _ = _list(monkeypatch, capsys, junk, _done(2, status))
    _assert_error(out, "--import")


def test_list_keys_no_data_still_needs_a_successful_listing(junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    out, _ = _list(monkeypatch, capsys, junk, _done(2, NO_DATA), _done(2, stderr="keyring unavailable"))
    _assert_error(out, "--list-keys")


def test_list_keys_no_data_with_a_listed_key_is_an_import_error(junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    out, _ = _list(monkeypatch, capsys, junk, _done(2, NO_DATA), _done(0, colons()))
    _assert_error(out, "--import")


@pytest.mark.parametrize("code", [1, -9, 127])
def test_list_keys_other_exit_codes_are_never_no_data(junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], code: int) -> None:
    out, _ = _list(monkeypatch, capsys, junk, _done(code, NO_DATA))
    _assert_error(out, "--import")
    assert f"exit {code}" in out["error"]


def test_list_keys_error_falls_back_to_status_output(junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    out, _ = _list(monkeypatch, capsys, junk, _done(2, "[GNUPG:] ERROR keydb_search 33554445\n"))
    _assert_error(out, "--import")
    assert "ERROR keydb_search 33554445" in out["error"]


def test_list_keys_error_without_diagnostics_names_stage_and_exit(junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    out, _ = _list(monkeypatch, capsys, junk, _done(2))
    _assert_error(out, "--import")
    assert "exit 2" in out["error"] and "no diagnostic output" in out["error"]


@pytest.mark.parametrize("stage", ["--import", "--list-keys"])
def test_list_keys_spawn_errors_name_the_stage(junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], stage: str) -> None:
    results = (OSError("could not start"),) if stage == "--import" else (_done(0), OSError("could not start"))
    out, _ = _list(monkeypatch, capsys, junk, *results)
    _assert_error(out, stage)
    assert "could not start" in out["error"]


def test_list_keys_no_data_does_not_hide_a_declared_public_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "truncated.asc"
    path.write_text("-----BEGIN PGP PUBLIC KEY BLOCK-----\n\nmQENBGoz\n", encoding="ascii")
    out, fake = _list(monkeypatch, capsys, path, _done(2, NO_DATA), _done(0))
    _assert_error(out, "--import")
    assert len(fake.results) == 1


def test_list_keys_read_error_is_reported_before_gpg(junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(Path, "read_bytes", lambda self: (_ for _ in ()).throw(PermissionError("permission denied")))
    out, fake = _list(monkeypatch, capsys, junk, _done(0), _done(0, colons()))
    assert out["_rc"] == 2 and "--file" in out["error"] and "permission denied" in out["error"]
    assert len(fake.results) == 2


def test_list_keys_directory_is_rejected_before_gpg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    out, fake = _list(monkeypatch, capsys, tmp_path, _done(2, NO_DATA), _done(0))
    assert out["_rc"] == 2 and "regular file" in out["error"] and len(fake.results) == 2


def test_gpg_non_utf8_diagnostics_do_not_hide_the_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rv.shutil, "which", lambda _: sys.executable)
    real_run = subprocess.run

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        script = "import sys; sys.stderr.buffer.write(b'failure: \\xff'); sys.exit(2)"
        return real_run([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(rv.subprocess, "run", fake_run)
    proc = rv._gpg(tmp_path, "--import")
    assert proc.returncode == 2 and "�" in proc.stderr
    assert "failure:" in str(rv._gpg_failure("--import", proc))


def test_list_keys_empty_input_does_not_need_gpg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    empty = tmp_path / "fetched.asc"
    empty.write_bytes(b"")
    out, fake = _list(monkeypatch, capsys, empty)
    assert out["_rc"] == 0 and out["keys"] == [] and fake.homes == []


def test_list_keys_gpg_unavailable_is_an_error(junk: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(rv.shutil, "which", lambda _: None)
    out = run(capsys, "list-keys", "--file", str(junk))
    assert out["_rc"] == 2 and set(out) == {"error", "_rc"} and "gpg not found" in out["error"]


_GPG = shutil.which("gpg")
_MSYS_GPG = sys.platform == "win32" and _GPG is not None and Path(_GPG).with_name("msys-2.0.dll").is_file()


@pytest.mark.skipif(not _MSYS_GPG, reason="requires Windows and Git/MSYS gpg")
def test_list_keys_incompatible_homedir_is_an_error_not_a_missing_key(capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "list-keys", "--file", str(GPG_FIXTURES / "OTHER.pub"))
    assert out["_rc"] == 2 and "gpg --import failed (exit 2)" in out["error"]
