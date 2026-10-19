# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""A project's own body-field parser: detection, confirmation, and every refusal to load it.

The parser is code from the tracker's repository, run outside the sandbox
through vetted operations, so each check that guards its loading has a test:
the descriptor names it, its path stays in the override directory with no
``..`` and no symlink, and its hash matches the descriptor and the one the
user confirmed on their terminal. Every failure stops the command with exit 2 and never falls back to the
default parser. All report text here is synthetic.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from magpie_local_tracker import cli, custom_parser, main
from magpie_local_tracker.descriptor import DESCRIPTOR_NAME

TEMPLATE = Path(__file__).resolve().parents[2] / "body-field-contract" / "formats" / "_template.py"
PARSER = ".apache-magpie-overrides/tools/local-tracker/parsers/key-value.py"
FRONT = "---\ntitle: Synthetic report {n}\nstate: open\n---\n\n"
BODY = "Summary: A synthetic summary {n}.\nAffected versions: 1.0 to 1.{n}\nSeverity: Low\n"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def run(capsys: pytest.CaptureFixture[str], root: Path, *args: str) -> tuple[int, Any, str]:
    code = main(["--root", str(root), *args])
    captured = capsys.readouterr()
    out = captured.out
    return code, (json.loads(out) if out.strip().startswith("{") else out), captured.err


def _git(top: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=top, check=True, capture_output=True, text=True).stdout


@pytest.fixture(autouse=True)
def user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A home of its own, and a user who answers yes on the terminal; the questions asked are kept."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    asked: list[str] = []

    def answer_yes(question: str) -> bool:
        asked.append(question)
        return True

    monkeypatch.setattr(cli, "_confirm_on_terminal", answer_yes)
    return asked


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path]:
    """A Git working copy holding a tracker whose two reports use `Name: value` lines."""
    if not TEMPLATE.is_file():
        pytest.skip(f"source tree absent: {TEMPLATE}")
    top = tmp_path / "wc"
    top.mkdir()
    _git(top, "init", "-q")
    root = top / "security"
    for n in (1, 2):
        folder = root / f"SEC-{n:04d}"
        folder.mkdir(parents=True)
        (folder / "issue.md").write_text(FRONT.format(n=n) + BODY.format(n=n), encoding="utf-8")
    return top, root


def _detect_and_write(capsys: pytest.CaptureFixture[str], root: Path) -> dict[str, Any]:
    code, out, _ = run(capsys, root, "detect", "--write", "--access-restricted")
    assert code == 0
    return out


def _install(top: Path) -> str:
    target = top / PARSER
    target.parent.mkdir(parents=True)
    shutil.copyfile(TEMPLATE, target)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def _trusted(capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]) -> tuple[Path, Path, str]:
    top, root = repo
    _detect_and_write(capsys, root)
    digest = _install(top)
    code, _, err = run(capsys, root, "trust-parser", PARSER, "--sha256", digest)
    assert code == 0, err
    return top, root, digest


def _descriptor(root: Path) -> dict[str, Any]:
    return json.loads((root / DESCRIPTOR_NAME).read_text(encoding="utf-8"))


def _set_descriptor(root: Path, **changes: Any) -> None:
    data = _descriptor(root)
    data.update(changes)
    (root / DESCRIPTOR_NAME).write_text(json.dumps(data), encoding="utf-8")


def _refused(capsys: pytest.CaptureFixture[str], root: Path, why: str) -> None:
    code, out, err = run(capsys, root, "field-get", "SEC-0001", "Severity")
    assert code == 2, (out, err)
    assert why in err and "re-confirm" in err
    assert out == ""  # nothing read, not even through the default parser


# ---------------------------------------------------------------- detection


def test_detect_reports_a_custom_layout_with_field_names_only(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]
) -> None:
    _, root = repo
    out = _detect_and_write(capsys, root)
    layout = out["field_layout"]
    assert layout["layout"] == "custom"
    assert layout["sample_field_names"] == ["Affected versions", "Severity", "Summary"]
    assert "synthetic summary" not in json.dumps(out).lower()  # no report text in the evidence
    assert out["descriptor"]["field_layout"] == "custom"


def test_detect_keeps_the_default_layout_for_field_sections(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    root = tmp_path / "security"
    for n in (1, 2):
        folder = root / f"SEC-{n:04d}"
        folder.mkdir(parents=True)
        (folder / "issue.md").write_text(
            FRONT.format(n=n) + "### Summary\n\nx\n\n### Severity\n\nLow\n", encoding="utf-8"
        )
    code, out, _ = run(capsys, root, "detect")
    assert code == 0
    assert out["field_layout"] == {
        "layout": "default",
        "description": "fields are level-3 heading sections",
        "sample_field_names": ["Severity", "Summary"],
    }


# ---------------------------------------------------------------- confirmation and use


def test_a_custom_layout_without_a_parser_is_refused(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]
) -> None:
    _, root = repo
    _detect_and_write(capsys, root)
    _refused(capsys, root, "names no body_parser")


