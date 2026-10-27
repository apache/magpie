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

"""Where config lives: the personal layer and the git common directory.

The `git_common_dir` and main-checkout vectors below are duplicated, verbatim, in every tool
that carries a copy of the helper (release-config, adversarial-review,
agent-guard, privacy-llm checker, container-gateway, sandbox-lint,
magpie-setup status).  Change them together.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from setup_preflight import layers

# --- git_common_dir: shared vectors -------------------------------------------------


def test_vector_dot_git_directory_is_the_common_dir(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert layers.git_common_dir(tmp_path) == tmp_path / ".git"


def test_vector_worktree_file_with_relative_commondir(tmp_path: Path) -> None:
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    assert layers.git_common_dir(wt) == main / ".git"


def test_vector_worktree_file_with_relative_gitdir(tmp_path: Path) -> None:
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = main / "nested" / "wt"
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: ../../.git/worktrees/wt\n")
    assert layers.git_common_dir(wt) == main / ".git"


def test_vector_worktree_file_with_absolute_commondir(tmp_path: Path) -> None:
    common = tmp_path / "elsewhere.git"
    wt_gitdir = common / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text(f"{common}\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    assert layers.git_common_dir(wt) == common


def test_vector_gitdir_file_without_commondir_is_its_own_common_dir(tmp_path: Path) -> None:
    """A submodule: `.git` points at `.git/modules/<name>`, which has no `commondir`."""
    module = tmp_path / "super" / ".git" / "modules" / "sub"
    module.mkdir(parents=True)
    sub = tmp_path / "super" / "sub"
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git/modules/sub\n")
    assert layers.git_common_dir(sub) == module


def test_vector_not_a_repository(tmp_path: Path) -> None:
    assert layers.git_common_dir(tmp_path) is None


def test_vector_malformed_dot_git_file(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("not a gitdir line\n")
    assert layers.git_common_dir(tmp_path) is None


def test_vector_dangling_gitdir(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text(f"gitdir: {tmp_path / 'gone'}\n")
    assert layers.git_common_dir(tmp_path) is None


# --- the personal layer -------------------------------------------------------------


def test_an_unadopted_repo_keeps_personal_config_in_the_git_dir(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert layers.personal_dir(tmp_path) == tmp_path / ".git" / "apache-magpie"


def test_every_worktree_shares_one_personal_layer(tmp_path: Path) -> None:
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    assert layers.personal_dir(wt) == layers.personal_dir(main) == main / ".git" / "apache-magpie"


def test_an_adopted_repo_keeps_personal_config_in_tree(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".apache-magpie.lock").write_text("method: local\n")
    assert layers.personal_dir(tmp_path) == tmp_path / ".apache-magpie-local"
    assert layers.legacy_local_dir(tmp_path) is None


def _svn_working_copy(root: Path) -> Path:
    admin = root / ".svn"
    admin.mkdir(parents=True)
    (admin / "wc.db").write_bytes(b"")
    return admin


def test_vector_svn_admin_dir_of_the_working_copy_root(tmp_path: Path) -> None:
    admin = _svn_working_copy(tmp_path)
    assert layers.svn_admin_dir(tmp_path) == admin


def test_vector_an_ancestor_dot_svn_is_never_followed(tmp_path: Path) -> None:
    _svn_working_copy(tmp_path)
    sub = tmp_path / "trunk" / "src"
    sub.mkdir(parents=True)
    assert layers.svn_admin_dir(sub) is None


def test_vector_a_dot_svn_without_wc_db_is_not_a_working_copy(tmp_path: Path) -> None:
    (tmp_path / ".svn").mkdir()
    assert layers.svn_admin_dir(tmp_path) is None


def test_an_unadopted_svn_working_copy_keeps_personal_config_in_the_svn_dir(tmp_path: Path) -> None:
    admin = _svn_working_copy(tmp_path)
    assert layers.personal_dir(tmp_path) == admin / "apache-magpie"
    assert layers.config_layers(tmp_path) == [
        admin / "apache-magpie",
        tmp_path / ".apache-magpie-overrides",
    ]


def test_git_wins_over_svn(tmp_path: Path) -> None:
    _svn_working_copy(tmp_path)
    (tmp_path / ".git").mkdir()
    assert layers.personal_dir(tmp_path) == tmp_path / ".git" / "apache-magpie"


def test_no_version_control_keeps_personal_config_in_tree(tmp_path: Path) -> None:
    assert layers.personal_dir(tmp_path) == tmp_path / ".apache-magpie-local"
    assert layers.config_layers(tmp_path) == [
        tmp_path / ".apache-magpie-local",
        tmp_path / ".apache-magpie-overrides",
    ]
    (tmp_path / ".apache-magpie-local").mkdir()
    assert layers.legacy_local_dir(tmp_path) is None


def test_a_legacy_in_tree_dir_is_read_after_the_git_dir_home(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".apache-magpie-local").mkdir()
    assert layers.config_layers(tmp_path) == [
        tmp_path / ".git" / "apache-magpie",
        tmp_path / ".apache-magpie-local",
        tmp_path / ".apache-magpie-overrides",
    ]


def test_resolution_is_first_match_wins(tmp_path: Path) -> None:
    (tmp_path / ".git" / "apache-magpie").mkdir(parents=True)
    (tmp_path / ".apache-magpie-local").mkdir()
    (tmp_path / ".apache-magpie-local" / "a.md").write_text("legacy")
    assert layers.resolve(tmp_path, "a.md") == tmp_path / ".apache-magpie-local" / "a.md"
    (tmp_path / ".git" / "apache-magpie" / "a.md").write_text("home")
    assert layers.resolve(tmp_path, "a.md") == tmp_path / ".git" / "apache-magpie" / "a.md"


def test_resolving_never_creates_the_personal_layer(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    layers.resolve(tmp_path, "project.md")
    layers.describe(tmp_path)
    assert not (tmp_path / ".git" / "apache-magpie").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == [".git"]


def test_the_module_prints_where_each_layer_is(tmp_path: Path, capsys) -> None:
    (tmp_path / ".git").mkdir()
    assert layers.main(["--project-root", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["adopted"] is False
    assert out["personal_dir"] == str(tmp_path / ".git" / "apache-magpie")
    assert out["personal_dir_exists"] is False


# --- the main checkout of a linked worktree: shared vectors -------------------------

LOCAL = ".apache-magpie-local"


def _linked_worktree(tmp_path: Path, *, adopt: bool = True) -> tuple[Path, Path]:
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    if adopt:
        for root in (main, wt):
            (root / ".apache-magpie.lock").write_text("method: local\n")
    return main, wt


def test_vector_main_worktree_of_a_linked_worktree(tmp_path: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    assert layers.main_worktree(wt) == main


def test_vector_main_worktree_of_the_main_checkout_is_none(tmp_path: Path) -> None:
    main, _ = _linked_worktree(tmp_path)
    assert layers.main_worktree(main) is None


def test_vector_main_worktree_of_a_bare_repository_is_none(tmp_path: Path) -> None:
    common = tmp_path / "repo.git"
    wt_gitdir = common / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    assert layers.main_worktree(wt) is None


def test_vector_main_worktree_of_a_submodule_is_none(tmp_path: Path) -> None:
    (tmp_path / "super" / ".git" / "modules" / "sub").mkdir(parents=True)
    sub = tmp_path / "super" / "sub"
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git/modules/sub\n")
    assert layers.main_worktree(sub) is None


def test_vector_main_worktree_outside_a_repository_is_none(tmp_path: Path) -> None:
    assert layers.main_worktree(tmp_path) is None


def test_vector_adopted_worktree_without_its_own_dir_uses_the_main_checkouts(tmp_path: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    (main / LOCAL).mkdir()
    assert layers.personal_layers(wt) == [wt / LOCAL, main / LOCAL]
    assert layers.personal_dir(wt) == main / LOCAL


def test_vector_adopted_worktree_with_its_own_dir_writes_there(tmp_path: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    (main / LOCAL).mkdir()
    (wt / LOCAL).mkdir()
    assert layers.personal_layers(wt) == [wt / LOCAL, main / LOCAL]
    assert layers.personal_dir(wt) == wt / LOCAL


def test_vector_adopted_worktree_with_neither_dir_writes_its_own(tmp_path: Path) -> None:
    _, wt = _linked_worktree(tmp_path)
    assert layers.personal_layers(wt) == [wt / LOCAL]
    assert layers.personal_dir(wt) == wt / LOCAL


def test_vector_a_worktree_falls_back_to_the_main_checkout_file_by_file(tmp_path: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    for root in (main, wt):
        (root / LOCAL).mkdir()
    (main / LOCAL / "a.md").write_text("main")
    (main / LOCAL / "b.md").write_text("main")
    (wt / LOCAL / "a.md").write_text("worktree")

    def first(name: str) -> Path | None:
        return next((p / name for p in layers.config_layers(wt) if (p / name).exists()), None)

    assert first("a.md") == wt / LOCAL / "a.md"
    assert first("b.md") == main / LOCAL / "b.md"


def test_vector_the_main_checkout_does_not_fall_back(tmp_path: Path) -> None:
    main, _ = _linked_worktree(tmp_path)
    assert layers.personal_layers(main) == [main / LOCAL]
    assert layers.personal_dir(main) == main / LOCAL


def test_vector_an_unadopted_worktree_is_unchanged(tmp_path: Path) -> None:
    main, wt = _linked_worktree(tmp_path, adopt=False)
    (main / LOCAL).mkdir()
    assert layers.personal_layers(wt) == [main / ".git" / "apache-magpie"]
    assert layers.personal_dir(wt) == main / ".git" / "apache-magpie"


def test_the_module_reports_the_main_checkout_fallback(tmp_path: Path, capsys) -> None:
    main, wt = _linked_worktree(tmp_path)
    (main / LOCAL).mkdir()
    assert layers.main(["--project-root", str(wt)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["main_worktree"] == str(main)
    assert out["personal_dir"] == str(main / LOCAL)
    assert out["personal_layers"] == [str(wt / LOCAL), str(main / LOCAL)]


# --- every copy of the helper stays identical ---------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
COPIES = (
    "tools/release-config/src/release_config/layers.py",
    "tools/pr-management/src/pr_management/layers.py",
    "tools/adversarial-review/src/adversarial_review/layers.py",
    "tools/privacy-llm/checker/src/checker/layers.py",
    "tools/container-gateway/src/container_gateway/layers.py",
    "tools/sandbox-lint/src/sandbox_lint/layers.py",
    "tools/vetted-ops/src/vetted_ops/layers.py",
    "tools/cve-tool-vulnogram/generate-cve-json/src/generate_cve_json/layers.py",
    "tools/agent-guard/src/agent_guard/__init__.py",
    "plugins/magpie-setup/skills/status/scripts/collect_status.py",
    "plugins/magpie-pr-management/skills/pr-triage/scripts/typed_decision_prefilter.py",
)
SHARED = (
    "_absolute",
    "git_common_dir",
    "svn_admin_dir",
    "unadopted_home",
    "adopted",
    "main_worktree",
    "personal_dir",
    "personal_layers",
)


def _functions(path: Path) -> dict[str, str]:
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            # Docstrings may differ in wording; the code may not.
            body = node.body[1:] if ast.get_docstring(node) else node.body
            found[node.name] = ast.dump(ast.Module(body=body, type_ignores=[]))
    return found


@pytest.mark.skipif(not (REPO_ROOT / "tools" / "release-config").is_dir(), reason="needs the framework tree")
@pytest.mark.parametrize("copy", COPIES)
def test_every_copy_of_the_layer_rule_matches_this_one(copy: str) -> None:
    canonical = _functions(Path(layers.__file__))
    other = _functions(REPO_ROOT / copy)
    for name in SHARED:
        assert other.get(name) == canonical[name], f"{copy}: {name} differs from setup_preflight/layers.py"


@pytest.mark.skipif(
    not (REPO_ROOT / "tools" / "container-gateway").is_dir(), reason="needs the framework tree"
)
def test_the_two_run_dir_copies_match() -> None:
    gateway = _functions(REPO_ROOT / "tools/container-gateway/src/container_gateway/layers.py")
    lint = _functions(REPO_ROOT / "tools/sandbox-lint/src/sandbox_lint/layers.py")
    for name in ("default_run_dir", "run_dir_candidates"):
        assert gateway[name] == lint[name]


# --- the documented PYTHONPATH finds the checker wherever `config` installs it ----

PREFLIGHT_BLOCK = REPO_ROOT / "tools" / "dev" / "preflight-block.md"


def _documented_pythonpath() -> str:
    import re

    match = re.search(r'^PYTHONPATH="([^"]+)"', PREFLIGHT_BLOCK.read_text(encoding="utf-8"), re.M)
    assert match, "the pre-flight block names no PYTHONPATH"
    return match.group(1)


def _block_command() -> str:
    """The block's command line, `PYTHONPATH=… \\` joined with the `python3 …` line."""
    text = PREFLIGHT_BLOCK.read_text(encoding="utf-8")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith('PYTHONPATH="'):
            return line.rstrip("\\").rstrip() + " " + lines[index + 1].strip()
    raise AssertionError("the pre-flight block names no PYTHONPATH")


