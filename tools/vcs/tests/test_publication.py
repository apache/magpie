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

"""Fix-flow choice, the publication scrub, and the scrubbed SVN commit proposal."""

import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from magpie_vcs import GitBackend, SubversionBackend, VCSError, main, publication
from magpie_vcs.publication import PublicationError, added_lines, commit_proposal, fix_flow, scrub

svn_required = pytest.mark.skipif(
    not SubversionBackend.is_available() or shutil.which("svnadmin") is None,
    reason="svn 1.9+ / svnadmin not installed",
)


# -- fix-flow ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("detected", "distributed", "declared", "flow"),
    [
        ("git", True, None, "pull-request"),
        ("git", True, "github", "pull-request"),
        ("svn", False, "asf-svn", "patch-then-commit"),
        ("svn", False, "Subversion", "patch-then-commit"),
        (None, None, "svn", "patch-then-commit"),
        (None, None, "github", "pull-request"),
    ],
)
def test_fix_flow(detected: str | None, distributed: bool | None, declared: str | None, flow: str) -> None:
    result = fix_flow(detected, distributed, declared)
    assert result["flow"] == flow
    if flow == "patch-then-commit":
        assert result["publishes_at"] == ["new-branch", "commit"]
    else:
        assert result["publishes_at"] == ["push"]


def test_fix_flow_refuses_a_working_copy_the_manifest_contradicts() -> None:
    with pytest.raises(PublicationError, match="declares 'asf-svn'"):
        fix_flow("git", True, "asf-svn")


def test_fix_flow_rejects_unknown_declared_value() -> None:
    with pytest.raises(PublicationError, match="unknown source-control value"):
        fix_flow("git", True, "cvs")


def test_fix_flow_needs_something() -> None:
    with pytest.raises(PublicationError):
        fix_flow(None, None, None)


def test_cli_fix_flow_without_working_copy(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-C", str(tmp_path), "fix-flow", "--declared", "asf-svn"]) == 0
    assert json.loads(capsys.readouterr().out)["flow"] == "patch-then-commit"
    assert main(["-C", str(tmp_path), "fix-flow"]) == 2


# -- scrub -------------------------------------------------------------------


def test_scrub_message_terms() -> None:
    result = scrub(message="Fix CVE-2026-00001\n\nThis is a security fix for an XSS vulnerability.")
    terms = {h["term"] for h in result["hits"]}
    assert result["clean"] is False
    assert {"CVE id", "CVE", "security fix", "XSS", "vulnerability"} <= terms


def test_scrub_neutral_message_is_clean() -> None:
    result = scrub(message="Reject request paths that leave the document root\n\nSee SEC-0012.")
    assert result == {"clean": True, "hits": []}


def test_scrub_diff_only_added_lines() -> None:
    diff = (
        "Index: server/core.c\n"
        "===================================================================\n"
        "--- server/core.c\t(revision 5)\n"
        "+++ server/core.c\t(working copy)\n"
        "@@ -1,2 +1,2 @@\n"
        "-/* old advisory wording already public */\n"
        "+/* guard against the path traversal reported privately */\n"
        " int x;\n"
    )
    hits = scrub(diff=diff)["hits"]
    assert [(h["term"], h["file"]) for h in hits] == [("path traversal", "server/core.c")]


def test_added_lines_reads_git_headers() -> None:
    diff = "--- a/x.py\n+++ b/x.py\n@@ -0,0 +1 @@\n+print(1)\n"
    assert added_lines(diff) == [(4, "x.py", "print(1)")]


def test_scrub_branch_name_with_separators() -> None:
    hits = scrub(branch="security-fix-cve-2026-00001")["hits"]
    terms = {h["term"] for h in hits}
    assert {"security fix", "CVE id"} <= terms
    assert scrub(branch="reject-dotdot-paths")["clean"] is True


def test_scrub_extra_term_and_allow() -> None:
    assert scrub(message="Touch advisory.c", allow=["advisory"])["clean"] is True
    hits = scrub(message="Credit to Jane Example", extra_terms=["Jane Example"])["hits"]
    assert [h["term"] for h in hits] == ["Jane Example"]


def test_scrub_verbatim_private_text_on_message_only() -> None:
    private = "The reporter found that the mod_widget handler forwards the raw header to the backend."
    msg = "Stop forwarding: the mod_widget handler forwards the raw header to the backend now trimmed."
    result = scrub(message=msg, private_texts=[private])
    assert [h["term"] for h in result["hits"]] == ["verbatim private text"]
    # The diff may carry an agreed snippet from the private discussion.
    assert scrub(diff=f"+++ a.c\n+{private}\n", private_texts=[private])["clean"] is True


def test_cli_scrub_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".git").mkdir()
    msg = tmp_path / "msg.txt"
    msg.write_text("Tighten header parsing\n")
    assert main(["-C", str(tmp_path), "scrub", "-F", str(msg)]) == 0
    msg.write_text("Fix advisory item\n")
    capsys.readouterr()
    assert main(["-C", str(tmp_path), "scrub", "-F", str(msg)]) == 1
    assert json.loads(capsys.readouterr().out)["hits"][0]["term"] == "advisory"


