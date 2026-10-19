# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""The body-field conformance cases, run through the tracker's store on real Git and SVN storage.

Each case body becomes an issue file in a working copy; reads and writes go
through :class:`Tracker` (the same path ``field-get`` / ``field-set`` take),
the result is committed, and a fresh checkout is read back. Git runs with
``core.autocrlf=true`` and SVN with ``svn:eol-style=native`` and
``svn:keywords``, so the storage rewrites line endings and expands keywords
the way a team's checkout would.

Through the store a value holding a line that would start a field is escaped
(BF-WRITE-1) rather than refused, and a fence it leaves open is closed in the
field, so the value-refusal clauses are not run here; tools/github-body-field's
suite runs them on the parser.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from magpie_local_tracker.body_field_format import FieldNotFoundError
from magpie_local_tracker.descriptor import load
from magpie_local_tracker.store import Tracker, TrackerError

CASES_FILE = Path(__file__).resolve().parents[2] / "body-field-contract" / "conformance" / "cases.jsonl"
if not CASES_FILE.is_file():
    pytest.skip(f"conformance cases absent: {CASES_FILE}", allow_module_level=True)
ALL = [json.loads(line) for line in CASES_FILE.read_text(encoding="utf-8").split("\n") if line.strip()]
# Through the store, values are escaped instead of refused (see the module docstring),
# names are matched leniently, and only extract and replace exist.
SKIPPED_CLAUSES = {"BF-REP-3", "BF-REP-4", "BF-REP-5"}
CASES = [
    c
    for c in ALL
    if c["op"] in ("extract", "replace")
    and c["clause"] not in SKIPPED_CLAUSES
    and not {"case-sensitive", "inner-whitespace"} & set(c["tags"])
    and not c["body"].startswith(("\n", "\r"))
]
KINDS = {
    "FieldNotFoundError": "not_found",
    "DuplicateFieldError": "duplicate",
    "AmbiguousFieldError": "ambiguous",
}
FRONT = "---\ntitle: case\nstate: open\n---\n\n"
_FRONT_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n\r?\n", re.DOTALL)
# (each case's outcome, each case file's line ending before the write, working copy, fresh checkout)
Storage = tuple[dict[str, dict[str, Any]], dict[str, str], Path, Path]


def _run(cwd: Path, *argv: str) -> str:
    return subprocess.run(argv, cwd=cwd, check=True, capture_output=True, text=True).stdout


def _issue_text(case: dict[str, Any]) -> str:
    """The case body under front matter in the body's own line-ending convention."""
    eol = "\r\n" if "\r\n" in case["body"] else "\n"
    return FRONT.replace("\n", eol) + case["body"]


def _body_of(path: Path) -> str:
    """The file's body, byte for byte, after its front matter."""
    raw = path.read_bytes().decode("utf-8")
    match = _FRONT_RE.match(raw)
    assert match, path
    return raw[match.end() :]


def _lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _ident(index: int) -> str:
    return f"SEC-{index + 1:04d}"


def _outcome(call: Any) -> dict[str, Any]:
    try:
        return {"value": call()}
    except TrackerError as exc:
        # The store refuses a duplicate or disputed field (exit 4); the parser's error is the cause.
        cause = KINDS.get(type(exc.__cause__).__name__)
        return {"error": cause or exc.args[0]}
    except FieldNotFoundError as exc:
        return {"error": KINDS[type(exc).__name__]}


def _seed(root: Path) -> None:
    """The tracker descriptor, then one issue file per case."""
    tracker = root
    tracker.mkdir(parents=True, exist_ok=True)
    from magpie_local_tracker import main

    assert main(["--root", str(tracker), "init", "--access-restricted"]) == 0
    for index, case in enumerate(CASES):
        folder = tracker / _ident(index)
        folder.mkdir()
        (folder / "issue.md").write_bytes(_issue_text(case).encode("utf-8"))


