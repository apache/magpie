# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from magpie_local_tracker import main, sections
from magpie_local_tracker import metadata as md
from magpie_local_tracker.descriptor import DESCRIPTOR_NAME, load
from magpie_local_tracker.detect import detect


def run(capsys: pytest.CaptureFixture[str], root: Path, *args: str) -> tuple[int, Any]:
    code = main(["--root", str(root), *args])
    out = capsys.readouterr().out
    return code, (json.loads(out) if out.strip() else None)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def fresh(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    root = tmp_path / "security"
    assert run(capsys, root, "init", "--access-restricted")[0] == 0
    return root


def new_report(
    capsys: pytest.CaptureFixture[str], root: Path, tmp_path: Path, title: str = "XSS in login"
) -> str:
    t = write(tmp_path / "title.txt", title)
    b = write(tmp_path / "body.md", "### Reporter\n\nAlice\n\n### Affected versions\n\n_No response_\n")
    code, out = run(
        capsys, root, "create", "--title-file", str(t), "--body-file", str(b), "--label", "needs triage"
    )
    assert code == 0
    return out["id"]


# ---------------------------------------------------------------- metadata


def test_front_matter_round_trip_keeps_order_and_unknown_keys() -> None:
    text = '---\ntitle: "RCE: in parser"\nstate: open\nlabels: [a, "b c"]\ncustom: x\n---\n\nBody\n'
    meta, body = md.split(text)
    assert meta.values == {"title": "RCE: in parser", "state": "open", "labels": ["a", "b c"], "custom": "x"}
    assert body == "Body\n"
    assert md.split(md.render(meta, body)) == (meta, body)


def test_front_matter_block_lists() -> None:
    meta, _ = md.split("---\nlabels:\n  - one\n  - two\nmilestone:\n---\nx\n")
    assert meta.values["labels"] == ["one", "two"]
    assert meta.values["milestone"] is None
    assert meta.list_style == "block"
    assert "  - one" in md.render(meta, "x\n")


def test_bold_fields_with_h1() -> None:
    meta, body = md.split("# Title here\n\n**Status:** Open\n**Labels:** a, b\n\n## Details\n\ntext\n")
    assert meta.style == "bold-fields"
    assert meta.values == {"Status": "Open", "Labels": ["a", "b"]}
    assert body.startswith("# Title here\n")
    rendered = md.render(meta, body)
    assert rendered.startswith("# Title here\n\n**Status:** Open\n**Labels:** a, b\n")


# ---------------------------------------------------------------- sections


def test_field_set_replaces_and_appends() -> None:
    body = "### A\n\none\n\n### B\n\ntwo\n"
    new, created = sections.set_field(body, "a", "uno", 3)
    assert not created and "uno" in new and "one" not in new and "two" in new
    new, created = sections.set_field(new, "C", "three", 3)
    assert created and new.rstrip().endswith("### C\n\nthree")
    assert sections.get_field(new, "b") == "two"
    assert sections.get_field(new, "missing") is None


def test_headings_inside_code_fences_are_ignored() -> None:
    body = "### A\n\n```\n### B\n```\n\n### C\n\nc\n"
    assert sections.get_field(body, "B") is None
    assert "### B" in (sections.get_field(body, "A") or "")


def test_rollup_append_and_amend() -> None:
    first = sections.rollup_append(None, "trk", sections.render_entry("2026-01-01", "@a", "Import", "  x"))
    assert first.startswith("<!-- trk status rollup v1")
    assert "\nx\n" in first  # left-trimmed
    second = sections.rollup_append(first, "trk", sections.render_entry("2026-01-02", "@b", "Sync", "y"))
    assert "\n\n---\n\n<details><summary>2026-01-02 · @b · Sync</summary>" in second
    assert sections.rollup_amend_latest(second, "Import", "z") is None
    amended = sections.rollup_amend_latest(second, "Sync", "z")
    assert (
        amended is not None
        and amended.count("<details>") == 2
        and "\nz\n" in amended
        and "\ny\n" not in amended
    )


# ---------------------------------------------------------------- default format, every op


def test_full_lifecycle_default_format(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ident = new_report(capsys, fresh, tmp_path)
    assert ident == "SEC-0001"
    assert (fresh / "SEC-0001" / "issue.md").is_file()
    assert new_report(capsys, fresh, tmp_path, "Second") == "SEC-0002"

    _, view = run(capsys, fresh, "view", "1")
    assert view["title"] == "XSS in login" and view["state"] == "open"
    assert view["labels"] == ["needs triage"]

    code, _ = run(capsys, fresh, "edit", ident, "--add-label", "cve allocated", "--remove-label", "needs triage",
                  "--add-assignee", "@bob", "--milestone", "1.2.3")  # fmt: skip
    assert code == 0
    _, view = run(capsys, fresh, "view", ident)
    assert view["labels"] == ["cve allocated"] and view["assignees"] == ["@bob"]
    assert view["milestone"] == "1.2.3"

    value = write(tmp_path / "v.md", "1.0 to 1.2")
    _, out = run(capsys, fresh, "field-set", ident, "Affected versions", "--value-file", str(value))
    assert out == {"id": ident, "heading": "Affected versions", "created": False}
    _, out = run(capsys, fresh, "field-get", ident, "affected versions")
    assert out["value"] == "1.0 to 1.2"

    c = write(tmp_path / "c.md", "Looks valid.")
    _, out = run(capsys, fresh, "comment", ident, "--body-file", str(c), "--author", "@carol")
    assert out["comment_id"] == 1
    run(capsys, fresh, "comment", ident, "--body-file", str(c), "--author", "@dave")
    _, view = run(capsys, fresh, "view", ident, "--comments")
    assert [x["author"] for x in view["comments"]] == ["@carol", "@dave"]

    e = write(tmp_path / "e.md", "Imported from the list.")
    run(capsys, fresh, "rollup-append", ident, "--action", "Import", "--entry-body-file", str(e), "--user", "@x",
        "--now", "2026-10-15T00:00:00Z")  # fmt: skip
    rollup = (fresh / ident / "status-rollup.md").read_text()
    assert "2026-10-15 · @x · Import" in rollup
    assert (
        run(capsys, fresh, "rollup-amend-latest", ident, "--action", "Sync", "--entry-body-file", str(e))[0]
        == 4
    )

    att = write(tmp_path / "cve.json", "{}")
    _, out = run(capsys, fresh, "attach", ident, str(att), "--name", "../../evil.json")
    assert out["name"] == "evil.json"
    assert (fresh / ident / "attachments" / "evil.json").is_file()

    _, listed = run(capsys, fresh, "list", "--label", "cve allocated")
    assert [x["id"] for x in listed] == [ident]
    _, listed = run(capsys, fresh, "list", "--search", "second")
    assert [x["id"] for x in listed] == ["SEC-0002"]

    run(capsys, fresh, "close", ident, "--reason", "not-planned")
    _, view = run(capsys, fresh, "view", ident)
    assert view["state"] == "closed"
    assert [x["id"] for x in run(capsys, fresh, "list")[1]] == ["SEC-0002"]
    run(capsys, fresh, "reopen", ident)
    assert run(capsys, fresh, "view", ident)[1]["state"] == "open"
    assert run(capsys, fresh, "labels")[1] == ["cve allocated", "needs triage"]


def test_writes_refused_until_access_confirmed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "t"
    run(capsys, root, "init")
    t = write(tmp_path / "t.txt", "x")
    code = main(["--root", str(root), "create", "--title-file", str(t), "--body-file", str(t)])
    assert code == 4
    assert "access_restricted" in capsys.readouterr().err


def test_unknown_id_is_exit_3(fresh: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(fresh), "view", "SEC-9999"]) == 3


def test_missing_descriptor_is_exit_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(tmp_path), "list"]) == 3