# -- the commit proposal -------------------------------------------------------


class FakeSvn(SubversionBackend):
    """A centralized backend whose state is given, not read from a server."""

    def __init__(self, root: Path, changes: Sequence[tuple[str, str]], diff: str = "") -> None:
        super().__init__(root)
        self._changes = list(changes)
        self._diff = diff

    def changed_paths(self) -> list[tuple[str, str]]:
        return self._changes

    def diff(self, base: str | None = None, cached: bool = False, paths: Sequence[str] = ()) -> str:
        return self._diff

    def current_branch(self) -> str:
        return "trunk"


def test_proposal_ready_with_gated_commands(tmp_path: Path) -> None:
    (tmp_path / "modules").mkdir()
    (tmp_path / "modules" / "new_test.c").write_text("int test_dotdot(void);\n")
    backend = FakeSvn(
        tmp_path,
        [("modified", "server/core.c"), ("unversioned", "modules/new_test.c"), ("unversioned", "notes.txt")],
        diff="+++ server/core.c\n+if (has_dotdot(path)) return HTTP_BAD_REQUEST;\n",
    )
    result = commit_proposal(
        backend,
        message="Reject request paths containing dot segments",
        message_file="/scratch/msg.txt",
        branch="reject-dot-segments",
        expect=["server/core.c", "modules"],
    )
    assert result["ready"] is True
    assert result["would_commit"] == ["modules/new_test.c", "server/core.c"]
    assert result["left_unversioned"] == ["notes.txt"]
    root = str(tmp_path)
    assert result["commands"] == [
        ["magpie-vcs", "-C", root, "new-branch", "--scrub", "reject-dot-segments"],
        ["magpie-vcs", "-C", root, "stage", "modules/new_test.c"],
        ["magpie-vcs", "-C", root, "commit", "--scrub", "--message-file", "/scratch/msg.txt"],
    ]


def test_proposal_blocks_on_scrub_hit_in_a_new_file(tmp_path: Path) -> None:
    (tmp_path / "t.c").write_text("/* regression test for CVE-2026-00001 */\n")
    backend = FakeSvn(tmp_path, [("unversioned", "t.c")])
    result = commit_proposal(backend, message="Add a test", message_file="m", expect=["t.c"])
    assert result["ready"] is False
    assert result["commands"] == []
    assert result["hits"][0]["file"] == "t.c"


def test_proposal_blocks_on_unrelated_changes(tmp_path: Path) -> None:
    backend = FakeSvn(tmp_path, [("modified", "server/core.c"), ("modified", "docs/manual.xml")])
    result = commit_proposal(backend, message="Tidy", message_file="m", expect=["server/core.c"])
    assert result["ready"] is False
    assert result["unexpected_paths"] == ["docs/manual.xml"]


def test_proposal_blocks_on_conflicts_and_needs_expect(tmp_path: Path) -> None:
    backend = FakeSvn(tmp_path, [("conflicted", "server/core.c")])
    result = commit_proposal(backend, message="Tidy", message_file="m", expect=["server"])
    assert result["blocked_by"] == [
        "the working copy has conflicted, obstructed or incomplete paths",
        "nothing to commit",
    ]
    with pytest.raises(PublicationError, match="--expect"):
        commit_proposal(backend, message="Tidy", message_file="m", expect=[])


