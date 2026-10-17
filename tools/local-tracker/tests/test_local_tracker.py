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
from magpie_local_tracker.store import Tracker, TrackerError


@pytest.fixture(autouse=True)
def _allow_local_test_remotes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tests push to bare repositories on disk; production allows only
    https/ssh. Widened here, in-process, never through the environment."""
    from magpie_local_tracker import vcs

    monkeypatch.setattr(vcs, "_GIT_SAFE", (*vcs._GIT_SAFE, "-c", "protocol.file.allow=always"))
    monkeypatch.setattr(vcs, "_PUSH_SCHEMES", (*vcs._PUSH_SCHEMES, "file"))
    original = vcs.push_url_allowed
    monkeypatch.setattr(vcs, "push_url_allowed", lambda url: url.startswith("/") or original(url))


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


# ---------------------------------------------------------------- review fixes


def test_writes_refuse_symlinks_out_of_the_tracker(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ident = new_report(capsys, fresh, tmp_path)
    outside = write(tmp_path / "outside.md", "### Affected versions\n\nkeep\n")
    issue = fresh / ident / "issue.md"
    issue.unlink()
    issue.symlink_to(outside)
    v = write(tmp_path / "v.md", "pwned")
    # The symlinked entry is not even listed, so it cannot be addressed.
    assert main(["--root", str(fresh), "field-set", ident, "Affected versions", "--value-file", str(v)]) == 3
    assert outside.read_text() == "### Affected versions\n\nkeep\n"


def test_symlinked_comments_file_is_refused(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ident = new_report(capsys, fresh, tmp_path)
    outside = write(tmp_path / "outside.txt", "secret")
    (fresh / ident / "comments.md").symlink_to(outside)
    c = write(tmp_path / "c.md", "hi")
    assert main(["--root", str(fresh), "comment", ident, "--body-file", str(c)]) == 4
    assert outside.read_text() == "secret"


def test_descriptor_names_cannot_escape(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "t"
    run(capsys, root, "init", "--access-restricted")
    data = json.loads((root / DESCRIPTOR_NAME).read_text())
    data["comments_file"] = "../../evil.md"
    (root / DESCRIPTOR_NAME).write_text(json.dumps(data))
    assert main(["--root", str(root), "list"]) == 5
    assert "plain file or folder name" in capsys.readouterr().err


def test_rollup_with_a_spaced_name_is_appended_not_replaced() -> None:
    old = "<!-- Security Reports status rollup v1 — x -->\n" + sections.render_entry(
        "2026-01-01", "@a", "Import", "a"
    )
    new = sections.rollup_append(
        old, "security-tracker", sections.render_entry("2026-01-02", "@b", "Sync", "b")
    )
    assert new.count("<details>") == 2 and new.startswith("<!-- Security Reports")


def test_metadata_free_report_gets_metadata_on_first_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "r"
    write(root / "VULN-1.md", "# Old report\n\n## Details\n\nx\n")
    write(root / "VULN-2.md", "# Other\n\n## Details\n\ny\n")
    run(capsys, root, "detect", "--write", "--access-restricted")
    run(capsys, root, "edit", "1", "--add-label", "needs triage")
    run(capsys, root, "close", "1")
    _, view = run(capsys, root, "view", "1")
    assert view["labels"] == ["needs triage"] and view["state"] == "closed"
    assert (root / "VULN-1.md").read_text().startswith("# Old report\n\n**")


def test_view_comments_includes_the_rollup_first(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ident = new_report(capsys, fresh, tmp_path)
    e = write(tmp_path / "e.md", "<!-- processed: 123 -->")
    run(
        capsys, fresh, "rollup-append", ident, "--action", "Sync", "--entry-body-file", str(e), "--user", "@x"
    )
    c = write(tmp_path / "c.md", "human note")
    run(capsys, fresh, "comment", ident, "--body-file", str(c), "--author", "@y")
    _, view = run(capsys, fresh, "view", ident, "--comments")
    assert view["comments"][0]["kind"] == "rollup" and "processed: 123" in view["comments"][0]["body"]
    assert view["comments"][1]["author"] == "@y"


def test_every_prefix_in_use_stays_visible(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "y"
    for name in ("2025-001", "2026-001", "2026-002"):
        write(root / f"{name}.md", f"---\ntitle: {name}\nstate: open\n---\n\nbody\n")
    run(capsys, root, "detect", "--write", "--access-restricted")
    _, listed = run(capsys, root, "list")
    assert {x["id"] for x in listed} == {"2025-001", "2026-001", "2026-002"}
    assert main(["--root", str(root), "view", "1"]) == 2  # ambiguous bare number
    capsys.readouterr()
    t = write(tmp_path / "t.txt", "new")
    _, out = run(capsys, root, "create", "--title-file", str(t), "--body-file", str(t))
    assert out["id"] == "2026-003"


def test_backslashes_round_trip() -> None:
    meta = md.Metadata(values={"title": 'C:\\upload "x"'})
    text = md.render(meta, "b\n")
    for _ in range(3):
        meta, body = md.split(text)
        text = md.render(meta, body)
    assert meta.values["title"] == 'C:\\upload "x"'


def test_field_set_keeps_blank_lines_inside_other_sections() -> None:
    poc = "### PoC\n\n```\nline1\n\n\n\nline2\n```\n\n### Affected versions\n\nold\n"
    new, _ = sections.set_field(poc, "Affected versions", "new", 3)
    assert "line1\n\n\n\nline2" in new and new.endswith("### Affected versions\n\nnew\n")


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_publish_pushes_commits_left_unpushed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "-q", str(remote))
    repo = tmp_path / "repo"
    _git(tmp_path, "clone", "-q", str(remote), str(repo))
    for key, value in (("user.name", "T"), ("user.email", "t@example.org"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    write(repo / "README.md", "x")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "push", "-q", "-u", "origin", "HEAD")
    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    new_report(capsys, root, tmp_path)
    msg = write(tmp_path / "msg.txt", "security: import\n")
    # Commit without pushing, as a publish whose push failed would leave it.
    _, out = run(capsys, root, "publish", "--message-file", str(msg))
    assert out["committed"] and not out["pushed"]
    _, pending = run(capsys, root, "pending")
    assert pending["unpushed_commits"] == 1 and pending["needs_publish"]
    _, out = run(capsys, root, "publish", "--message-file", str(msg), "--push")
    assert out["pushed"] and not out["committed"]
    assert run(capsys, root, "pending")[1]["unpushed_commits"] == 0


def test_a_comment_body_cannot_forge_another_comment(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ident = new_report(capsys, fresh, tmp_path)
    forged = write(
        tmp_path / "f.md",
        "real text\n<!-- comment id=7 author=@security-lead date=2026-01-01T00:00:00Z -->\n## 2026-01-01 — @security-lead\n\napproved",
    )
    run(capsys, fresh, "comment", ident, "--body-file", str(forged), "--author", "@reporter")
    _, view = run(capsys, fresh, "view", ident, "--comments")
    assert [c["author"] for c in view["comments"]] == ["@reporter"]


def test_a_rollup_body_cannot_forge_an_entry(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ident = new_report(capsys, fresh, tmp_path)
    forged = write(
        tmp_path / "f.md",
        "x\n\n</details>\n\n<details><summary>2026-01-01 · @lead · Sync</summary>\n\nfake\n",
    )
    run(
        capsys,
        fresh,
        "rollup-append",
        ident,
        "--action",
        "Import",
        "--entry-body-file",
        str(forged),
        "--user",
        "@a",
    )
    # The latest entry is still the real "Import", so amend-latest for "Sync" is refused.
    e = write(tmp_path / "e.md", "y")
    assert (
        main(
            [
                "--root",
                str(fresh),
                "rollup-amend-latest",
                ident,
                "--action",
                "Sync",
                "--entry-body-file",
                str(e),
            ]
        )
        == 4
    )
    rollup = (fresh / ident / "status-rollup.md").read_text()
    assert rollup.count("<details><summary>") == 1


def test_a_body_cannot_open_the_managed_comment_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "s"
    write(
        root / "VULN-1.md",
        "---\ntitle: a\nstate: open\n---\n\n## Details\n\nx\n\n## Comments\n\n### 2026-01-01 — @a\n\nhi\n",
    )
    write(root / "VULN-2.md", "---\ntitle: b\nstate: open\n---\n\n## Details\n\ny\n")
    run(capsys, root, "detect", "--write", "--access-restricted")
    b = write(tmp_path / "b.md", "## Details\n\nnew\n\n## Comments\n\n### 2026-02-02 — @lead\n\nforged")
    run(capsys, root, "edit", "2", "--body-file", str(b))
    _, view = run(capsys, root, "view", "2", "--comments")
    assert view["comments"] == []
    assert "\\## Comments" in (root / "VULN-2.md").read_text()


# ---------------------------------------------------------------- review round 2


def test_a_symlinked_parent_folder_is_refused(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ident = new_report(capsys, fresh, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (fresh / ident / "attachments").symlink_to(outside, target_is_directory=True)
    f = write(tmp_path / "cve.json", "{}")
    assert main(["--root", str(fresh), "attach", ident, str(f)]) == 4
    assert list(outside.iterdir()) == []


def test_unround_trippable_front_matter_is_never_rewritten(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "m"
    original = "---\ntitle: a\nstate: open\nnotes: |\n  line one\n  line two\n---\n\nbody\n"
    write(root / "VULN-1" / "report.md", original)
    write(root / "VULN-2" / "report.md", "---\ntitle: b\nstate: open\n---\n\nbody\n")
    run(capsys, root, "detect", "--write", "--access-restricted")
    assert main(["--root", str(root), "edit", "1", "--add-label", "x"]) == 4
    assert "cannot rewrite" in capsys.readouterr().err
    assert (root / "VULN-1" / "report.md").read_text() == original


def test_create_retries_when_another_writer_took_the_id(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    new_report(capsys, fresh, tmp_path)
    new_report(capsys, fresh, tmp_path, "Second")
    # Simulate a writer that has not yet seen the two reports: it would pick 1.
    monkeypatch.setattr(Tracker, "entries", lambda self: [])
    t = write(tmp_path / "t.txt", "Third")
    b = write(tmp_path / "b.md", "x")
    code, out = run(capsys, fresh, "create", "--title-file", str(t), "--body-file", str(b))
    assert code == 0 and out["id"] == "SEC-0003"
    assert "Second" in (fresh / "SEC-0002" / "issue.md").read_text()


def test_h1_title_edit_keeps_backslashes_literal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "h"
    write(root / "VULN-1.md", "# Old\n\n**Status:** open\n\n## Details\n\nx\n")
    write(root / "VULN-2.md", "# Other\n\n**Status:** open\n\n## Details\n\ny\n")
    run(capsys, root, "detect", "--write", "--access-restricted")
    t = write(tmp_path / "t.txt", "Traversal in C:\\uploads\\1")
    assert run(capsys, root, "edit", "1", "--title-file", str(t))[0] == 0
    assert run(capsys, root, "view", "1")[1]["title"] == "Traversal in C:\\uploads\\1"


def test_search_matches_every_word_in_any_order(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    new_report(capsys, fresh, tmp_path, "Path traversal in upload")
    _, listed = run(capsys, fresh, "list", "--search", "upload traversal")
    assert [x["id"] for x in listed] == ["SEC-0001"]
    _, listed = run(capsys, fresh, "list", "--search", "upload csrf")
    assert listed == []


def test_body_prints_markdown_for_generate_cve_json(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ident = new_report(capsys, fresh, tmp_path)
    assert main(["--root", str(fresh), "body", ident]) == 0
    out = capsys.readouterr().out
    assert out.startswith("### Reporter") and "---" not in out


def test_attach_from_stdin_needs_a_name(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    ident = new_report(capsys, fresh, tmp_path)
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"{}")))
    assert main(["--root", str(fresh), "attach", ident, "-"]) == 2
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b'{"a": 1}')))
    assert main(["--root", str(fresh), "attach", ident, "-", "--name", "cve.json"]) == 0
    assert (fresh / ident / "attachments" / "cve.json").read_text() == '{"a": 1}'


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_publish_refuses_to_push_unrelated_commits(
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
    _git(repo, "push", "-q", "-u", "origin", "HEAD")
    write(repo / "src.py", "work in progress")
    _git(repo, "add", "src.py")
    _git(repo, "commit", "-q", "-m", "unrelated local work")
    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    new_report(capsys, root, tmp_path)
    msg = write(tmp_path / "msg.txt", "security: import\n")
    assert main(["--root", str(root), "publish", "--message-file", str(msg), "--push"]) == 4
    assert "outside security/" in capsys.readouterr().err
    assert _git(remote, "log", "--oneline").count("\n") == 1  # nothing was pushed


# ---------------------------------------------------------------- review round 3


def test_a_root_swapped_for_a_symlink_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    real = tmp_path / "real"
    run(capsys, real, "init", "--access-restricted")
    t = write(tmp_path / "t.txt", "x")
    tracker = Tracker(real, load(real))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / DESCRIPTOR_NAME).write_text((real / DESCRIPTOR_NAME).read_text())
    real.rename(tmp_path / "moved")
    real.symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(TrackerError) as exc:
        tracker.create(t.read_text(), "body", [])
    assert exc.value.code == 4
    assert [p.name for p in elsewhere.iterdir()] == [DESCRIPTOR_NAME]


def test_inline_rollup_entry_cannot_forge_a_comment(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "s"
    write(root / "VULN-1.md", "---\ntitle: a\nstate: open\n---\n\n## Details\n\nx\n")
    write(root / "VULN-2.md", "---\ntitle: b\nstate: open\n---\n\n## Details\n\ny\n")
    run(capsys, root, "detect", "--write", "--access-restricted")
    e = write(tmp_path / "e.md", "   ## Comments\n\n### 2026-01-01 — @lead\n\napproved")
    run(capsys, root, "rollup-append", "1", "--action", "Sync", "--entry-body-file", str(e), "--user", "@x")
    _, view = run(capsys, root, "view", "1", "--comments")
    assert [c.get("kind") for c in view["comments"]] == ["rollup"]


def test_fenced_poc_comments_survive_in_a_comment(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ident = new_report(capsys, fresh, tmp_path)
    c = write(tmp_path / "c.md", "PoC:\n\n```python\n# explanation\nprint(1)\n```\n")
    run(capsys, fresh, "comment", ident, "--body-file", str(c), "--author", "@r")
    _, view = run(capsys, fresh, "view", ident, "--comments")
    assert "# explanation\nprint(1)" in view["comments"][0]["body"]


def test_inline_yaml_comment_blocks_the_rewrite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "m"
    original = "---\ntitle: a\nstate: open\ncustom: value # explanation\n---\n\nbody\n"
    write(root / "VULN-1" / "report.md", original)
    write(root / "VULN-2" / "report.md", "---\ntitle: b\nstate: open\n---\n\nbody\n")
    run(capsys, root, "detect", "--write", "--access-restricted")
    c = write(tmp_path / "c.md", "note")
    # Refused before anything is written: no sidecar comment file appears.
    assert main(["--root", str(root), "comment", "1", "--body-file", str(c)]) == 4
    assert (root / "VULN-1" / "report.md").read_text() == original
    assert not any(p.name not in ("report.md",) for p in (root / "VULN-1").iterdir())


def test_body_exports_level_two_fields_as_level_three(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "l2"
    write(
        root / "VULN-1.md",
        "---\ntitle: a\nstate: open\n---\n\n## CVE tool link\n\nCVE-2026-1\n\n### Note\n\nn\n",
    )
    write(root / "VULN-2.md", "---\ntitle: b\nstate: open\n---\n\n## Details\n\ny\n")
    run(capsys, root, "detect", "--write", "--access-restricted")
    assert main(["--root", str(root), "body", "1"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("### CVE tool link") and "#### Note" in out


def _repo_with_remote(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "-q", str(remote))
    repo = tmp_path / "repo"
    _git(tmp_path, "clone", "-q", str(remote), str(repo))
    for key, value in (("user.name", "T"), ("user.email", "t@example.org"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    write(repo / "README.md", "x")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "push", "-q", "-u", "origin", "HEAD")
    return remote, repo


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_publish_counts_commits_already_on_another_remote_branch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _remote, repo = _repo_with_remote(tmp_path)
    write(repo / "src.py", "feature work")
    _git(repo, "add", "src.py")
    _git(repo, "commit", "-q", "-m", "feature")
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/feature")  # on origin/feature, not on main
    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    new_report(capsys, root, tmp_path)
    msg = write(tmp_path / "msg.txt", "security: import\n")
    assert main(["--root", str(root), "publish", "--message-file", str(msg), "--push"]) == 4


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_publish_sees_changes_that_exist_only_in_a_merge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _remote, repo = _repo_with_remote(tmp_path)
    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    _git(repo, "checkout", "-q", "-b", "side")
    write(repo / "security" / "a.md", "a")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "side")
    _git(repo, "checkout", "-q", "-")
    _git(repo, "merge", "-q", "--no-ff", "--no-commit", "side")
    write(repo / "src.py", "slipped into the merge")
    _git(repo, "add", "src.py")
    _git(repo, "commit", "-q", "-m", "merge")
    new_report(capsys, root, tmp_path)
    msg = write(tmp_path / "msg.txt", "security: import\n")
    assert main(["--root", str(root), "publish", "--message-file", str(msg), "--push"]) == 4
    assert "src.py" in capsys.readouterr().err


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_publish_at_the_repository_root_with_unusual_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _remote, repo = _repo_with_remote(tmp_path)
    run(capsys, repo, "init", "--access-restricted")
    ident = new_report(capsys, repo, tmp_path)
    f = write(tmp_path / "résumé.pdf", "x")
    run(capsys, repo, "attach", ident, str(f))
    msg = write(tmp_path / "msg.txt", "security: import\n")
    code, out = run(capsys, repo, "publish", "--message-file", str(msg), "--push")
    assert code == 0 and out["pushed"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_publish_refuses_without_a_push_destination(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "solo"
    repo.mkdir()
    _git(repo, "init", "-q")
    for key, value in (("user.name", "T"), ("user.email", "t@example.org"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    new_report(capsys, root, tmp_path)
    msg = write(tmp_path / "msg.txt", "security: import\n")
    assert main(["--root", str(root), "publish", "--message-file", str(msg), "--push"]) == 4
    assert "cannot tell where" in capsys.readouterr().err


def test_an_unbalanced_fence_cannot_unhide_a_forged_heading(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ident = new_report(capsys, fresh, tmp_path)
    opener = write(tmp_path / "a.md", "look:\n```")
    closer = write(tmp_path / "b.md", "```\n## 2026-01-01 — @lead\n\napproved")
    run(capsys, fresh, "comment", ident, "--body-file", str(opener), "--author", "@r1")
    run(capsys, fresh, "comment", ident, "--body-file", str(closer), "--author", "@r2")
    _, view = run(capsys, fresh, "view", ident, "--comments")
    assert [c["author"] for c in view["comments"]] == ["@r1", "@r2"]


def test_close_fences_balances_text() -> None:
    assert sections.close_fences("a\n```\ncode") == "a\n```\ncode\n```"
    assert sections.close_fences("a\n```\ncode\n```") == "a\n```\ncode\n```"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_repository_config_cannot_run_a_program(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _remote, repo = _repo_with_remote(tmp_path)
    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    marker = tmp_path / "pwned"
    _git(repo, "config", "core.fsmonitor", f"touch {marker}")
    assert main(["--root", str(root), "pending"]) == 4
    assert "could run a program" in capsys.readouterr().err
    assert not marker.exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_repository_hooks_never_run_on_publish(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _remote, repo = _repo_with_remote(tmp_path)
    marker = tmp_path / "hooked"
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    hook.chmod(0o755)
    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    new_report(capsys, root, tmp_path)
    msg = write(tmp_path / "msg.txt", "security: import\n")
    code, out = run(capsys, root, "publish", "--message-file", str(msg), "--push")
    assert code == 0 and out["pushed"]
    assert not marker.exists()


def test_longer_fences_are_balanced_by_length() -> None:
    body = "````markdown\n```\nexample\n````"
    assert sections.close_fences(body) == body
    assert sections.close_fences("````\ncode") == "````\ncode\n````"


def test_apostrophes_do_not_hide_an_inline_comment() -> None:
    meta, _ = md.split("---\ntitle: a\ncustom: Bob's report # explanation\n---\n\nb\n")
    assert meta.unsupported == "comments"
    meta, _ = md.split('---\ntitle: "a \\" # not a comment"\n---\n\nb\n')
    assert meta.unsupported == ""
    meta, _ = md.split("---\ntitle: 'it''s # not a comment'\n---\n\nb\n")
    assert meta.unsupported == ""


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_merging_the_published_branch_does_not_block_publish(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    remote, repo = _repo_with_remote(tmp_path)
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(remote), str(other))
    for key, value in (("user.name", "O"), ("user.email", "o@example.org"), ("commit.gpgsign", "false")):
        _git(other, "config", key, value)
    write(other / "src.py", "someone else's published change")
    _git(other, "add", "src.py")
    _git(other, "commit", "-q", "-m", "upstream work")
    _git(other, "push", "-q")
    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    new_report(capsys, root, tmp_path)
    msg = write(tmp_path / "msg.txt", "security: import\n")
    run(capsys, root, "publish", "--message-file", str(msg))  # commit only
    _git(repo, "pull", "-q", "--no-rebase", "--no-edit")  # merge the published src.py
    code, out = run(capsys, root, "publish", "--message-file", str(msg), "--push")
    assert code == 0 and out["pushed"]


def test_push_urls_must_be_network_remotes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()  # the production rules, without the test-only widening
    from magpie_local_tracker.vcs import push_url_allowed

    assert push_url_allowed("https://github.com/acme/tracker.git")
    assert push_url_allowed("ssh://git@github.com/acme/tracker.git")
    assert push_url_allowed("git@github.com:acme/tracker.git")
    for bad in ("/tmp/evil.git", "file:///tmp/evil.git", "../evil", "ext::sh -c x", "c:/x"):
        assert not push_url_allowed(bad), bad


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_gc_hook_config_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _remote, repo = _repo_with_remote(tmp_path)
    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    _git(repo, "config", "gc.recentObjectsHook", "touch /tmp/never")
    assert main(["--root", str(root), "pending"]) == 4
    assert "gc.recentobjectshook" in capsys.readouterr().err.lower()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_publish_refuses_a_merge_that_reverts_published_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    remote, repo = _repo_with_remote(tmp_path)
    write(repo / "src.py", "v1")
    _git(repo, "add", "src.py")
    _git(repo, "commit", "-q", "-m", "v1")
    _git(repo, "push", "-q")
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(remote), str(other))
    for key, value in (("user.name", "O"), ("user.email", "o@example.org"), ("commit.gpgsign", "false")):
        _git(other, "config", key, value)
    write(other / "src.py", "v2")
    _git(other, "commit", "-q", "-am", "v2")
    _git(other, "push", "-q")
    _git(repo, "fetch", "-q")
    _git(repo, "merge", "-q", "-s", "ours", "--no-edit", "@{upstream}")
    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    new_report(capsys, root, tmp_path)
    msg = write(tmp_path / "msg.txt", "security: import\n")
    assert main(["--root", str(root), "publish", "--message-file", str(msg), "--push"]) == 4
    assert "src.py" in capsys.readouterr().err


def test_a_hash_inside_a_quoted_list_item_is_not_a_comment(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ident = new_report(capsys, fresh, tmp_path)
    assert run(capsys, fresh, "edit", ident, "--add-label", "see #123")[0] == 0
    assert run(capsys, fresh, "edit", ident, "--add-label", "second")[0] == 0
    assert run(capsys, fresh, "view", ident)[1]["labels"] == ["needs triage", "see #123", "second"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_publish_pushes_only_the_checked_branch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    remote, repo = _repo_with_remote(tmp_path)
    main_branch = _git(repo, "symbolic-ref", "--short", "HEAD").strip()
    # Another branch on the remote with an unpublished local commit: with
    # push.default=matching a bare `git push` would send it too.
    _git(repo, "checkout", "-q", "-b", "other")
    _git(repo, "push", "-q", "origin", "other")
    write(repo / "src.py", "unreviewed work")
    _git(repo, "add", "src.py")
    _git(repo, "commit", "-q", "-m", "wip")
    _git(repo, "checkout", "-q", main_branch)
    _git(repo, "config", "push.default", "matching")
    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    new_report(capsys, root, tmp_path)
    msg = write(tmp_path / "msg.txt", "security: import\n")
    code, out = run(capsys, root, "publish", "--message-file", str(msg), "--push")
    assert code == 0 and out["pushed"]
    assert _git(remote, "rev-parse", "other").strip() != _git(repo, "rev-parse", "other").strip()
    assert _git(remote, "rev-parse", main_branch).strip() == _git(repo, "rev-parse", "HEAD").strip()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_attributes_from_the_working_tree_cannot_start_a_filter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _remote, repo = _repo_with_remote(tmp_path)
    marker = tmp_path / "filtered"
    # A filter driver outside the repository's own config (which the config
    # check refuses), switched on by a `.gitattributes` in the working tree.
    global_config = write(tmp_path / "gitconfig", f'[filter "evil"]\n\tclean = touch {marker}; cat\n')
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    root = repo / "security"
    run(capsys, root, "init", "--access-restricted")
    write(root / ".gitattributes", "* filter=evil\n")
    new_report(capsys, root, tmp_path)
    msg = write(tmp_path / "msg.txt", "security: import\n")
    code, out = run(capsys, root, "publish", "--message-file", str(msg))
    assert code == 0 and out["committed"]
    assert not marker.exists()


def test_descriptor_names_may_contain_spaces(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "security"
    assert run(capsys, root, "init", "--access-restricted")[0] == 0
    data = json.loads((root / DESCRIPTOR_NAME).read_text())
    data["state"]["mode"] = "directory"
    data["state"]["open_dir"] = "in progress"
    (root / DESCRIPTOR_NAME).write_text(json.dumps(data))
    assert load(root).state.open_dir == "in progress"
    for bad in ("../up", "a/b", " lead", "trail ", "nul\x00"):
        data["state"]["open_dir"] = bad
        (root / DESCRIPTOR_NAME).write_text(json.dumps(data))
        with pytest.raises(ValueError):
            load(root)


def test_a_bare_number_matching_two_reports_is_ambiguous(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = new_report(capsys, fresh, tmp_path, title="first")
    second = new_report(capsys, fresh, tmp_path, title="second")
    number = int("".join(ch for ch in first if ch.isdigit()))
    tracker = Tracker(fresh, load(fresh))
    # Give the second report the first one's number under a slugged name.
    entry = tracker.resolve(second)
    entry.container.rename(entry.container.with_name(f"{first}-dup"))
    with pytest.raises(TrackerError, match="ambiguous"):
        Tracker(fresh, load(fresh)).resolve(str(number))
    # The full ID still names exactly one report.
    assert Tracker(fresh, load(fresh)).resolve(first).id == first


def test_slugs_with_underscores_resolve_by_bare_id(
    fresh: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ident = new_report(capsys, fresh, tmp_path)
    entry = Tracker(fresh, load(fresh)).resolve(ident)
    entry.container.rename(entry.container.with_name(f"{ident}_xss"))
    assert Tracker(fresh, load(fresh)).resolve(ident).id == f"{ident}_xss"


@pytest.mark.parametrize(
    "raw, items",
    [
        ("[Bob's report, triaged]", ["Bob's report", "triaged"]),
        ('["a \\" , b", c]', ['a " , b', "c"]),
        ("['it''s, here', x]", ["it's, here", "x"]),
        ('[plain, "quoted, comma"]', ["plain", "quoted, comma"]),
    ],
)
def test_inline_lists_split_on_scalar_boundaries(raw: str, items: list[str]) -> None:
    meta, body = md.split(f"---\nlabels: {raw}\n---\n\nBody\n")
    assert meta.values["labels"] == items
    # What the renderer writes back reads the same.
    assert md.split(md.render(meta, body))[0].values["labels"] == items


def test_comment_authors_with_spaces_read_back() -> None:
    trail = sections.render_comment(1, "Jane Doe", "2026-10-17T00:00:00Z", "first", 3)
    trail += "\n" + sections.render_comment(2, "John Q. Public", "2026-10-17T01:00:00Z", "second", 3)
    comments = sections.parse_comments(trail)
    assert [(c.author, c.body) for c in comments] == [("Jane Doe", "first"), ("John Q. Public", "second")]