def _project(tmp_path: Path, vcs: str) -> Path:
    root = tmp_path / "project"
    root.mkdir(parents=True)
    if vcs == "git":
        subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    elif vcs == "svn":
        _svn_working_copy(root)
    return root


def _plant(directory: Path, marker: Path) -> None:
    """A `setup_preflight` package that records it was imported."""
    planted = directory / "setup_preflight"
    planted.mkdir(parents=True)
    code = f"open({str(marker)!r}, 'a').write({str(directory)!r} + '\\n')\n"
    (planted / "__init__.py").write_text(code, encoding="utf-8")
    (planted / "__main__.py").write_text(code + "print('PLANTED')\n", encoding="utf-8")


def _run_block(root: Path, tmp_path: Path, module: str) -> subprocess.CompletedProcess[str]:
    """Run the block's own command, with `-m setup_preflight` swapped for `module`."""
    import os

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path),
        # Never let `git` find a repository above the test project.
        "GIT_CEILING_DIRECTORIES": str(tmp_path),
    }
    command = _block_command()
    head = command.split(" --skill", 1)[0]
    assert head.endswith("python3 -P -m setup_preflight"), head
    script = head.removesuffix("setup_preflight") + module
    return subprocess.run(
        ["sh", "-c", script], cwd=root, env=env, capture_output=True, text=True, check=False
    )