# ---------------------------------------------------------------- detection


def test_detect_empty_folder_gives_default(tmp_path: Path) -> None:
    desc, evidence = detect(tmp_path / "nothing")
    assert evidence["confidence"] == "default"
    assert desc.layout == "folder-per-issue"


def test_detect_file_per_issue_bold_fields_state_dirs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "reports"
    write(root / "open" / "2024-007-xss-in-login.md",
          "# XSS in login\n\n**Status:** Triage\n**Reporter:** Eve\n\n## Details\n\nx\n\n## Notes\n\n### 2024-01-01 — @a\n\nhi\n")  # fmt: skip
    write(root / "open" / "2024-012-csrf.md", "# CSRF\n\n**Status:** Accepted\n\n## Details\n\ny\n")
    write(root / "closed" / "2024-003-sqli.md", "# SQLi\n\n**Status:** Fixed\n\n## Details\n\nz\n")
    write(root / "README.md", "index")
    desc, evidence = detect(root)
    assert desc.layout == "file-per-issue"
    assert desc.state.mode == "directory" and desc.state.closed_dir == "closed"
    assert desc.id.prefix == "2024-" and desc.id.width == 3 and desc.id.slug
    assert desc.metadata == "bold-fields" and desc.title_source == "h1"
    assert desc.field_heading_level == 2
    assert desc.comments_mode == "section" and desc.comments_heading == "Notes"
    assert evidence["reports_found"] == 3

    run(capsys, root, "detect", "--write", "--access-restricted")
    assert load(root).access_restricted
    _, listed = run(capsys, root, "list", "--state", "all")
    assert {x["id"]: x["state"] for x in listed} == {
        "2024-012-csrf": "open", "2024-007-xss-in-login": "open", "2024-003-sqli": "closed",
    }  # fmt: skip

    t = write(tmp_path / "t.txt", "Path traversal in upload")
    b = write(tmp_path / "b.md", "## Details\n\nnew\n")
    _, out = run(capsys, root, "create", "--title-file", str(t), "--body-file", str(b))
    assert out["id"] == "2024-013-path-traversal-in-upload"
    created = (root / "open" / "2024-013-path-traversal-in-upload.md").read_text()
    assert created.startswith("# Path traversal in upload\n\n**Status:** Triage")

    # Comments are recovered from the hand-written headings, and appended in the same section.
    c = write(tmp_path / "c.md", "ack")
    run(capsys, root, "comment", "7", "--body-file", str(c), "--author", "@bob")
    _, view = run(capsys, root, "view", "2024-007", "--comments")
    assert [x["author"] for x in view["comments"]] == ["@a", "@bob"]
    assert "## Notes" not in view["body"]

    # A field set lands before the managed comment section, not after it.
    v = write(tmp_path / "v.md", "9.9")
    run(capsys, root, "field-set", "7", "Affected versions", "--value-file", str(v))
    text = (root / "open" / "2024-007-xss-in-login.md").read_text()
    assert text.index("## Affected versions") < text.index("## Notes")

    run(capsys, root, "close", "7")
    assert (root / "closed" / "2024-007-xss-in-login.md").is_file()
    assert not (root / "open" / "2024-007-xss-in-login.md").exists()