def test_trust_parser_refuses_a_hash_the_user_did_not_review(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]
) -> None:
    top, root = repo
    _detect_and_write(capsys, root)
    _install(top)
    code, _, err = run(capsys, root, "trust-parser", PARSER, "--sha256", "0" * 64)
    assert code == 2 and "not the reviewed" in err
    assert _descriptor(root)["body_parser"] == {}


def test_a_confirmed_parser_reads_and_writes_fields(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]
) -> None:
    top, root, digest = _trusted(capsys, repo)
    assert _descriptor(root)["body_parser"] == {"path": PARSER, "sha256": digest}
    assert json.loads(custom_parser.trust_file().read_text()) == {os.path.realpath(top): {PARSER: digest}}
    assert run(capsys, root, "field-get", "SEC-0001", "Severity")[1]["value"] == "Low"
    value = top / "value.txt"
    value.write_text("High\n", encoding="utf-8")
    assert run(capsys, root, "field-set", "SEC-0001", "Severity", "--value-file", str(value))[0] == 0
    text = (root / "SEC-0001" / "issue.md").read_text(encoding="utf-8")
    assert text.endswith("Summary: A synthetic summary 1.\nAffected versions: 1.0 to 1.1\nSeverity: High\n")
    code, out, _ = run(capsys, root, "body", "SEC-0001")
    assert code == 0 and "### Severity\n\nHigh\n" in out
    code, out, _ = run(capsys, root, "doctor")
    assert {"name": "custom body parser", "ok": True, "detail": PARSER} in out["checks"]


def test_a_whole_body_write_is_refused_on_a_custom_layout(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]
) -> None:
    top, root, _ = _trusted(capsys, repo)
    body = top / "body.md"
    body.write_text("### Summary\n\nx\n", encoding="utf-8")
    code, _, err = run(capsys, root, "create", "--title", "Synthetic", "--body-file", str(body))
    assert code == 4 and "custom field layout" in err


# ---------------------------------------------------------------- every refusal to load


def test_a_changed_parser_is_refused(capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]) -> None:
    top, root, _ = _trusted(capsys, repo)
    with (top / PARSER).open("a", encoding="utf-8") as handle:
        handle.write("\n# changed after the review\n")
    _refused(capsys, root, "but the descriptor records")


def test_a_descriptor_hash_not_confirmed_here_is_refused(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]
) -> None:
    """Someone commits a new parser together with its hash: the personal layer still holds the old one."""
    top, root, _ = _trusted(capsys, repo)
    with (top / PARSER).open("a", encoding="utf-8") as handle:
        handle.write("\n# changed and re-hashed in the descriptor\n")
    _set_descriptor(
        root, body_parser={"path": PARSER, "sha256": hashlib.sha256((top / PARSER).read_bytes()).hexdigest()}
    )
    _refused(capsys, root, "has not been confirmed on this machine")


def test_a_parser_never_confirmed_on_this_machine_is_refused(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]
) -> None:
    _, root, _ = _trusted(capsys, repo)
    custom_parser.trust_file().unlink()
    _refused(capsys, root, "has not been confirmed on this machine")


@pytest.mark.parametrize(
    "path",
    [
        "../outside.py",
        ".apache-magpie-overrides/tools/local-tracker/parsers/../parsers/key-value.py",
        "/etc/key-value.py",
        ".apache-magpie-overrides/tools/local-tracker/key-value.py",
        ".apache-magpie-overrides/tools/local-tracker/parsers/sub/key-value.py",
        ".apache-magpie-overrides/tools/local-tracker/parsers/key-value.txt",
        ".apache-magpie-overrides\\tools\\local-tracker\\parsers\\key-value.py",
    ],
)
def test_a_path_outside_the_parser_directory_is_refused(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path], path: str
) -> None:
    _, root, digest = _trusted(capsys, repo)
    _set_descriptor(root, body_parser={"path": path, "sha256": digest})
    _refused(capsys, root, "is not a .py file directly in")


def test_a_symlinked_parser_is_refused(capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]) -> None:
    top, root, _ = _trusted(capsys, repo)
    real = top / "elsewhere.py"
    os.replace(top / PARSER, real)
    os.symlink(real, top / PARSER)
    _refused(capsys, root, "is a symlink")