def test_proposal_refuses_distributed_backend(tmp_path: Path) -> None:
    with pytest.raises(PublicationError, match="distributed"):
        commit_proposal(GitBackend(tmp_path), message="x", message_file="m", expect=["x"])


def test_svn_changed_paths_parses_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    xml = f"""<?xml version="1.0"?><status><target path=".">
      <entry path="{tmp_path}/a.c"><wc-status item="modified" props="none"/></entry>
      <entry path="b.c"><wc-status item="unversioned" props="none"/></entry>
      <entry path="c"><wc-status item="normal" props="modified"/></entry>
      <entry path="d.c"><wc-status item="external" props="none"/></entry>
    </target></status>"""
    backend = SubversionBackend(tmp_path)
    monkeypatch.setattr(backend, "_svn", lambda *a, **k: xml)
    assert backend.changed_paths() == [("modified", "a.c"), ("unversioned", "b.c"), ("modified", "c")]


def test_changed_paths_is_svn_only(tmp_path: Path) -> None:
    with pytest.raises(VCSError):
        GitBackend(tmp_path).changed_paths()


# -- the gate on the publishing writes ---------------------------------------


def test_commit_scrub_refuses_before_the_vcs_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".svn").mkdir()
    calls: list[str] = []
    monkeypatch.setattr(SubversionBackend, "diff", lambda self, **k: "+++ a.c\n+fix the XSS\n")
    monkeypatch.setattr(SubversionBackend, "commit", lambda self, m: calls.append(m))
    msg = tmp_path / "msg.txt"
    msg.write_text("Escape the title attribute\n")
    assert main(["-C", str(tmp_path), "commit", "--scrub", "-F", str(msg)]) == 3
    assert calls == []
    assert "refused by the publication scrub" in capsys.readouterr().err
    monkeypatch.setattr(SubversionBackend, "diff", lambda self, **k: "+++ a.c\n+escape(title);\n")
    assert main(["-C", str(tmp_path), "commit", "--scrub", "-F", str(msg)]) == 0
    assert calls == ["Escape the title attribute\n"]


def test_new_branch_scrub_refuses_before_the_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".svn").mkdir()
    calls: list[str] = []
    monkeypatch.setattr(SubversionBackend, "create_branch", lambda self, n: calls.append(n))
    assert main(["-C", str(tmp_path), "new-branch", "--scrub", "cve-2026-00001"]) == 3
    assert main(["-C", str(tmp_path), "new-branch", "--scrub", "trim-header"]) == 0
    assert calls == ["trim-header"]


def test_cli_diff_output_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".svn").mkdir()
    monkeypatch.setattr(SubversionBackend, "diff", lambda self, **k: "+++ a.c\n+x\n")
    out = tmp_path / "fix.patch"
    assert main(["-C", str(tmp_path), "diff", "-o", str(out)]) == 0
    assert out.read_text() == "+++ a.c\n+x\n"


def test_module_exports_publication() -> None:
    assert publication.FLOW_PATCH_THEN_COMMIT == "patch-then-commit"


@svn_required
def test_svn_proposal_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repos = tmp_path / "repo"
    subprocess.run(["svnadmin", "create", str(repos)], check=True, capture_output=True)
    url = repos.as_uri()
    subprocess.run(
        ["svn", "mkdir", "--parents", "-m", "layout", f"{url}/p/trunk"], check=True, capture_output=True
    )
    wc = tmp_path / "wc"
    subprocess.run(["svn", "checkout", f"{url}/p/trunk", str(wc)], check=True, capture_output=True)
    (wc / "a.c").write_text("int a;\n")
    msg = tmp_path / "msg.txt"
    msg.write_text("Add a\n")
    assert main(["-C", str(wc), "propose-commit", "-F", str(msg), "--expect", "a.c"]) == 0
    proposal = json.loads(capsys.readouterr().out)
    assert proposal["would_commit"] == ["a.c"]
    assert main(["-C", str(wc), "stage", "a.c"]) == 0
    assert main(["-C", str(wc), "commit", "--scrub", "-F", str(msg)]) == 0
    assert SubversionBackend(wc).is_clean()