@pytest.mark.skipif(not PREFLIGHT_BLOCK.is_file(), reason="needs the framework tree")
def test_the_block_runs_the_checker_with_dash_p() -> None:
    """`python3 -m` alone would put the opened project ahead of PYTHONPATH."""
    assert " -P -m setup_preflight " in _block_command()


@pytest.mark.skipif(not PREFLIGHT_BLOCK.is_file(), reason="needs the framework tree")
def test_the_block_pythonpath_names_no_in_tree_directory() -> None:
    pythonpath = _documented_pythonpath()
    assert ".apache-magpie-local" not in pythonpath
    assert ":" not in pythonpath, "one directory, the checker_dir"


@pytest.mark.skipif(not PREFLIGHT_BLOCK.is_file(), reason="needs the framework tree")
@pytest.mark.parametrize("vcs", ["git", "svn"])
@pytest.mark.parametrize("adopted", [False, True])
def test_the_block_finds_the_checker_in_its_checker_dir(tmp_path: Path, vcs: str, adopted: bool) -> None:
    """Install the checker where `config` would, then resolve it exactly as the block does."""
    import shutil

    root = _project(tmp_path, vcs)
    if adopted:
        (root / layers.LOCK_NAME).write_text("method: marketplace\n", encoding="utf-8")
    home = layers.checker_home(root)
    assert home is not None
    package = Path(layers.__file__).resolve().parent
    shutil.copytree(package, home / "setup_preflight")
    done = _run_block(root, tmp_path, "setup_preflight.layers")
    assert done.returncode == 0, done.stderr
    assert done.stderr == ""
    described = json.loads(done.stdout)
    assert Path(described["checker_dir"]).resolve() == home.resolve()