def test_a_symlinked_parser_directory_is_refused(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]
) -> None:
    top, root, _ = _trusted(capsys, repo)
    parsers = (top / PARSER).parent
    moved = top / "moved-parsers"
    os.replace(parsers, moved)
    os.symlink(moved, parsers)
    _refused(capsys, root, "is a symlink")


def test_a_missing_parser_is_refused(capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]) -> None:
    top, root, _ = _trusted(capsys, repo)
    (top / PARSER).unlink()
    _refused(capsys, root, "does not exist")


def test_a_parser_missing_the_interface_is_refused(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]
) -> None:
    top, root = repo
    _detect_and_write(capsys, root)
    target = top / PARSER
    target.parent.mkdir(parents=True)
    target.write_text("FORMAT = 'nothing'\n", encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    code, out, _ = run(capsys, root, "trust-parser", PARSER, "--sha256", digest)
    # Said at once, to the user who confirmed it.
    assert code == 2 and "does not provide" in out["parser_loads"]
    _refused(capsys, root, "does not provide")


def test_trust_parser_records_nothing_without_a_terminal(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An agent's shell has no controlling terminal, so it cannot confirm a parser for the user."""
    monkeypatch.undo()
    monkeypatch.setenv("HOME", str(repo[0].parent / "home"))
    top, root = repo
    _detect_and_write(capsys, root)
    digest = _install(top)
    code, _, err = run(capsys, root, "trust-parser", PARSER, "--sha256", digest)
    assert code == 2 and "was not confirmed" in err
    assert _descriptor(root)["body_parser"] == {}
    assert not custom_parser.trust_file().exists()


def test_trust_parser_asks_about_the_file_and_its_hash(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path], user: list[str]
) -> None:
    _, _, digest = _trusted(capsys, repo)
    assert len(user) == 1 and PARSER in user[0] and digest in user[0]


def test_trust_parser_reports_that_the_parser_loads(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]
) -> None:
    top, root = repo
    _detect_and_write(capsys, root)
    digest = _install(top)
    code, out, _ = run(capsys, root, "trust-parser", PARSER, "--sha256", digest)
    assert code == 0 and out["parser_loads"] is True


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads an unreadable file")
def test_an_unreadable_record_says_the_parser_cannot_be_verified_here(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]
) -> None:
    """The secure setup's sandbox may not read ~/.config/apache-magpie: that is no reason to re-confirm."""
    _, root, _ = _trusted(capsys, repo)
    record_dir = custom_parser.trust_file().parent
    record_dir.chmod(0)
    try:
        code, out, err = run(capsys, root, "field-get", "SEC-0001", "Severity")
        assert code == 2 and out == ""
        assert "cannot be verified" in err and "vetted operations" in err and "re-confirm" not in err
        _, report, _ = run(capsys, root, "doctor")
        (check,) = [c for c in report["checks"] if c["name"] == "custom body parser"]
        assert check["ok"] is False and check["unverifiable_here"] is True
    finally:
        record_dir.chmod(0o700)


@pytest.mark.parametrize("at", ["top", "tracker"])
def test_a_trust_record_committed_with_the_parser_is_ignored(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path], at: str
) -> None:
    """A commit carrying the parser, its descriptor entry and a ``.svn/`` trust record confirms nothing.

    At the tracker folder the committed ``.svn/`` even makes that folder look
    like a Subversion working copy of its own: still the repository's content,
    never the user's confirmation.
    """
    top, root = repo
    _detect_and_write(capsys, root)
    base = top if at == "top" else root
    digest = _install(base)
    _set_descriptor(root, field_layout="custom", body_parser={"path": PARSER, "sha256": digest})
    layer = base / ".svn" / "apache-magpie"
    layer.mkdir(parents=True)
    record = {PARSER: digest, os.path.realpath(base): {PARSER: digest}}
    (layer / "local-tracker-parsers.json").write_text(json.dumps(record), encoding="utf-8")
    (top / ".git" / "apache-magpie").mkdir()
    (top / ".git" / "apache-magpie" / "local-tracker-parsers.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    _refused(capsys, root, "has not been confirmed on this machine")


def test_a_confirmation_belongs_to_one_working_copy(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path], tmp_path: Path
) -> None:
    top, _, _ = _trusted(capsys, repo)
    other = tmp_path / "other"
    shutil.copytree(top, other, symlinks=True)
    _refused(capsys, other / "security", "has not been confirmed on this machine")


def test_an_unknown_field_layout_is_refused(
    capsys: pytest.CaptureFixture[str], repo: tuple[Path, Path]
) -> None:
    _, root = repo
    _detect_and_write(capsys, root)
    _set_descriptor(root, field_layout="guess")
    code, _, err = run(capsys, root, "field-get", "SEC-0001", "Severity")
    assert code == 5 and "field_layout" in err