def test_detect_folder_front_matter_custom_keys(tmp_path: Path) -> None:
    root = tmp_path / "t"
    for n, status in ((1, "new"), (2, "fixed"), (3, "rejected")):
        write(root / f"VULN-{n}" / "report.md",
              f"---\nSummary: report {n}\nStatus: {status}\nTags: [a]\n---\n\n## Description\n\nd\n")  # fmt: skip
        write(root / f"VULN-{n}" / "notes.md", "")
    desc, _ = detect(root)
    assert desc.layout == "folder-per-issue" and desc.issue_file == "report.md"
    assert desc.id.prefix == "VULN-" and desc.id.width == 1
    assert (
        desc.keys["title"] == "Summary" and desc.keys["state"] == "Status" and desc.keys["labels"] == "Tags"
    )
    assert desc.keys["milestone"] == "Milestone"  # required role added in the team's casing
    assert desc.state.open_value == "new" and desc.state.closed_value == "fixed"
    assert desc.state.not_planned_value == "rejected"
    assert desc.comments_mode == "file" and desc.comments_file == "notes.md"


# ---------------------------------------------------------------- vcs


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_publish_git_commits_only_tracker_root_and_pushes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "-q", str(remote))
    repo = tmp_path / "repo"
    _git(tmp_path, "clone", "-q", str(remote), str(repo))
    for key, value in (("user.name", "T"), ("user.email", "t@example.org"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    write(repo / "README.md", "x")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "push", "-q", "origin", "HEAD")
    write(repo / "unrelated.txt", "keep me out")

    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    new_report(capsys, root, tmp_path)
    _, pending = run(capsys, root, "pending")
    assert pending["needs_publish"] and pending["vcs"] == "git"
    assert all(c["path"].startswith("security/") for c in pending["changes"])

    msg = write(tmp_path / "msg.txt", "security: import SEC-0001\n")
    _, out = run(
        capsys, root, "publish", "--message-file", str(msg), "--trailer", "Generated-by: test", "--push"
    )
    assert out["committed"] and out["pushed"]
    files = _git(repo, "show", "--name-only", "--format=%B", "HEAD")
    assert "Generated-by: test" in files and "security/SEC-0001/issue.md" in files
    assert "unrelated.txt" not in files
    assert _git(remote, "log", "--oneline").count("\n") == 2
    assert run(capsys, root, "pending")[1]["needs_publish"] is False


@pytest.mark.skipif(
    shutil.which("svn") is None or shutil.which("svnadmin") is None, reason="svn not installed"
)
def test_publish_svn(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # svn reads ~/.subversion; keep the test off the real home directory.
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "svnrepo"
    subprocess.run(["svnadmin", "create", str(repo)], check=True)
    wc = tmp_path / "wc"
    subprocess.run(["svn", "checkout", "-q", f"file://{repo}", str(wc)], check=True)
    root = wc / "security"
    run(capsys, root, "init", "--access-restricted")
    ident = new_report(capsys, root, tmp_path)
    msg = write(tmp_path / "msg.txt", "security: import\n")
    _, out = run(capsys, root, "publish", "--message-file", str(msg), "--push")
    assert out["committed"] and out["revision"] == "1"
    log = subprocess.run(["svn", "log", "-v", f"file://{repo}"], capture_output=True, text=True).stdout
    assert f"security/{ident}/issue.md" in log


def test_descriptor_file_name() -> None:
    assert DESCRIPTOR_NAME == ".magpie-tracker.json"
