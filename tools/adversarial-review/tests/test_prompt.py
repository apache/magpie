#
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
from __future__ import annotations

import dataclasses
import inspect
import os
import subprocess

import pytest

from adversarial_review.prompt import (
    PROMPT_RULES,
    InputError,
    ReviewInput,
    diff_for_branch,
    files_from_diff,
    make_input,
    pr_input,
    render_prompt,
    tracker_warning,
)

DIFF = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"


def test_files_from_diff_keeps_order_and_dedupes():
    diff = DIFF + "diff --git a/docs/a.md b/docs/a.md\n" + DIFF
    assert files_from_diff(diff) == ("app.py", "docs/a.md")


def test_render_prompt_is_exactly_rules_plus_the_three_inputs():
    prompt = render_prompt(make_input(DIFF, "Harden the allowlist", "Deny by default."))
    assert prompt == (
        PROMPT_RULES
        + "\n\nPR title:\n<<<TITLE\nHarden the allowlist\nTITLE>>>\n\n"
        + "PR description:\n<<<BODY\nDeny by default.\nBODY>>>\n\n"
        + "Changed files:\n- app.py\n\n"
        + "Diff:\n<<<DIFF\n"
        + DIFF
        + "\nDIFF>>>\n"
    )


def test_input_builder_accepts_no_other_context():
    """This is what makes the absence of a privacy gate safe: there is no
    parameter through which tracker, mail or advisory text can be passed."""
    assert list(inspect.signature(make_input).parameters) == ["diff", "title", "body", "max_chars"]
    assert [f.name for f in dataclasses.fields(ReviewInput)] == [
        "diff",
        "files",
        "title",
        "body",
        "truncated",
    ]


def test_tracker_shaped_context_never_reaches_the_prompt(git_repo, monkeypatch):
    (git_repo / "tracker-issue.md").write_text(
        "CVE-2026-12345 reported by alice@example.org\n", encoding="utf-8"
    )
    (git_repo / ".apache-magpie-overrides").mkdir()
    (git_repo / ".apache-magpie-overrides" / "project.md").write_text(
        "| `tracker_repo` | `acme/tracker` | private |\n", encoding="utf-8"
    )
    monkeypatch.setenv("TRACKER_BODY", "CVE-2026-12345")
    prompt = render_prompt(make_input(diff_for_branch(git_repo, "main"), "Fix f", "Return 2."))
    assert "app.py" in prompt and "return 2" in prompt
    for private in ("CVE-2026-12345", "alice@example.org", "acme/tracker", "tracker-issue.md"):
        assert private not in prompt


def test_large_diff_is_truncated_with_marker():
    diff = "diff --git a/x b/x\n" + "+" * 500
    inp = make_input(diff, "", "", max_chars=100)
    assert inp.truncated
    assert inp.diff.startswith("diff --git a/x b/x\n")
    assert "diff truncated by adversarial-review" in inp.diff
    assert len(inp.diff) < 250
    assert inp.files == ("x",)


def test_diff_for_branch(git_repo):
    diff = diff_for_branch(git_repo, "main")
    assert "-    return 1" in diff and "+    return 2" in diff


def test_diff_for_branch_bad_base_is_an_input_error(git_repo):
    with pytest.raises(InputError, match="git diff"):
        diff_for_branch(git_repo, "no-such-ref")


def test_pr_input_uses_gh(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make(
        "gh",
        "import json, sys\n"
        f"diff = {DIFF!r}\n"
        "if sys.argv[1:3] == ['pr', 'diff']: print(diff, end='')\n"
        "elif sys.argv[1:3] == ['pr', 'view']: print(json.dumps({'title': 'T', 'body': 'B'}))\n"
        "else: sys.exit(9)\n",
    )
    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    assert pr_input(tmp_path, 7, "acme/product", env) == (DIFF, "T", "B")


def test_tracker_checkout_warns(git_repo):
    subprocess.run(
        ["git", "-C", str(git_repo), "remote", "add", "origin", "git@github.com:acme/tracker.git"], check=True
    )
    overrides = git_repo / ".apache-magpie-overrides"
    overrides.mkdir()
    (overrides / "project.md").write_text("| `tracker_repo` | `acme/tracker` | private |\n", encoding="utf-8")
    warning = tracker_warning(git_repo)
    assert warning is not None and "acme/tracker" in warning


def test_other_checkout_does_not_warn(git_repo):
    subprocess.run(
        ["git", "-C", str(git_repo), "remote", "add", "origin", "https://github.com/acme/product.git"],
        check=True,
    )
    overrides = git_repo / ".apache-magpie-overrides"
    overrides.mkdir()
    (overrides / "project.md").write_text("tracker_repo: acme/tracker\n", encoding="utf-8")
    assert tracker_warning(git_repo) is None


def test_pr_view_with_null_body(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make(
        "gh",
        "import json, sys\n"
        "if sys.argv[1:3] == ['pr', 'diff']: print('', end='')\n"
        "else: print(json.dumps({'title': 'T', 'body': None}))\n",
    )
    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    assert pr_input(tmp_path, 7, None, env) == ("", "T", "")