def _apply(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Every case's operation through the store, the field reads included, and the
    line ending each case file had in the working copy before it (the storage's own)."""
    tracker = Tracker(root, load(root))
    results: dict[str, dict[str, Any]] = {}
    endings: dict[str, str] = {}
    for index, case in enumerate(CASES):
        ident = _ident(index)
        name = case["args"]["name"]
        endings[case["id"]] = "\r\n" if b"\r\n" in (root / ident / "issue.md").read_bytes() else "\n"
        if case["op"] == "extract":
            got = _outcome(lambda: tracker.field_get(ident, name)["value"])
            if got.get("value", "") is None:
                got = {"error": "not_found"}
        else:
            before = _outcome(lambda: tracker.field_get(ident, name)["value"])
            if "error" in before or before["value"] is None:
                got = before if "error" in before else {"error": "not_found"}
            else:
                got = _outcome(lambda: tracker.field_set(ident, name, case["args"]["value"]))
        results[case["id"]] = got
    return results, endings


def _check(storage: Storage, case: dict[str, Any], index: int) -> None:
    """The store's result is the contract's; the file in the working copy is the
    expected body byte for byte; a fresh checkout reads the same, up to the line
    endings the storage itself converts."""
    results, endings, work, back = storage
    got = results[case["id"]]
    expected = case["expect"]
    if case["op"] == "extract":
        if "value" in expected:
            assert "value" in got and got["value"].strip() == expected["value"].strip(), case["id"]
        else:
            assert got == expected, case["id"]
        return
    body = case["body"] if "error" in expected else expected["value"]
    if "error" in expected:
        assert got == expected, case["id"]
    else:
        assert "value" in got, (case["id"], got)
    issue = Path(_ident(index)) / "issue.md"
    # Byte for byte in the file's own line endings, which an SVN commit of an
    # svn:eol-style=native file may already have turned to the platform's.
    want = body if endings[case["id"]] == "\r\n" else _lf(body)
    assert _body_of(work / issue) == want, case["id"]
    assert _lf(_body_of(back / issue)) == _lf(body), case["id"]
    if "value" in expected:
        reread = Tracker(back, load(back)).field_get(_ident(index), case["args"]["name"])["value"]
        assert str(reread or "").strip() == _lf(case["args"]["value"]).strip(), case["id"]


@pytest.fixture(scope="module")
def git_storage(tmp_path_factory: pytest.TempPathFactory) -> Storage:
    if shutil.which("git") is None:
        pytest.skip("git not installed: the Git storage round trip is not checked here")
    base = tmp_path_factory.mktemp("git")
    remote = base / "remote.git"
    _run(base, "git", "init", "--bare", "-q", str(remote))
    work = base / "work"
    _run(base, "git", "clone", "-q", str(remote), str(work))
    for key, value in (
        ("user.name", "T"),
        ("user.email", "t@example.org"),
        ("commit.gpgsign", "false"),
        ("core.autocrlf", "true"),
    ):
        _run(work, "git", "config", key, value)
    _seed(work / "security")
    _run(work, "git", "add", "-A")
    _run(work, "git", "commit", "-q", "-m", "seed")
    results, endings = _apply(work / "security")
    _run(work, "git", "add", "-A")
    _run(work, "git", "commit", "-q", "--allow-empty", "-m", "fields")
    _run(work, "git", "push", "-q", "origin", "HEAD")
    back = base / "back"
    _run(base, "git", "-c", "core.autocrlf=true", "clone", "-q", str(remote), str(back))
    return results, endings, work / "security", back / "security"


@pytest.fixture(scope="module")
def svn_storage(tmp_path_factory: pytest.TempPathFactory) -> Storage:
    if shutil.which("svn") is None or shutil.which("svnadmin") is None:
        pytest.skip("svn / svnadmin not installed: the Subversion storage round trip is not checked here")
    base = tmp_path_factory.mktemp("svn")
    env_home = base / "home"
    env_home.mkdir()
    repo = base / "repo"
    subprocess.run(
        ["svnadmin", "create", str(repo)], check=True, env={"HOME": str(env_home), "PATH": _path()}
    )
    work = base / "work"
    _svn(base, env_home, "checkout", "-q", f"file://{repo}", str(work))
    _seed(work / "security")
    _svn(work, env_home, "add", "-q", "security")
    for index in range(len(CASES)):
        issue = f"security/{_ident(index)}/issue.md"
        _svn(work, env_home, "propset", "-q", "svn:eol-style", "native", issue)
    # A report whose text holds an svn:keywords keyword, expanded on checkout.
    keyword = work / "security" / "SEC-9999"
    keyword.mkdir()
    (keyword / "issue.md").write_text(
        FRONT + "### Note\n\nrev $Id$\n\n### Severity\n\nLow\n", encoding="utf-8"
    )
    _svn(work, env_home, "add", "-q", "security/SEC-9999")
    _svn(work, env_home, "propset", "-q", "svn:keywords", "Id", "security/SEC-9999/issue.md")
    _svn(work, env_home, "commit", "-q", "-m", "seed")
    results, endings = _apply(work / "security")
    _svn(work, env_home, "commit", "-q", "-m", "fields")
    back = base / "back"
    _svn(base, env_home, "checkout", "-q", f"file://{repo}", str(back))
    return results, endings, work / "security", back / "security"


def _path() -> str:
    return os.environ.get("PATH", "")


def _svn(cwd: Path, home: Path, *args: str) -> None:
    subprocess.run(
        ["svn", *args], cwd=cwd, check=True, capture_output=True, env={"HOME": str(home), "PATH": _path()}
    )


@pytest.mark.parametrize("index", range(len(CASES)), ids=[c["id"] for c in CASES])
def test_through_git_storage(git_storage: Storage, index: int) -> None:
    _check(git_storage, CASES[index], index)


@pytest.mark.parametrize("index", range(len(CASES)), ids=[c["id"] for c in CASES])
def test_through_svn_storage(svn_storage: Storage, index: int) -> None:
    _check(svn_storage, CASES[index], index)


def test_an_expanded_svn_keyword_is_plain_text(svn_storage: Storage) -> None:
    _, _, _, back = svn_storage
    tracker = Tracker(back, load(back))
    assert str(tracker.field_get("SEC-9999", "Note")["value"] or "").startswith("rev $Id: issue.md ")
    before = (back / "SEC-9999" / "issue.md").read_bytes()
    tracker.field_set("SEC-9999", "Severity", "High")
    after = (back / "SEC-9999" / "issue.md").read_bytes()
    assert (
        after.split(b"### Note")[1].split(b"### Severity")[0]
        == before.split(b"### Note")[1].split(b"### Severity")[0]
    )
    assert tracker.field_get("SEC-9999", "Severity")["value"] == "High"


def _plain(tmp_path: Path, raw: bytes) -> tuple[Tracker, Path]:
    """A tracker on a plain directory holding one report with exactly ``raw``."""
    from magpie_local_tracker import main

    root = tmp_path / "security"
    root.mkdir()
    assert main(["--root", str(root), "init", "--access-restricted"]) == 0
    (root / "SEC-0001").mkdir()
    path = root / "SEC-0001" / "issue.md"
    path.write_bytes(raw)
    return Tracker(root, load(root)), path


@pytest.mark.parametrize("eol", ["\r\n", "\r", "\n"])
def test_a_write_keeps_the_files_line_endings(tmp_path: Path, eol: str) -> None:
    text = FRONT + "### Note\n\nkeep  me \n\n### Severity\n\nLow\n"
    tracker, path = _plain(tmp_path, text.replace("\n", eol).encode())
    tracker.field_set("SEC-0001", "Severity", "High")
    after = path.read_bytes().decode()
    # The front matter gains an `updated` date; the body is byte-identical but for the value.
    assert not set(after.replace(eol, "")) & {"\r", "\n"}  # one convention, front matter included
    expected = text.replace("Low", "High").replace("\n", eol)
    assert after[after.index("### Note") :] == expected[expected.index("### Note") :]
    assert tracker.field_get("SEC-0001", "Severity")["value"] == "High"


def test_a_write_keeps_a_missing_final_newline(tmp_path: Path) -> None:
    text = FRONT + "### Severity\n\nLow\n\n### Note\n\nlast"
    tracker, path = _plain(tmp_path, text.encode())
    tracker.field_set("SEC-0001", "Severity", "High")
    after = path.read_bytes().decode()
    expected = text.replace("Low", "High")
    assert after[after.index("### Severity") :] == expected[expected.index("### Severity") :]


def test_a_file_mixing_line_endings_is_refused(tmp_path: Path) -> None:
    raw = (FRONT + "### Severity\n\nLow\r\n").encode()
    tracker, path = _plain(tmp_path, raw)
    with pytest.raises(TrackerError) as err:
        tracker.field_set("SEC-0001", "Severity", "High")
    assert err.value.code == 4 and "mixes line endings" in str(err.value)
    assert path.read_bytes() == raw


def test_carriage_returns_in_report_text_cannot_lock_the_file(tmp_path: Path) -> None:
    """Report text is untrusted: its own ``\\r`` must neither mix the file's
    line endings (which would refuse every later write) nor start a line the
    escaping never saw."""
    from magpie_local_tracker import main

    root = tmp_path / "security"
    root.mkdir()
    assert main(["--root", str(root), "init", "--access-restricted"]) == 0
    tracker = Tracker(root, load(root))
    body = "### Severity\r\n\r\nLow\r\n\r\n### Note\r\n\r\nseen\rtwice\n"
    created = tracker.create("A report", body, [])
    ident, path = str(created["id"]), Path(str(created["path"]))
    assert b"\r" not in path.read_bytes()
    tracker.field_set(ident, "Severity", "High\r\nor\rmore\r### Forged\r\rno")
    tracker.comment(ident, "a comment\r\nover\rlines", "@lead")
    tracker.comment(ident, "a second one", "@lead")  # the comments file is still writable
    for written in path.parent.iterdir():
        assert b"\r" not in written.read_bytes(), written.name
    assert str(tracker.field_get(ident, "Severity")["value"]).startswith("High\nor\nmore\n")
    assert tracker.field_get(ident, "Forged")["value"] is None


def test_a_carriage_return_in_a_value_keeps_the_files_one_convention(tmp_path: Path) -> None:
    tracker, path = _plain(tmp_path, (FRONT + "### Severity\n\nLow\n").replace("\n", "\r\n").encode())
    tracker.field_set("SEC-0001", "Severity", "High\rstill")
    assert not set(path.read_bytes().decode().replace("\r\n", "")) & {"\r", "\n"}
    tracker.field_set("SEC-0001", "Severity", "Critical")  # still writable
    assert tracker.field_get("SEC-0001", "Severity")["value"] == "Critical"