@pytest.mark.skipif(not PREFLIGHT_BLOCK.is_file(), reason="needs the framework tree")
@pytest.mark.parametrize("vcs", ["git", "svn", "none"])
@pytest.mark.parametrize("adopted", [False, True])
def test_a_committable_setup_preflight_is_never_imported(tmp_path: Path, vcs: str, adopted: bool) -> None:
    """Pre-flight imports the checker only from paths a repository cannot commit.

    The working-tree root, `.apache-magpie-local/` (adopted or legacy) and a
    `.svn/` a git repository carries are all
    committable, so none of them is ever imported, whatever else is there.
    """
    root = _project(tmp_path, vcs)
    if adopted:
        (root / layers.LOCK_NAME).write_text("method: marketplace\n", encoding="utf-8")
    marker = tmp_path / "planted-ran"
    _plant(root, marker)
    _plant(root / layers.LOCAL_DIR, marker)
    if vcs == "git":
        # A git repository can commit a `.svn/` directory.
        _plant(root / ".svn" / layers.GIT_HOME_NAME, marker)
    done = _run_block(root, tmp_path, "setup_preflight")
    assert not marker.exists(), marker.read_text(encoding="utf-8")
    assert "PLANTED" not in done.stdout
    assert done.returncode != 0, "no checker is installed, so the block must not succeed"


def test_checker_home_is_inside_the_vcs_directory(tmp_path: Path) -> None:
    def home(root: Path) -> Path:
        found = layers.checker_home(root)
        assert found is not None
        return found.resolve()

    git_root = _project(tmp_path / "g", "git")
    assert home(git_root) == (git_root / ".git" / "apache-magpie").resolve()
    (git_root / layers.LOCK_NAME).write_text("method: marketplace\n", encoding="utf-8")
    assert home(git_root) == (git_root / ".git" / "apache-magpie").resolve()
    svn_root = _project(tmp_path / "s", "svn")
    assert home(svn_root) == (svn_root / ".svn" / "apache-magpie").resolve()


def test_no_version_control_has_no_checker_home(tmp_path: Path) -> None:
    root = _project(tmp_path, "none")
    assert layers.checker_home(root) is None
    assert layers.describe(root)["checker_dir"] is None
