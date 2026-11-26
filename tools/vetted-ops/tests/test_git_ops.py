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
"""`vetted-op-git` against real repositories in a temporary directory."""

from __future__ import annotations

import dataclasses
import fnmatch
import json
import os
import shutil
import stat
import subprocess
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from vetted_ops import checks, git_ops
from vetted_ops.config import Config, ConfigError, account_home
from vetted_ops.git_ops import Git, GitPolicy, GitRefused

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def approved(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty approved-policy directory, so no test reads the account's real one."""
    root = Path(os.path.realpath(tmp_path_factory.mktemp("approved")))
    monkeypatch.setattr(git_ops, "approved_dir", lambda: root)
    return root


def _git(directory: Path, *args: str) -> str:
    env = git_ops.clean_env()
    env.update(
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.org",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.org",
        GIT_CONFIG_GLOBAL=os.devnull,
    )
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-C", str(directory), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()


def _commit(directory: Path, name: str) -> str:
    (directory / name).write_text(name)
    _git(directory, "add", name)
    _git(directory, "commit", "-q", "-m", name)
    return _git(directory, "rev-parse", "HEAD")


@dataclass(frozen=True)
class LocalPolicy(GitPolicy):
    """Pushes to bare repositories on disk instead of a forge."""

    remotes: Path = Path("/nonexistent")

    def push_url(self, repo: str) -> str:
        return str(self.remotes / f"{repo.replace('/', '__')}.git")


@pytest.fixture
def git() -> Git:
    return Git(runner=_runner(os.devnull), protocols=("https", "ssh", "file"))


def _runner(global_config: str) -> git_ops.Runner:
    def runner(argv: list[str], env: dict[str, str], cwd_fd: int | None) -> subprocess.CompletedProcess[str]:
        return git_ops._default_runner(argv, {**env, "GIT_CONFIG_GLOBAL": global_config}, cwd_fd)

    return runner


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = Path(os.path.realpath(tmp_path))
    checkout = root / "checkout"
    checkout.mkdir()
    _git(checkout, "init", "-q", "-b", "main")
    _commit(checkout, "one")
    (root / "worktrees").mkdir()
    remotes = root / "remotes"
    remotes.mkdir()
    for name in ("me__project", "acme__project"):
        _git(remotes, "init", "-q", "--bare", f"{name}.git")
    return checkout


@pytest.fixture
def policy(repo: Path) -> LocalPolicy:
    root = repo.parent
    return LocalPolicy(
        checkouts=(repo,),
        upstream_repo="acme/project",
        fork_repo="me/project",
        upstream_push=("feature-*",),
        worktree_roots=(root / "worktrees",),
        remotes=root / "remotes",
    )


def _remote_head(policy: LocalPolicy, repo: str, branch: str) -> str:
    return _git(Path(policy.push_url(repo)), "rev-parse", f"refs/heads/{branch}")


def _push(
    git: Git,
    policy: GitPolicy,
    repo: Path,
    branch: str,
    target: str,
    remote_branch: str,
    expected: str,
    dry_run: bool = False,
) -> str:
    return git_ops.push_branch(
        git,
        policy,
        {
            "checkout": str(repo),
            "branch": branch,
            "target": target,
            "remote_branch": remote_branch,
            "expected": expected,
        },
        dry_run,
    )


def test_push_creates_then_moves_a_branch_under_a_lease(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "topic")
    first = _commit(repo, "two")
    assert "created" in _push(git, policy, repo, "topic", "fork", "topic", "new")
    assert _remote_head(policy, "me/project", "topic") == first

    _git(repo, "commit", "-q", "--amend", "-m", "rewritten")
    rewritten = _git(repo, "rev-parse", "HEAD")
    _push(git, policy, repo, "topic", "fork", "topic", first)
    assert _remote_head(policy, "me/project", "topic") == rewritten


def test_push_refuses_when_the_remote_moved(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "topic")
    first = _commit(repo, "two")
    _push(git, policy, repo, "topic", "fork", "topic", "new")
    second = _commit(repo, "three")

    with pytest.raises(git_ops.GitFailed):
        _push(git, policy, repo, "topic", "fork", "topic", "0" * 40)
    assert _remote_head(policy, "me/project", "topic") == first
    _push(git, policy, repo, "topic", "fork", "topic", first)
    assert _remote_head(policy, "me/project", "topic") == second


@pytest.mark.parametrize(
    ("target", "remote_branch", "message"),
    [
        pytest.param("fork", "main", "protected", id="protected-on-fork"),
        pytest.param("upstream", "v3-1-test", "protected", id="protected-release-branch"),
        pytest.param("upstream", "topic", "upstream_push", id="upstream-outside-globs"),
        pytest.param("elsewhere", "topic", "target must be", id="unknown-target"),
    ],
)
def test_push_refuses_destinations_outside_the_policy(
    git: Git, policy: LocalPolicy, repo: Path, target: str, remote_branch: str, message: str
) -> None:
    _git(repo, "branch", "topic")
    with pytest.raises(GitRefused, match=message):
        _push(git, policy, repo, "topic", target, remote_branch, "new")


def test_push_to_upstream_inside_the_globs(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _git(repo, "branch", "feature-x")
    _push(git, policy, repo, "feature-x", "upstream", "feature-x", "new")
    assert _remote_head(policy, "acme/project", "feature-x") == _git(repo, "rev-parse", "feature-x")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("core.sshCommand", "touch /tmp/pwned"),
        ("url.file:///tmp/evil.insteadOf", "git@github.com:"),
        ("filter.x.smudge", "touch /tmp/pwned"),
        ("core.fsmonitor", "touch /tmp/pwned"),
        ("remote.origin.receivepack", "touch /tmp/pwned"),
        ("include.path", "/tmp/elsewhere"),
        ("core.hooksPath", "/tmp/hooks"),
    ],
)
def test_repository_config_that_steers_git_is_refused(
    git: Git, policy: LocalPolicy, repo: Path, key: str, value: str
) -> None:
    _git(repo, "branch", "topic")
    _git(repo, "config", key, value)
    with pytest.raises(GitRefused, match="repository configuration"):
        _push(git, policy, repo, "topic", "fork", "topic", "new")


def test_the_main_checkouts_worktree_config_is_checked_for_a_linked_worktree(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    start = _git(repo, "rev-parse", "HEAD")
    path = policy.worktree_roots[0] / "wt"
    git_ops.worktree_add(
        git, policy, {"checkout": str(repo), "path": str(path), "branch": "t", "start": start}, False
    )
    _git(repo, "config", "extensions.worktreeConfig", "true")
    _git(repo, "config", "--worktree", "core.sshCommand", "touch /tmp/pwned")
    with pytest.raises(GitRefused, match=r"core\.sshcommand"):
        git_ops.worktree_remove(git, policy, {"worktree": str(path)}, False)
    assert path.exists()


def test_config_added_after_the_first_check_is_caught_before_the_command(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    _git(repo, "branch", "topic")
    checks = 0
    real_runner = git.runner

    def runner(argv: list[str], env: dict[str, str], cwd_fd: int | None) -> subprocess.CompletedProcess[str]:
        nonlocal checks
        if "--show-scope" in argv:
            checks += 1
            if checks == 2:
                _git(repo, "config", "core.sshCommand", "touch /tmp/pwned")
        return real_runner(argv, env, cwd_fd)

    with pytest.raises(GitRefused, match=r"core\.sshcommand"):
        _push(Git(runner=runner, protocols=git.protocols), policy, repo, "topic", "fork", "topic", "new")
    with pytest.raises(subprocess.CalledProcessError):
        _remote_head(policy, "me/project", "topic")


def test_every_git_call_carries_the_pins(git: Git, repo: Path) -> None:
    argv = git.argv(repo, "status", hooks=True)
    for pin in (*git_ops.PINNED_CONFIG, "core.sshCommand=ssh", "protocol.ssh.allow=always"):
        assert pin in argv
    assert "core.hooksPath=/dev/null" not in argv
    assert "core.hooksPath=/dev/null" in git.argv(repo, "status")


def test_ssh_command_is_pinned_to_the_users_global_one(repo: Path, tmp_path: Path) -> None:
    global_config = tmp_path / "gitconfig"
    global_config.write_text("[core]\n\tsshCommand = my-ssh-wrapper\n")
    git = Git(runner=_runner(str(global_config)))
    assert "core.sshCommand=my-ssh-wrapper" in git.argv(repo, "status")


def test_a_local_transport_is_refused_in_production(policy: LocalPolicy, repo: Path) -> None:
    _git(repo, "branch", "topic")
    with pytest.raises(git_ops.GitFailed):
        _push(Git(runner=_runner(os.devnull)), policy, repo, "topic", "fork", "topic", "new")


def test_reachable_tags_are_not_pushed(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _git(repo, "config", "push.followTags", "true")
    _git(repo, "tag", "-a", "v1", "-m", "v1")
    _git(repo, "branch", "topic")
    _push(git, policy, repo, "topic", "fork", "topic", "new")
    with pytest.raises(subprocess.CalledProcessError):
        _git(Path(policy.push_url("me/project")), "rev-parse", "refs/tags/v1")


def test_attributes_cannot_switch_on_a_filter(policy: LocalPolicy, repo: Path, tmp_path: Path) -> None:
    marker = tmp_path / "filter-ran"
    global_config = tmp_path / "gitconfig"
    global_config.write_text(f'[filter "x"]\n\tsmudge = touch {marker}; cat\n')
    (repo / ".gitattributes").write_text("* filter=x\n")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-q", "-m", "attributes")
    start = _git(repo, "rev-parse", "HEAD")
    git = Git(runner=_runner(str(global_config)), protocols=("https", "ssh", "file"))
    path = policy.worktree_roots[0] / "wt"
    git_ops.worktree_add(
        git, policy, {"checkout": str(repo), "path": str(path), "branch": "t", "start": start}, False
    )
    assert path.exists()
    assert not marker.exists()


def test_clean_env_takes_home_from_the_account_and_drops_xdg() -> None:
    env = git_ops.clean_env({"HOME": "/tmp/fake", "XDG_CONFIG_HOME": "/tmp/fake", "PATH": "/bin"})
    assert env["HOME"] == str(account_home())
    assert "XDG_CONFIG_HOME" not in env


def test_a_remote_named_like_the_destination_cannot_redirect_the_push(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    _git(repo, "branch", "topic")
    destination = policy.push_url("me/project")
    _git(repo, "config", f"remote.{destination}.pushurl", policy.push_url("acme/project"))
    with pytest.raises(GitRefused, match="repository configuration"):
        _push(git, policy, repo, "topic", "fork", "topic", "new")


@pytest.mark.parametrize(("output", "refused"), [("git version 2.41.0", True), ("git version 2.42.0", False)])
def test_git_older_than_2_42_is_refused(repo: Path, output: str, refused: bool) -> None:
    def runner(argv: list[str], env: dict[str, str], cwd_fd: int | None) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")

    git = Git(runner=runner)
    if refused:
        with pytest.raises(GitRefused, match=r"2\.42 or later"):
            git.check_version()
    else:
        git.check_version()


def test_a_root_swapped_for_a_symlink_after_the_checks_cannot_redirect_the_worktree(
    git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    start = _git(repo, "rev-parse", "HEAD")
    root = policy.worktree_roots[0]
    elsewhere = Path(os.path.realpath(tmp_path)) / "elsewhere"
    elsewhere.mkdir()
    real_open_dir = git_ops.open_dir

    def swapping_open_dir(path: Path) -> int:
        fd = real_open_dir(path)
        if path == root:
            # The swap lands after the root was opened, i.e. after every check.
            root.rename(root.with_name("moved-root"))
            root.symlink_to(elsewhere, target_is_directory=True)
        return fd

    git_ops.open_dir = swapping_open_dir
    try:
        git_ops.worktree_add(
            git,
            policy,
            {"checkout": str(repo), "path": str(root / "wt"), "branch": "t", "start": start},
            False,
        )
    finally:
        git_ops.open_dir = real_open_dir
    assert list(elsewhere.iterdir()) == []
    assert (root.with_name("moved-root") / "wt" / "one").exists()


def test_a_symlinked_worktree_path_is_refused(git: Git, policy: LocalPolicy, repo: Path) -> None:
    start = _git(repo, "rev-parse", "HEAD")
    path = policy.worktree_roots[0] / "wt"
    git_ops.worktree_add(
        git, policy, {"checkout": str(repo), "path": str(path), "branch": "t", "start": start}, False
    )
    link = policy.worktree_roots[0] / "link"
    link.symlink_to(path, target_is_directory=True)
    with pytest.raises(GitRefused, match="symlink"):
        git_ops.worktree_sync(git, policy, {"worktree": str(link), "commit": start}, False)


def test_protocols_are_limited_through_the_environment(git: Git) -> None:
    assert git._env()["GIT_ALLOW_PROTOCOL"] == "https:ssh:file"
    assert Git()._env()["GIT_ALLOW_PROTOCOL"] == "https:ssh"


def test_a_copy_of_the_main_checkout_is_not_a_linked_worktree(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    start = _git(repo, "rev-parse", "HEAD")
    copy = policy.worktree_roots[0] / "copy"
    copy.mkdir()
    (copy / "one").write_text("one")
    (copy / ".git").write_text(f"gitdir: {repo / '.git'}\n")
    with pytest.raises(GitRefused, match="registered"):
        git_ops.worktree_sync(git, policy, {"worktree": str(copy), "commit": start}, False)


def test_a_git_directory_swapped_after_validation_is_refused(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    _git(repo, "branch", "topic")
    worktree = git_ops.resolve_worktree(git, str(repo), policy, "checkout")
    (repo / ".git").rename(repo / "real-git")
    (repo / ".git").mkdir()
    with pytest.raises(GitRefused, match="changed since it was validated"):
        git_ops.check_repository_config(git, worktree)


def test_a_linked_worktrees_git_file_is_not_read_after_validation(
    git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    start = _git(repo, "rev-parse", "HEAD")
    path = policy.worktree_roots[0] / "wt"
    git_ops.worktree_add(
        git, policy, {"checkout": str(repo), "path": str(path), "branch": "t", "start": start}, False
    )
    other = Path(os.path.realpath(tmp_path)) / "other"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    worktree = git_ops.resolve_worktree(git, str(path), policy)
    (path / ".git").write_text(f"gitdir: {other / '.git'}\n")
    assert git.run(path, "rev-parse", "--absolute-git-dir").strip() == str(worktree.git_dir)


def test_a_commondir_rewritten_after_validation_is_refused_before_the_command(
    git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    """A linked worktree's common directory comes from a file that can change after the check."""
    start = _git(repo, "rev-parse", "HEAD")
    path = policy.worktree_roots[0] / "wt"
    git_ops.worktree_add(
        git, policy, {"checkout": str(repo), "path": str(path), "branch": "t", "start": start}, False
    )
    other = Path(os.path.realpath(tmp_path)) / "other"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    worktree = git_ops.resolve_worktree(git, str(path), policy)
    git_ops.check_repository_config(git, worktree)  # passes as validated
    (worktree.git_dir / "commondir").write_text(f"{other / '.git'}\n")
    with pytest.raises(GitRefused, match="common git directory"):
        git_ops.check_repository_config(git, worktree)


def test_a_checkout_ancestor_swapped_after_validation_is_refused(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    worktree = git_ops.resolve_worktree(git, str(repo), policy, "checkout")
    moved = repo.with_name("moved")
    repo.rename(moved)
    repo.symlink_to(moved, target_is_directory=True)
    with pytest.raises(GitRefused, match="symlink"):
        git_ops.check_repository_config(git, worktree)


def _track_default_branch(repo: Path, commit: str) -> None:
    _git(repo, "update-ref", "refs/remotes/upstream/main", commit)
    _git(repo, "symbolic-ref", "refs/remotes/upstream/HEAD", "refs/remotes/upstream/main")


def test_moving_a_branch_to_an_empty_rebase_is_refused(git: Git, policy: LocalPolicy, repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _track_default_branch(repo, base)
    _git(repo, "checkout", "-q", "-b", "topic")
    first = _commit(repo, "two")
    _push(git, policy, repo, "topic", "fork", "topic", "new")
    _git(repo, "reset", "-q", "--hard", base)
    with pytest.raises(GitRefused, match="no commits over upstream/main"):
        _push(git, policy, repo, "topic", "fork", "topic", first)
    assert _remote_head(policy, "me/project", "topic") == first


def test_a_branch_with_commits_over_the_default_branch_is_pushed(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    _track_default_branch(repo, _git(repo, "rev-parse", "HEAD"))
    _git(repo, "checkout", "-q", "-b", "topic")
    first = _commit(repo, "two")
    _push(git, policy, repo, "topic", "fork", "topic", "new")
    second = _commit(repo, "three")
    _push(git, policy, repo, "topic", "fork", "topic", first)
    assert _remote_head(policy, "me/project", "topic") == second


def test_inert_repository_config_is_accepted(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _git(repo, "branch", "topic")
    _git(repo, "config", "remote.origin.url", "git@github.com:me/project.git")
    _git(repo, "config", "branch.topic.remote", "origin")
    _git(repo, "config", "user.name", "someone")
    # Written by `gh stack link`, which AGENTS.md recommends; git never reads it.
    _git(repo, "config", "gh-stack.remote", "upstream")
    _push(git, policy, repo, "topic", "fork", "topic", "new")


def _hook(repo: Path, name: str, marker: Path, exit_code: int = 0) -> None:
    hook = repo / ".git" / "hooks" / name
    hook.write_text(f"#!/bin/sh\ntouch {marker}\nexit {exit_code}\n")
    hook.chmod(0o755)


def test_a_push_never_runs_a_pre_push_hook(git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path) -> None:
    """The hook is working-tree code; it runs in the sandbox before the push, never out here."""
    marker = tmp_path / "hook-ran"
    _hook(repo, "pre-push", marker, exit_code=1)
    _git(repo, "branch", "topic")
    _push(git, policy, repo, "topic", "fork", "topic", "new")
    assert not marker.exists()
    assert _remote_head(policy, "me/project", "topic") == _git(repo, "rev-parse", "topic")


def test_a_push_has_no_hooks_parameter() -> None:
    assert "hooks" not in git_ops.OPS["git-push-branch"].params


def test_worktree_operations_never_run_hooks(
    git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    marker = tmp_path / "hook-ran"
    _hook(repo, "post-checkout", marker)
    start = _git(repo, "rev-parse", "HEAD")
    path = policy.worktree_roots[0] / "wt"
    git_ops.worktree_add(
        git, policy, {"checkout": str(repo), "path": str(path), "branch": "t", "start": start}, False
    )
    git_ops.worktree_sync(git, policy, {"worktree": str(path), "commit": start}, False)
    assert not marker.exists()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("expected", "abc123", "full lowercase commit SHA"),
        ("branch", "--upload-pack=x", "may not"),
        ("remote_branch", "a..b", "branch name"),
        ("checkout", "relative/path", "absolute"),
    ],
)
def test_push_validates_parameters(
    git: Git, policy: LocalPolicy, repo: Path, field: str, value: str, message: str
) -> None:
    _git(repo, "branch", "topic")
    params = {
        "checkout": str(repo),
        "branch": "topic",
        "target": "fork",
        "remote_branch": "topic",
        "expected": "new",
        field: value,
    }
    with pytest.raises(GitRefused, match=message):
        git_ops.push_branch(git, policy, params, False)


def test_a_checkout_the_policy_does_not_name_is_refused(
    git: Git, policy: LocalPolicy, tmp_path: Path
) -> None:
    other = Path(os.path.realpath(tmp_path)) / "other"
    other.mkdir()
    _git(other, "init", "-q")
    _commit(other, "x")
    with pytest.raises(GitRefused, match="does not belong"):
        _push(git, policy, other, "master", "fork", "topic", "new")


def test_worktree_add_sync_remove(git: Git, policy: LocalPolicy, repo: Path) -> None:
    start = _git(repo, "rev-parse", "HEAD")
    path = policy.worktree_roots[0] / "wt-topic"
    git_ops.worktree_add(
        git, policy, {"checkout": str(repo), "path": str(path), "branch": "topic", "start": start}, False
    )
    assert _git(path, "rev-parse", "--abbrev-ref", "HEAD") == "topic"

    _git(repo, "checkout", "-q", "-b", "rebased")
    target = _commit(repo, "two")
    message = git_ops.worktree_sync(git, policy, {"worktree": str(path), "commit": target}, False)
    assert start in message
    assert _git(path, "rev-parse", "HEAD") == target

    git_ops.worktree_remove(git, policy, {"worktree": str(path)}, False)
    assert not path.exists()


def test_worktree_sync_refuses_local_changes(git: Git, policy: LocalPolicy, repo: Path) -> None:
    start = _git(repo, "rev-parse", "HEAD")
    path = policy.worktree_roots[0] / "wt"
    git_ops.worktree_add(
        git, policy, {"checkout": str(repo), "path": str(path), "branch": "t", "start": start}, False
    )
    (path / "one").write_text("changed")
    with pytest.raises(GitRefused, match="uncommitted"):
        git_ops.worktree_sync(git, policy, {"worktree": str(path), "commit": start}, False)


def test_worktree_sync_refuses_the_main_checkout(git: Git, policy: LocalPolicy, repo: Path) -> None:
    start = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(GitRefused, match="linked worktrees only"):
        git_ops.worktree_sync(git, policy, {"worktree": str(repo), "commit": start}, False)


@pytest.mark.parametrize(
    "where",
    [
        pytest.param(lambda p, r: r.parent / "outside", id="outside-roots"),
        pytest.param(lambda p, r: p.worktree_roots[0] / "nested" / "wt", id="not-directly-inside"),
        pytest.param(lambda p, r: p.worktree_roots[0] / "-flag", id="bad-name"),
    ],
)
def test_worktree_add_refuses_paths_outside_the_roots(
    git: Git, policy: LocalPolicy, repo: Path, where: Callable[[LocalPolicy, Path], Path]
) -> None:
    start = _git(repo, "rev-parse", "HEAD")
    params = {"checkout": str(repo), "path": str(where(policy, repo)), "branch": "t", "start": start}
    with pytest.raises(GitRefused):
        git_ops.worktree_add(git, policy, params, False)


def test_worktree_add_refuses_an_existing_branch(git: Git, policy: LocalPolicy, repo: Path) -> None:
    start = _git(repo, "rev-parse", "HEAD")
    params = {
        "checkout": str(repo),
        "path": str(policy.worktree_roots[0] / "wt"),
        "branch": "main",
        "start": start,
    }
    with pytest.raises(GitRefused, match="already exists"):
        git_ops.worktree_add(git, policy, params, False)


def test_worktree_remove_keeps_a_worktree_with_changes(git: Git, policy: LocalPolicy, repo: Path) -> None:
    start = _git(repo, "rev-parse", "HEAD")
    path = policy.worktree_roots[0] / "wt"
    git_ops.worktree_add(
        git, policy, {"checkout": str(repo), "path": str(path), "branch": "t", "start": start}, False
    )
    (path / "untracked").write_text("x")
    with pytest.raises(git_ops.GitFailed):
        git_ops.worktree_remove(git, policy, {"worktree": str(path)}, False)
    assert path.exists()


def test_dry_run_changes_nothing(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _git(repo, "branch", "topic")
    printed = _push(git, policy, repo, "topic", "fork", "topic", "new", dry_run=True)
    assert "--force-with-lease=refs/heads/topic:" in printed
    assert "core.hooksPath=/dev/null" in printed
    assert "--no-verify" in printed
    assert "--no-follow-tags" in printed
    with pytest.raises(subprocess.CalledProcessError):
        _remote_head(policy, "me/project", "topic")


def _config(git_table: object) -> Config:
    return Config(
        tracker_repo=None,
        upstream_repo="acme/project",
        workspace=Path("/tmp"),
        values={},
        endpoints={},
        callers={},
        git=git_table,
    )


def test_git_policy_defaults_and_protected_branches(tmp_path: Path) -> None:
    checkout = Path(os.path.realpath(tmp_path))
    policy = git_ops.git_policy(_config({"checkouts": [str(checkout)], "protected": ["prod"]}))
    assert policy.push_url("acme/project") == "git@github.com:acme/project.git"
    assert git_ops.is_protected("prod", policy)
    assert git_ops.is_protected("main", policy)
    assert not policy.upstream_push


@pytest.mark.parametrize(
    "table",
    [
        pytest.param(None, id="no-table"),
        pytest.param({"checkouts": []}, id="no-checkouts"),
        pytest.param({"checkouts": ["relative"]}, id="relative-checkout"),
        pytest.param({"checkouts": ["/"], "fork": "not a repo"}, id="bad-fork"),
        pytest.param({"checkouts": ["/"], "transport": "ftp"}, id="bad-transport"),
        # `$` also matches before a final newline; each value must match whole.
        pytest.param({"checkouts": ["/"], "fork": "me/project\n"}, id="fork-trailing-newline"),
        pytest.param({"checkouts": ["/"], "host": "github.com\n"}, id="host-trailing-newline"),
        pytest.param({"checkouts": ["/"], "upstream_remote": "upstream\n"}, id="remote-trailing-newline"),
        pytest.param({"checkouts": ["/"], "pr_base": "main\n"}, id="pr-base-trailing-newline"),
    ],
)
def test_git_policy_refuses_malformed_tables(table: object) -> None:
    with pytest.raises(ConfigError):
        git_ops.git_policy(_config(table))


def _operator(approved: Path, text: str) -> None:
    (approved / git_ops.OPERATOR_GIT_FILE).write_text(text)


def test_operator_table_alone_supplies_the_git_values(tmp_path: Path, approved: Path) -> None:
    checkout = Path(os.path.realpath(tmp_path))
    _operator(approved, f'["acme/project"]\ncheckouts = ["{checkout}"]\nfork = "me/project"\n')
    policy = git_ops.git_policy(_config(None))
    assert policy.checkouts == (checkout,)
    assert policy.fork_repo == "me/project"
    assert not policy.upstream_push
    assert policy.pr_base == "main"


def test_operator_values_override_the_shared_policy(tmp_path: Path, approved: Path) -> None:
    root = Path(os.path.realpath(tmp_path))
    (root / "mine").mkdir()
    (root / "worktrees").mkdir(mode=0o700)
    shared = {
        "checkouts": [str(root)],
        "fork": "someone/project",
        "upstream_push": ["ci-*"],
        "pr_base": "develop",
        "protected": ["prod"],
    }
    _operator(
        approved,
        '["acme/project"]\n'
        f'checkouts = ["{root / "mine"}"]\n'
        'fork = "me/project"\n'
        f'worktree_roots = ["{root / "worktrees"}"]\n'
        'protected = ["staging"]\n',
    )
    policy = git_ops.git_policy(_config(shared))
    assert policy.checkouts == (root / "mine",)
    assert policy.fork_repo == "me/project"
    assert policy.worktree_roots == (root / "worktrees",)
    assert policy.upstream_push == ("ci-*",)
    assert policy.pr_base == "develop"
    assert git_ops.is_protected("prod", policy)
    assert git_ops.is_protected("staging", policy)


def test_describe_git_names_where_each_value_came_from(tmp_path: Path, approved: Path) -> None:
    root = Path(os.path.realpath(tmp_path))
    _operator(approved, f'["acme/project"]\ncheckouts = ["{root}"]\nfork = "me/project"\n')
    config = _config({"pr_base": "develop", "protected": ["prod"]})
    text = git_ops.describe_git(config, git_ops.git_policy(config))
    operator_file = str(approved / git_ops.OPERATOR_GIT_FILE)
    assert f"fork = 'me/project'  # {operator_file}" in text
    assert "pr_base = 'develop'  # policy" in text
    assert "upstream_remote = 'upstream'  # default" in text
    assert "protected += ['prod']  # policy" in text


def test_operator_table_for_another_upstream_is_ignored(tmp_path: Path, approved: Path) -> None:
    _operator(approved, f'["other/repo"]\ncheckouts = ["{os.path.realpath(tmp_path)}"]\n')
    with pytest.raises(ConfigError, match="no \\[git\\] values for acme/project"):
        git_ops.git_policy(_config(None))


@pytest.mark.parametrize("key", ["upstream_push", "pr_base", "host", "bogus"])
def test_operator_table_may_not_set_project_keys(tmp_path: Path, approved: Path, key: str) -> None:
    _operator(approved, f'["acme/project"]\ncheckouts = ["{os.path.realpath(tmp_path)}"]\n{key} = "x"\n')
    with pytest.raises(ConfigError, match=f"may not set {key}"):
        git_ops.git_policy(_config(None))


def test_operator_file_through_a_symlink_is_refused(tmp_path: Path, approved: Path) -> None:
    real = tmp_path / "elsewhere.toml"
    real.write_text(f'["acme/project"]\ncheckouts = ["{os.path.realpath(tmp_path)}"]\n')
    (approved / git_ops.OPERATOR_GIT_FILE).symlink_to(real)
    with pytest.raises(ConfigError):
        git_ops.git_policy(_config(None))


@pytest.mark.parametrize("mode", [0o770, 0o777])
def test_worktree_root_writable_by_others_is_refused(tmp_path: Path, mode: int) -> None:
    root = Path(os.path.realpath(tmp_path))
    shared = root / "shared"
    shared.mkdir()
    shared.chmod(mode)
    with pytest.raises(ConfigError, match="writable by others"):
        git_ops.git_policy(_config({"checkouts": [str(root)], "worktree_roots": [str(shared)]}))


def test_missing_worktree_root_is_refused(tmp_path: Path) -> None:
    root = Path(os.path.realpath(tmp_path))
    with pytest.raises(ConfigError, match="does not exist"):
        git_ops.git_policy(_config({"checkouts": [str(root)], "worktree_roots": [str(root / "nope")]}))


def test_clean_env_drops_git_variables() -> None:
    env = git_ops.clean_env({"PATH": "/bin", "GIT_SSH_COMMAND": "evil", "GIT_DIR": "/x"})
    assert env == {"PATH": "/bin", "HOME": str(account_home()), "GIT_TERMINAL_PROMPT": "0"}


def test_parse_config_scopes_handles_both_separators() -> None:
    assert git_ops.parse_config_scopes("local\x00core.bare\x00global\x00user.name\x00") == [
        ("local", "core.bare"),
        ("global", "user.name"),
    ]
    assert git_ops.parse_config_scopes("local\tcore.bare\x00") == [("local", "core.bare")]


class _ExplodingGit(Git):
    """Fails the test the moment anything would run git."""

    def __init__(self) -> None:
        super().__init__(runner=_runner(os.devnull), protocols=("https", "ssh", "file"))

    def run(self, *args: object, **kwargs: object) -> str:
        raise AssertionError("a dry run against an unapproved policy ran git")

    def ok(self, *args: object, **kwargs: object) -> bool:
        raise AssertionError("a dry run against an unapproved policy ran git")


def test_a_dry_run_against_an_unapproved_policy_runs_no_git(
    policy: LocalPolicy, repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Even read-only git, outside the sandbox, is steered by the policy: an unapproved one runs none."""
    config = dataclasses.replace(_config({}), callers={"skill": frozenset({"git-push-branch"})})
    loads: list[bool] = []

    def fake_load(*, approved_only: bool = False, **_: object) -> Config:
        loads.append(approved_only)
        if approved_only:
            raise ConfigError("the policy is not an approved copy")
        return config

    monkeypatch.setattr(git_ops, "load", fake_load)
    monkeypatch.setattr(git_ops, "git_policy", lambda _config: policy)
    argv = ["--caller", "skill", "--dry-run", "git-push-branch", str(repo), "topic", "fork", "topic", "new"]
    assert git_ops.main(argv, git=_ExplodingGit()) == git_ops.EXIT_OK
    assert loads == [True, False]  # the approved policy is always tried first
    assert "no git command was run" in capsys.readouterr().out


# The longest prefix of `--caller`, spelled by slicing so the spell checker passes it.
CALLER_ONE_SHORT = "--caller"[:-1]


@pytest.mark.parametrize(
    "spelling",
    [
        ["--ca", "skill"],
        ["--call", "skill"],
        [CALLER_ONE_SHORT, "skill"],
        ["--call=skill"],
        ["--caller", "skill", "--call=other"],
        ["--caller", "skill", CALLER_ONE_SHORT, "other"],
        ["--caller", "skill", "--dry"],
    ],
)
def test_abbreviated_long_options_are_not_accepted(
    spelling: list[str], repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every long option is matched exactly, as the `--caller` count assumes; argparse refuses a prefix."""
    argv = [*spelling, "git-push-branch", str(repo), "topic", "fork", "topic", "new"]
    with pytest.raises(SystemExit) as exc:
        git_ops.main(argv, git=_ExplodingGit())
    assert exc.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


@pytest.mark.parametrize("caller", [["--caller", "skill"], ["--caller=skill"]])
def test_exact_caller_spellings_still_parse(
    caller: list[str], policy: LocalPolicy, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = dataclasses.replace(_config({}), callers={"skill": frozenset({"git-push-branch"})})

    def fake_load(*, approved_only: bool = False, **_: object) -> Config:
        if approved_only:
            raise ConfigError("the policy is not an approved copy")
        return config

    monkeypatch.setattr(git_ops, "load", fake_load)
    monkeypatch.setattr(git_ops, "git_policy", lambda _config: policy)
    argv = [*caller, "--dry-run", "git-push-branch", str(repo), "topic", "fork", "topic", "new"]
    assert git_ops.main(argv, git=_ExplodingGit()) == git_ops.EXIT_OK


def test_checks_refuses_abbreviated_options(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        checks.main(["--h", str(tmp_path), str(tmp_path / "paths")])
    assert exc.value.code == 2


def test_a_real_run_against_an_unapproved_policy_is_refused(
    policy: LocalPolicy, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_load(*, approved_only: bool = False, **_: object) -> Config:
        raise ConfigError("the policy is not an approved copy")

    monkeypatch.setattr(git_ops, "load", fake_load)
    argv = ["--caller", "skill", "git-push-branch", str(repo), "topic", "fork", "topic", "new"]
    assert git_ops.main(argv, git=_ExplodingGit()) == git_ops.EXIT_POLICY


def _is_open(fd: int) -> bool:
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True


def test_anchor_closes_a_passed_descriptor_for_a_path_it_already_holds(git: Git, tmp_path: Path) -> None:
    path = Path(os.path.realpath(tmp_path))
    first = git.anchor(path)
    second = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    assert git.anchor(path, second) == first
    assert not _is_open(second)
    assert _is_open(first)
    git.close()
    assert not _is_open(first)


def test_anchor_keeps_a_passed_descriptor_for_a_new_path_until_close(git: Git, tmp_path: Path) -> None:
    path = Path(os.path.realpath(tmp_path))
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    assert git.anchor(path, fd) == fd
    assert git.anchor(path, fd) == fd
    assert _is_open(fd)
    git.close()
    assert not _is_open(fd)


# --- stage, commit, fetch, pull request -------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    path = Path(os.path.realpath(tmp_path)) / "workspace"
    path.mkdir(mode=0o700)
    return path


@pytest.fixture
def wpolicy(policy: LocalPolicy, workspace: Path) -> LocalPolicy:
    return dataclasses.replace(policy, workspace=workspace)


def _linked(git: Git, policy: GitPolicy, repo: Path, branch: str = "topic") -> Path:
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "user.email", "t@example.org")
    path = policy.worktree_roots[0] / branch
    start = _git(repo, "rev-parse", "HEAD")
    git_ops.worktree_add(
        git, policy, {"checkout": str(repo), "path": str(path), "branch": branch, "start": start}, False
    )
    return path


def _file(workspace: Path, name: str, text: str) -> str:
    path = workspace / name
    path.write_text(text)
    return str(path)


def _checked(wt: Path, paths_file: str) -> None:
    """What `vetted-op-checks` does in the sandbox: run the checks, record the content."""
    checks.record(wt, Path(paths_file))


def test_stage_and_commit_a_listed_change(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path
) -> None:
    wt = _linked(git, wpolicy, repo)
    (wt / "new.txt").write_text("new")
    (wt / "other.txt").write_text("not listed")
    paths = _file(workspace, "p", "new.txt\n")
    _checked(wt, paths)
    out = git_ops.stage_paths(git, wpolicy, {"worktree": str(wt), "paths_file": paths}, False)
    assert "staged 1 path" in out
    assert _git(wt, "diff", "--cached", "--name-only") == "new.txt"
    message = _file(workspace, "m", "feat: add new\n\nBody line.\n")
    out = git_ops.commit_staged(git, wpolicy, {"worktree": str(wt), "message_file": message}, False)
    assert out.startswith("committed ") and "on topic" in out
    assert _git(wt, "log", "-1", "--format=%B").strip() == "feat: add new\n\nBody line."
    assert _git(wt, "status", "--porcelain") == "?? other.txt"


def test_stage_uses_literal_pathspecs(git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path) -> None:
    wt = _linked(git, wpolicy, repo)
    (wt / "a.txt").write_text("a")
    paths = _file(workspace, "p", "*.txt\n")
    with pytest.raises(git_ops.GitFailed):
        git_ops.stage_paths(git, wpolicy, {"worktree": str(wt), "paths_file": paths}, False)
    assert _git(wt, "diff", "--cached", "--name-only") == ""


@pytest.mark.parametrize("bad", ["../escape", "/etc/passwd", "-A", ":(glob)*", ".git/config", "a/../../b"])
def test_stage_refuses_paths_outside_the_worktree(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path, bad: str
) -> None:
    wt = _linked(git, wpolicy, repo)
    paths = _file(workspace, "p", bad)
    with pytest.raises(GitRefused):
        git_ops.stage_paths(git, wpolicy, {"worktree": str(wt), "paths_file": paths}, False)


def test_stage_refuses_a_list_outside_the_workspace(
    git: Git, wpolicy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    wt = _linked(git, wpolicy, repo)
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("one.txt\n")
    with pytest.raises(GitRefused, match="workspace"):
        git_ops.stage_paths(git, wpolicy, {"worktree": str(wt), "paths_file": str(outside)}, False)


def test_commit_refuses_with_nothing_staged(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path
) -> None:
    wt = _linked(git, wpolicy, repo)
    message = _file(workspace, "m", "x")
    with pytest.raises(GitRefused, match="nothing is staged"):
        git_ops.commit_staged(git, wpolicy, {"worktree": str(wt), "message_file": message}, False)


def test_commit_refuses_a_protected_branch(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path
) -> None:
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "user.email", "t@example.org")
    (repo / "x.txt").write_text("x")
    _git(repo, "add", "x.txt")
    message = _file(workspace, "m", "x")
    with pytest.raises(GitRefused, match="protected"):
        git_ops.commit_staged(git, wpolicy, {"worktree": str(repo), "message_file": message}, False)


def test_commit_refuses_an_empty_message(git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path) -> None:
    wt = _linked(git, wpolicy, repo)
    message = _file(workspace, "m", "  \n")
    with pytest.raises(GitRefused, match="empty"):
        git_ops.commit_staged(git, wpolicy, {"worktree": str(wt), "message_file": message}, False)


def test_commit_runs_no_hook(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path, tmp_path: Path
) -> None:
    wt = _linked(git, wpolicy, repo)
    marker = tmp_path / "hook-ran"
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    hook.chmod(0o755)
    (wt / "h.txt").write_text("h")
    paths = _file(workspace, "p", "h.txt")
    _checked(wt, paths)
    git_ops.stage_paths(git, wpolicy, {"worktree": str(wt), "paths_file": paths}, False)
    message = _file(workspace, "m", "msg")
    git_ops.commit_staged(git, wpolicy, {"worktree": str(wt), "message_file": message}, False)
    assert not marker.exists()


def _stage(git: Git, policy: GitPolicy, wt: Path, paths: str) -> None:
    git_ops.stage_paths(git, policy, {"worktree": str(wt), "paths_file": paths}, False)


def _commit_op(git: Git, policy: GitPolicy, wt: Path, workspace: Path) -> str:
    message = _file(workspace, "m", "msg")
    return git_ops.commit_staged(git, policy, {"worktree": str(wt), "message_file": message}, False)


def test_commit_refuses_a_change_the_checks_never_saw(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path
) -> None:
    """No hook runs out here, so nothing is committed that the sandboxed checks did not pass."""
    wt = _linked(git, wpolicy, repo)
    (wt / "a.txt").write_text("a")
    _stage(git, wpolicy, wt, _file(workspace, "p", "a.txt"))
    with pytest.raises(GitRefused, match="no checks were recorded"):
        _commit_op(git, wpolicy, wt, workspace)


def test_commit_refuses_content_changed_after_the_checks(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path
) -> None:
    wt = _linked(git, wpolicy, repo)
    (wt / "a.txt").write_text("checked")
    paths = _file(workspace, "p", "a.txt")
    _checked(wt, paths)
    (wt / "a.txt").write_text("edited after the checks")
    _stage(git, wpolicy, wt, paths)
    with pytest.raises(GitRefused, match=r"did not pass these staged paths.*a\.txt"):
        _commit_op(git, wpolicy, wt, workspace)


def test_commit_refuses_a_staged_path_the_checks_did_not_list(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path
) -> None:
    wt = _linked(git, wpolicy, repo)
    (wt / "a.txt").write_text("a")
    (wt / "b.txt").write_text("b")
    _checked(wt, _file(workspace, "p", "a.txt"))
    _stage(git, wpolicy, wt, _file(workspace, "q", "a.txt\nb.txt"))
    with pytest.raises(GitRefused, match=r"b\.txt"):
        _commit_op(git, wpolicy, wt, workspace)


def test_commit_accepts_a_checked_deletion(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path
) -> None:
    wt = _linked(git, wpolicy, repo)
    tracked = _git(wt, "ls-files").splitlines()[0]
    (wt / tracked).unlink()
    paths = _file(workspace, "p", tracked)
    _checked(wt, paths)
    _stage(git, wpolicy, wt, paths)
    assert _commit_op(git, wpolicy, wt, workspace).startswith("committed ")


def test_a_record_outside_the_policy_workspace_does_not_count(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path, tmp_path: Path
) -> None:
    wt = _linked(git, wpolicy, repo)
    (wt / "a.txt").write_text("a")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "p").write_text("a.txt")
    checks.record(wt, elsewhere / "p")
    _stage(git, wpolicy, wt, _file(workspace, "p", "a.txt"))
    with pytest.raises(GitRefused, match="no checks were recorded"):
        _commit_op(git, wpolicy, wt, workspace)


def test_a_record_reached_through_a_symlink_is_refused(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path, tmp_path: Path
) -> None:
    wt = _linked(git, wpolicy, repo)
    (wt / "a.txt").write_text("a")
    paths = _file(workspace, "p", "a.txt")
    real = checks.record(wt, Path(paths))
    moved = tmp_path / "moved.json"
    real.rename(moved)
    real.symlink_to(moved)
    _stage(git, wpolicy, wt, paths)
    with pytest.raises(GitRefused, match="cannot be read"):
        _commit_op(git, wpolicy, wt, workspace)


def _fake_prek(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    ran = tmp_path / "prek-args"
    prek = bin_dir / "prek"
    prek.write_text(f'#!/bin/sh\necho "$@" > {ran}\nexit {exit_code}\n')
    prek.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    return ran


def test_the_checks_run_prek_on_the_listed_paths(
    git: Git,
    wpolicy: LocalPolicy,
    repo: Path,
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wt = _linked(git, wpolicy, repo)
    (wt / ".pre-commit-config.yaml").write_text("repos: []\n")
    (wt / "a.txt").write_text("a")
    ran = _fake_prek(tmp_path, monkeypatch, 0)
    record = json.loads(checks.record(wt, Path(_file(workspace, "p", "a.txt"))).read_text())
    assert ran.read_text().split() == ["run", "--files", "a.txt"]
    assert record["checks"] == "prek"


def test_failing_checks_record_nothing(
    git: Git,
    wpolicy: LocalPolicy,
    repo: Path,
    workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wt = _linked(git, wpolicy, repo)
    (wt / ".pre-commit-config.yaml").write_text("repos: []\n")
    (wt / "a.txt").write_text("a")
    _fake_prek(tmp_path, monkeypatch, 1)
    paths = _file(workspace, "p", "a.txt")
    assert checks.main([str(wt), paths]) == 1
    assert not checks.stamp_path(workspace, wt).exists()


def _unreadable_git_dir(tmp_path: Path) -> Path:
    """A worktree whose `.git` points where nothing can be read, as a site checkout the sandbox denies."""
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {tmp_path / 'denied' / '.git' / 'worktrees' / '-'}\n")
    return wt


def test_checks_without_a_readable_git_dir_record_git_s_own_blob_ids(
    tmp_path: Path, workspace: Path, repo: Path
) -> None:
    """No hooks configured: the record's ids are computed in-process and equal git's."""
    wt = _unreadable_git_dir(tmp_path)
    (wt / "content").mkdir()
    (wt / "content" / "a.json").write_text('{"a": 1}\n')
    assert checks.unreadable_git_dir(wt) is not None
    record = json.loads(
        checks.record(wt, Path(_file(workspace, "p", "content/a.json\ngone.txt"))).read_text()
    )
    assert record["checks"] == "none"
    (repo / "probe.json").write_text('{"a": 1}\n')
    assert record["files"]["content/a.json"] == _git(repo, "hash-object", "--no-filters", "probe.json")
    assert record["files"]["gone.txt"] == checks.DELETED


def test_configured_checks_refuse_without_a_readable_git_dir(
    tmp_path: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hook manager runs git: with the git directory out of reach the checks refuse, never pass unchecked."""
    wt = _unreadable_git_dir(tmp_path)
    (wt / ".pre-commit-config.yaml").write_text("repos: []\n")
    (wt / "a.txt").write_text("a")
    ran = _fake_prek(tmp_path, monkeypatch, 0)
    paths = _file(workspace, "p", "a.txt")
    assert checks.main([str(wt), paths]) == 1
    assert not ran.exists()
    assert not checks.stamp_path(workspace, wt).exists()


def test_site_hooks_are_recorded_as_skipped_only_when_asked(
    tmp_path: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wt = _unreadable_git_dir(tmp_path)
    (wt / ".pre-commit-config.yaml").write_text("repos: []\n")
    (wt / "a.txt").write_text("a")
    ran = _fake_prek(tmp_path, monkeypatch, 0)
    paths = _file(workspace, "p", "a.txt")
    assert checks.main([str(wt), paths]) == 1  # without the opt-in: refused
    assert checks.main([str(wt), paths, "--skip-site-hooks"]) == 0
    assert not ran.exists()
    record = json.loads(checks.stamp_path(workspace, wt).read_text())
    assert record["checks"] == checks.SITE_HOOKS_SKIPPED
    assert record["files"]["a.txt"] == checks.blob_id(b"a")


def _skipped_hooks_commit(
    git: Git, policy: LocalPolicy, repo: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> str:
    """Stage and commit a change whose checks record says the site's hooks were skipped."""
    wt = _linked(git, policy, repo)
    (wt / ".pre-commit-config.yaml").write_text("repos: []\n")
    (wt / "security").mkdir()
    (wt / "security" / "a.json").write_text("{}\n")
    paths = _file(workspace, "p", "security/a.json\n")
    # As in a ~/.cache worktree of a checkout the sandbox denies.
    monkeypatch.setattr(checks, "unreadable_git_dir", lambda _wt: tmp_git_dir)
    checks.record(wt, Path(paths), skip_site_hooks=True)
    git_ops.stage_paths(git, policy, {"worktree": str(wt), "paths_file": paths}, False)
    message = _file(workspace, "m", "Add a record\n")
    return git_ops.commit_staged(git, policy, {"worktree": str(wt), "message_file": message}, False)


tmp_git_dir = Path("/nonexistent/.git/worktrees/-")


def test_commit_accepts_skipped_site_hooks_under_a_site_policy_that_opts_in(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = dataclasses.replace(
        wpolicy, published_terms=("CVE",), published_paths=("security",), site_hooks="skip"
    )
    assert _skipped_hooks_commit(git, site, repo, workspace, monkeypatch).startswith("committed ")


def test_commit_refuses_skipped_site_hooks_without_the_opt_in(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(GitRefused, match="site's hooks were skipped"):
        _skipped_hooks_commit(git, wpolicy, repo, workspace, monkeypatch)


def test_site_hooks_belong_to_a_records_site_policy_only(tmp_path: Path, approved: Path) -> None:
    checkout = str(Path(os.path.realpath(tmp_path)))
    site = {"checkouts": [checkout], "published_terms": ["CVE"], "published_paths": ["security"]}
    assert git_ops.git_policy(_config({**site, "site_hooks": "skip"})).site_hooks == "skip"
    assert git_ops.git_policy(_config(site)).site_hooks is None
    with pytest.raises(ConfigError, match="records-site policy"):
        git_ops.git_policy(_config({"checkouts": [checkout], "site_hooks": "skip"}))
    with pytest.raises(ConfigError, match='may only be "skip"'):
        git_ops.git_policy(_config({**site, "site_hooks": "off"}))
    _operator(approved, f'["acme/project"]\ncheckouts = ["{checkout}"]\nsite_hooks = "skip"\n')
    with pytest.raises(ConfigError, match="may not set site_hooks"):
        git_ops.git_policy(_config(site))


def test_a_readable_linked_worktree_still_uses_git(git: Git, wpolicy: LocalPolicy, repo: Path) -> None:
    assert checks.unreadable_git_dir(_linked(git, wpolicy, repo)) is None


def test_the_checks_command_is_never_excluded_from_the_sandbox() -> None:
    """It runs the working tree's hooks; out of the sandbox it would be the very escape it prevents."""
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())
    template = REPO_ROOT / "tools" / "agent-isolation" / "claude-settings.local.template.json"
    excluded = [
        *settings.get("sandbox", {}).get("excludedCommands", []),
        *json.loads(template.read_text()).get("sandbox", {}).get("excludedCommands", []),
    ]
    for base in ("~/.claude/magpie/vetted-ops", "~/.cache/apache-magpie/vetted-ops/current"):
        for launcher in ("uvx --from", "uv run --project"):
            command = f"{launcher} {base} {checks.PROG} /wt /ws/p"
            assert not [p for p in excluded if fnmatch.fnmatchcase(command, p)], command


def test_fetch_writes_the_upstream_remote_tracking_ref(git: Git, wpolicy: LocalPolicy, repo: Path) -> None:
    upstream = Path(wpolicy.push_url("acme/project"))
    _git(repo, "push", "-q", str(upstream), "HEAD:refs/heads/main")
    head = _git(repo, "rev-parse", "HEAD")
    out = git_ops.fetch_upstream(git, wpolicy, {"checkout": str(repo), "branch": "main"}, False)
    assert "refs/remotes/upstream/main" in out
    assert _git(repo, "rev-parse", "refs/remotes/upstream/main") == head


@dataclass
class FakeGh:
    calls: list[tuple[list[str], str]] = dataclasses.field(default_factory=list)

    def __call__(self, argv: list[str], env: dict[str, str], stdin: str) -> subprocess.CompletedProcess[str]:
        self.calls.append((argv, stdin))
        return subprocess.CompletedProcess(argv, 0, "https://github.com/acme/project/pull/7\n", "")


def _pr(
    git: Git, policy: GitPolicy, repo: Path, workspace: Path, title: str, body: str, branch: str = "topic"
) -> str:
    return git_ops.pr_create(
        git,
        policy,
        {
            "checkout": str(repo),
            "branch": branch,
            "title": title,
            "body_file": _file(workspace, "b", body),
        },
        False,
    )


def test_pr_create_opens_from_the_fork_against_pr_base(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path
) -> None:
    fake = FakeGh()
    git.gh_runner = fake
    out = _pr(git, wpolicy, repo, workspace, "feat: neat thing", "Does a neat thing.\n")
    assert "pull/7" in out
    argv, stdin = fake.calls[0]
    assert "repos/acme/project/pulls" in argv
    assert "head=me:topic" in argv and "base=main" in argv and "title=feat: neat thing" in argv
    assert stdin == "Does a neat thing.\n"


@pytest.mark.parametrize(("title", "body"), [("fix CVE-2026-1234", "ok"), ("ok", "closes the advisory")])
def test_pr_create_refuses_never_publish_terms(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path, title: str, body: str
) -> None:
    fake = FakeGh()
    git.gh_runner = fake
    with pytest.raises(GitRefused, match="never published"):
        _pr(git, wpolicy, repo, workspace, title, body)
    assert not fake.calls


def test_pr_create_refuses_a_protected_head_and_a_missing_fork(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path
) -> None:
    git.gh_runner = FakeGh()
    with pytest.raises(GitRefused, match="protected"):
        _pr(git, wpolicy, repo, workspace, "t", "b", branch="main")
    with pytest.raises(GitRefused, match=r"no \[git\] fork"):
        _pr(git, dataclasses.replace(wpolicy, fork_repo=None), repo, workspace, "t", "b")


@dataclass
class FakeForge:
    """Answers the compare of the pull request's branch, then opens the pull request."""

    files: list[str]
    head: str
    calls: list[list[str]] = dataclasses.field(default_factory=list)

    def __call__(self, argv: list[str], env: dict[str, str], stdin: str) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        if any("/compare/" in a for a in argv):
            out = json.dumps({"files": self.files, "head": self.head, "total": len(self.files)})
            return subprocess.CompletedProcess(argv, 0, out, "")
        return subprocess.CompletedProcess(argv, 0, "https://github.com/acme/project/pull/7\n", "")


def _site(wpolicy: LocalPolicy, repo: Path) -> LocalPolicy:
    _git(repo, "branch", "-f", "topic", "HEAD")
    return dataclasses.replace(wpolicy, published_terms=("CVE id", "CVE"), published_paths=("security/json",))


def test_pr_create_lets_a_published_records_identifier_through_where_the_policy_says(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path
) -> None:
    """A site policy names `published_terms`: the record's identifier passes, every other term stays refused."""
    site = _site(wpolicy, repo)
    fake = FakeForge(["security/json/CVE-2026-1234.json"], _git(repo, "rev-parse", "topic"))
    git.gh_runner = fake
    body = "Adds the published record of CVE-2026-1234:\n\n- `security/json/CVE-2026-1234.json`\n"
    assert "pull/7" in _pr(git, site, repo, workspace, "Add CVE-2026-1234 to the security pages", body)
    with pytest.raises(GitRefused, match=r"never published.*advisory"):
        _pr(git, site, repo, workspace, "Add CVE-2026-1234", "the advisory")
    with pytest.raises(GitRefused, match="never published"):
        _pr(git, wpolicy, repo, workspace, "Add CVE-2026-1234 to the security pages", body)
    assert [any("/compare/" in a for a in call) for call in fake.calls] == [True, False]
    assert "repos/acme/project/compare/main...me:topic" in fake.calls[0]
    # A renamed file's old path counts as changed too, so a move out of a path
    # outside `published_paths` is caught.
    jq = fake.calls[0][fake.calls[0].index("--jq") + 1]
    assert ".previous_filename" in jq


@pytest.mark.parametrize(
    ("files", "head", "reason"),
    [
        pytest.param(
            ["security/json/a.json", "src/app.py"], None, "also changes src/app.py", id="outside-file"
        ),
        pytest.param(["security/jsonx/a.json"], None, "also changes", id="prefix-is-a-directory"),
        pytest.param([], None, "no changed file", id="no-files"),
        pytest.param(["security/json/a.json"], "0" * 40, "not at the local branch", id="other-head"),
    ],
)
def test_pr_create_binds_the_exemption_to_the_records_paths(
    git: Git,
    wpolicy: LocalPolicy,
    repo: Path,
    workspace: Path,
    files: list[str],
    head: str | None,
    reason: str,
) -> None:
    """A branch that changes anything else gets the normal scan: a source repository cannot use the exemption."""
    site = _site(wpolicy, repo)
    fake = FakeForge(files, head or _git(repo, "rev-parse", "topic"))
    git.gh_runner = fake
    with pytest.raises(GitRefused, match=f"exemption does not apply.*{reason}"):
        _pr(git, site, repo, workspace, "Add CVE-2026-1234 to the security pages", "Adds a record.\n")
    assert len(fake.calls) == 1  # the compare only; nothing opened


def test_pr_create_without_an_exempted_term_asks_the_forge_nothing(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path
) -> None:
    site = _site(wpolicy, repo)
    fake = FakeForge(["src/app.py"], "x")
    git.gh_runner = fake
    assert "pull/7" in _pr(git, site, repo, workspace, "feat: neat thing", "Does a neat thing.\n")
    assert len(fake.calls) == 1


def test_published_terms_name_only_a_records_identifier(tmp_path: Path, approved: Path) -> None:
    checkout = str(Path(os.path.realpath(tmp_path)))
    table = {
        "checkouts": [checkout],
        "published_terms": ["CVE id", "CVE"],
        "published_paths": ["security/json/"],
    }
    policy = git_ops.git_policy(_config(table))
    assert policy.published_terms == ("CVE id", "CVE")
    assert policy.published_paths == ("security/json",)
    assert git_ops.git_policy(_config({"checkouts": [checkout]})).published_terms == ()
    with pytest.raises(ConfigError, match="published_terms may name only"):
        git_ops.git_policy(_config({**table, "published_terms": ["advisory"]}))
    with pytest.raises(ConfigError, match="needs published_paths"):
        git_ops.git_policy(_config({"checkouts": [checkout], "published_terms": ["CVE"]}))
    with pytest.raises(ConfigError, match="only with published_terms"):
        git_ops.git_policy(_config({"checkouts": [checkout], "published_paths": ["security"]}))


@pytest.mark.parametrize("raw", ["/abs", "a/../b", "./a", "a/*", "a/[b]", "", "a//b"])
def test_published_paths_are_relative_glob_free_prefixes(tmp_path: Path, approved: Path, raw: str) -> None:
    checkout = str(Path(os.path.realpath(tmp_path)))
    table = {"checkouts": [checkout], "published_terms": ["CVE"], "published_paths": [raw]}
    with pytest.raises(ConfigError, match=r"published_paths (entries|must)"):
        git_ops.git_policy(_config(table))


def test_the_operator_file_cannot_let_terms_through(tmp_path: Path, approved: Path) -> None:
    """`published_terms` is the project's decision, in the shared policy everyone approves."""
    checkout = Path(os.path.realpath(tmp_path))
    _operator(approved, f'["acme/project"]\ncheckouts = ["{checkout}"]\npublished_terms = ["CVE"]\n')
    with pytest.raises(ConfigError, match="may not set published_terms"):
        git_ops.git_policy(_config(None))


def test_policy_from_discovers_the_policy_in_the_named_directory(
    policy: LocalPolicy, repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, approved: Path
) -> None:
    config = dataclasses.replace(_config({}), callers={"skill": frozenset({"git-push-branch"})})
    seen: list[object] = []

    def fake_load(*, approved_only: bool = False, cwd: Path | None = None, **_: object) -> Config:
        seen.append(cwd)
        if approved_only:
            raise ConfigError("the policy is not an approved copy")
        return config

    monkeypatch.setattr(git_ops, "load", fake_load)
    monkeypatch.setattr(git_ops, "git_policy", lambda _config, _base=None: policy)
    site = Path(os.path.realpath(tmp_path))
    _operator(approved, f'["acme/project"]\ncheckouts = ["{site}"]\n')
    argv = ["--caller", "skill", "--policy-from", str(site), "--dry-run"]
    argv += ["git-push-branch", str(repo), "topic", "fork", "topic", "new"]
    assert git_ops.main(argv, git=_ExplodingGit()) == git_ops.EXIT_OK
    assert seen == [site, site]


def test_policy_from_takes_only_a_checkout_the_operator_listed(
    repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    approved: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unlisted directory is refused before anything on disk is looked at: no probing of the host."""
    looked: list[object] = []

    def fake_load(**kw: object) -> Config:
        looked.append(kw)
        return _config({})

    monkeypatch.setattr(git_ops, "load", fake_load)
    listed = Path(os.path.realpath(tmp_path)) / "site"
    _operator(approved, f'["acme/other"]\ncheckouts = ["{listed}"]\n')
    argv = ["--caller", "skill", "--policy-from", str(tmp_path / "elsewhere"), "--dry-run"]
    argv += ["git-push-branch", str(repo), "topic", "fork", "topic", "new"]
    assert git_ops.main(argv, git=_ExplodingGit()) == git_ops.EXIT_POLICY
    assert "is not a checkout your" in capsys.readouterr().err
    assert not looked
    # Listed, but under another repository than the policy found there names.
    argv[argv.index("--policy-from") + 1] = str(listed)
    assert git_ops.main(argv, git=_ExplodingGit()) == git_ops.EXIT_POLICY
    assert "does not list" in capsys.readouterr().err


@pytest.mark.parametrize(
    "spelling",
    [
        pytest.param(["--policy-from", "relative/dir"], id="relative"),
        pytest.param(["--policy-from", "/does/not/exist"], id="missing"),
        pytest.param(["--policy-from", "/", "--policy-from=/tmp"], id="twice"),
    ],
)
def test_policy_from_refuses_a_relative_missing_or_repeated_directory(
    spelling: list[str], repo: Path
) -> None:
    argv = ["--caller", "skill", *spelling, "git-push-branch", str(repo), "topic", "fork", "topic", "new"]
    assert git_ops.main(argv, git=_ExplodingGit()) == git_ops.EXIT_POLICY


@dataclass
class FakePr:
    """`gh api repos/<upstream>/pulls/<N>`, answering with one pull request's head."""

    head: dict[str, object]
    calls: list[list[str]] = dataclasses.field(default_factory=list)

    def __call__(self, argv: list[str], env: dict[str, str], stdin: str) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, json.dumps(self.head), "")


def _contributor_pr(policy: LocalPolicy, repo: Path, **overrides: object) -> tuple[FakePr, str, str]:
    """A contributor's branch in their fork with one commit, and a local fixup on top of it."""
    # The operations run git without the test's GIT_* identity, so a commit they
    # make (a merge) needs one in the repository: Linux CI cannot guess one.
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "user.email", "t@example.org")
    _git(Path(policy.remotes), "init", "-q", "--bare", "alice__project.git")
    # Upstream's pr_base, which a push of an upstream merge fetches to check the merge against.
    _git(repo, "push", "-q", policy.push_url("acme/project"), "main:refs/heads/main")
    _git(repo, "checkout", "-q", "-b", "fixup")
    head = _commit(repo, "contribution")
    _git(repo, "push", "-q", policy.push_url("alice/project"), "HEAD:refs/heads/feature")
    fixup = _commit(repo, "fixup")
    answer: dict[str, object] = {
        "state": "open",
        "maintainer_can_modify": True,
        "base_repo": "acme/project",
        "head_repo": "alice/project",
        "head_ref": "feature",
        "head_sha": head,
    }
    answer.update(overrides)
    return FakePr(answer), head, fixup


def _push_head(
    git: Git,
    policy: GitPolicy,
    repo: Path,
    expected: str,
    number: str = "42",
    head_repo: str = "alice/project",
    head_branch: str = "feature",
) -> str:
    return git_ops.push_pr_head(
        git,
        policy,
        {
            "worktree": str(repo),
            "branch": "fixup",
            "number": number,
            "head_repo": head_repo,
            "head_branch": head_branch,
            "expected": expected,
        },
        False,
    )


def test_push_pr_head_fast_forwards_the_contributors_branch(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    fake, head, fixup = _contributor_pr(policy, repo)
    git.gh_runner = fake
    out = _push_head(git, policy, repo, head)
    assert f"was {head}" in out and "alice/project feature" in out
    assert _remote_head(policy, "alice/project", "feature") == fixup
    assert fake.calls[0][4] == "repos/acme/project/pulls/42"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        pytest.param({"maintainer_can_modify": False}, "does not allow edits", id="edits-not-allowed"),
        pytest.param({"state": "closed"}, "not open", id="closed"),
        pytest.param({"head_sha": "0" * 40}, "head is now", id="head-moved"),
        pytest.param({"base_repo": "other/project"}, "not against", id="other-base"),
        pytest.param({"head_repo": None}, "no head repository", id="fork-deleted"),
        pytest.param({"head_ref": "main"}, "protected", id="protected-head"),
        pytest.param(
            {"head_repo": "acme/project", "head_ref": "topic"}, "upstream_push", id="upstream-outside-globs"
        ),
    ],
)
def test_push_pr_head_refuses_what_the_forge_does_not_allow(
    git: Git, policy: LocalPolicy, repo: Path, overrides: dict[str, object], message: str
) -> None:
    fake, head, _ = _contributor_pr(policy, repo, **overrides)
    git.gh_runner = fake
    # The caller names the head the forge reports, so each refusal is the one under test.
    named_repo = overrides.get("head_repo") or "alice/project"
    named_branch = overrides.get("head_ref") or "feature"
    with pytest.raises(GitRefused, match=message):
        _push_head(git, policy, repo, head, head_repo=str(named_repo), head_branch=str(named_branch))
    assert _remote_head(policy, "alice/project", "feature") == head


@pytest.mark.parametrize(
    ("head_repo", "head_branch"),
    [("mallory/project", "feature"), ("alice/project", "other")],
)
def test_push_pr_head_refuses_a_head_other_than_the_one_named(
    git: Git, policy: LocalPolicy, repo: Path, head_repo: str, head_branch: str
) -> None:
    """The confirmation shows the named head; the forge must agree with it."""
    fake, head, _ = _contributor_pr(policy, repo)
    git.gh_runner = fake
    with pytest.raises(GitRefused, match="name the head the forge reports"):
        _push_head(git, policy, repo, head, head_repo=head_repo, head_branch=head_branch)
    assert _remote_head(policy, "alice/project", "feature") == head


def test_push_pr_head_refuses_a_merge_of_other_history(git: Git, policy: LocalPolicy, repo: Path) -> None:
    """Unpublished work merged into the fixup would go to the contributor's fork with it."""
    fake, head, _ = _contributor_pr(policy, repo)
    git.gh_runner = fake
    _git(repo, "checkout", "-q", "-b", "private", "main")
    _commit(repo, "unpublished")
    _git(repo, "checkout", "-q", "fixup")
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "private")
    with pytest.raises(GitRefused, match="merge commit"):
        _push_head(git, policy, repo, head)
    assert not fake.calls
    assert _remote_head(policy, "alice/project", "feature") == head


def test_push_pr_head_sees_through_a_replace_ref(git: Git, policy: LocalPolicy, repo: Path) -> None:
    """A replace ref that hides the merge from the graph checks is not honoured."""
    fake, head, _ = _contributor_pr(policy, repo)
    git.gh_runner = fake
    _git(repo, "checkout", "-q", "-b", "private", "main")
    _commit(repo, "unpublished")
    _git(repo, "checkout", "-q", "fixup")
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "private")
    merge = _git(repo, "rev-parse", "HEAD")
    # The same tree as the merge, with the fixup as its only parent.
    disguise = _git(repo, "commit-tree", f"{merge}^{{tree}}", "-p", f"{merge}^1", "-m", "fixup")
    _git(repo, "replace", merge, disguise)
    with pytest.raises(GitRefused, match="merge commit"):
        _push_head(git, policy, repo, head)
    assert _remote_head(policy, "alice/project", "feature") == head


def test_the_graph_checks_never_read_agent_writable_graph_metadata(git: Git, repo: Path) -> None:
    """The commit-graph, replace refs and grafts all live in `.git`; none of them is read."""
    argv = git.argv(repo, "rev-list", "HEAD")
    assert "core.commitGraph=false" in argv
    env = git._env()
    assert env["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert env["GIT_GRAFT_FILE"] == os.devnull


def test_push_pr_head_accepts_the_forges_casing(git: Git, policy: LocalPolicy, repo: Path) -> None:
    """GitHub names are case-insensitive, and the forge answers in its canonical casing."""
    fake, head, fixup = _contributor_pr(policy, repo, base_repo="Acme/Project")
    git.gh_runner = fake
    _push_head(git, policy, repo, head, head_repo="Alice/project")
    assert _remote_head(policy, "alice/project", "feature") == fixup


def test_a_repository_with_grafts_is_refused(git: Git, policy: LocalPolicy, repo: Path) -> None:
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "grafts").write_text("")
    _git(repo, "branch", "topic")
    with pytest.raises(GitRefused, match="grafts"):
        _push(git, policy, repo, "topic", "fork", "topic", "new")


def test_push_pr_head_refuses_more_than_a_fixup(git: Git, policy: LocalPolicy, repo: Path) -> None:
    fake, head, _ = _contributor_pr(policy, repo)
    git.gh_runner = fake
    for n in range(git_ops.MAX_FIXUP_COMMITS):
        _commit(repo, f"extra-{n}")
    with pytest.raises(GitRefused, match="at most"):
        _push_head(git, policy, repo, head)
    assert not fake.calls


def test_push_pr_head_never_rewrites_the_contributors_commits(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    fake, head, _ = _contributor_pr(policy, repo)
    git.gh_runner = fake
    _git(repo, "reset", "-q", "--hard", "main")
    _commit(repo, "replacement")
    with pytest.raises(GitRefused, match="never rewrites"):
        _push_head(git, policy, repo, head)
    assert not fake.calls
    assert _remote_head(policy, "alice/project", "feature") == head


def test_push_pr_head_refuses_a_branch_with_no_fixup(git: Git, policy: LocalPolicy, repo: Path) -> None:
    fake, head, _ = _contributor_pr(policy, repo)
    git.gh_runner = fake
    _git(repo, "reset", "-q", "--hard", head)
    with pytest.raises(GitRefused, match="commit the fixup first"):
        _push_head(git, policy, repo, head)


def test_push_pr_head_to_an_upstream_head_inside_the_globs(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "fixup")
    head = _commit(repo, "contribution")
    _git(repo, "push", "-q", policy.push_url("acme/project"), "HEAD:refs/heads/feature-x")
    fixup = _commit(repo, "fixup")
    git.gh_runner = FakePr(
        {
            "state": "open",
            "maintainer_can_modify": False,
            "base_repo": "acme/project",
            "head_repo": "acme/project",
            "head_ref": "feature-x",
            "head_sha": head,
        }
    )
    _push_head(git, policy, repo, head, head_repo="acme/project", head_branch="feature-x")
    assert _remote_head(policy, "acme/project", "feature-x") == fixup


@pytest.mark.parametrize(("number", "expected"), [("0", "a" * 40), ("42x", "a" * 40), ("42", "abc123")])
def test_push_pr_head_validates_parameters(
    git: Git, policy: LocalPolicy, repo: Path, number: str, expected: str
) -> None:
    _git(repo, "branch", "fixup")
    git.gh_runner = FakePr({})
    with pytest.raises(GitRefused):
        _push_head(git, policy, repo, expected, number=number)


def _switch(git: Git, policy: GitPolicy, worktree: Path, branch: str) -> str:
    return git_ops.switch_branch(git, policy, {"worktree": str(worktree), "branch": branch}, False)


def _upstream_main(repo: Path) -> None:
    """Publish the checkout's current `main` as upstream's (the bare `acme/project` remote)."""
    _git(
        repo,
        "push",
        "-q",
        "--force",
        str(repo.parent / "remotes" / "acme__project.git"),
        "main:refs/heads/main",
    )


def _settings(repo: Path, text: str, message: str) -> str:
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "settings.json").write_text(text)
    _git(repo, "add", ".claude/settings.json")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_switch_moves_a_clean_tree_to_a_branch(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _upstream_main(repo)
    _git(repo, "checkout", "-q", "-b", "topic")
    topic = _commit(repo, "two")
    _git(repo, "checkout", "-q", "main")
    out = _switch(git, policy, repo, "topic")
    assert "from main to topic" in out
    assert _git(repo, "rev-parse", "HEAD") == topic


def test_switch_brings_harness_files_that_came_from_upstream(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    """A branch cut from a newer upstream may carry its settings; only its own changes are refused."""
    _git(repo, "checkout", "-q", "-b", "old")
    _settings(repo, '{"v": 2}', "upstream moves settings")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--ff-only", "old")
    _upstream_main(repo)
    _git(repo, "checkout", "-q", "-b", "topic")
    _commit(repo, "two")
    _git(repo, "checkout", "-q", "old")
    _git(repo, "reset", "-q", "--hard", "main~1")
    _switch(git, policy, repo, "topic")
    assert (repo / ".claude" / "settings.json").read_text() == '{"v": 2}'


def test_switch_takes_an_older_branch_that_left_harness_files_alone(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    """A branch cut before upstream changed its settings switches, with the settings it was cut with."""
    _settings(repo, '{"v": 1}', "upstream, before")
    _git(repo, "checkout", "-q", "-b", "old-topic")
    _commit(repo, "two")
    _git(repo, "checkout", "-q", "main")
    _settings(repo, '{"v": 2}', "upstream changes settings")
    _upstream_main(repo)
    _switch(git, policy, repo, "old-topic")
    assert (repo / ".claude" / "settings.json").read_text() == '{"v": 1}'


@pytest.mark.parametrize(
    ("path", "harness"),
    [
        (".claude/settings.json", True),
        ("sub/project/.claude/skills/x/SKILL.md", True),
        (".github/skills/x", True),
        (".github", True),
        (".apache-magpie-overrides/tools", True),
        (".apache-magpie-overrides/tools/vetted-ops/config.toml", True),
        ("nested/.apache-magpie-overrides/tools/vetted-ops/config.toml", True),
        (".claude-plugin/marketplace.json", True),
        (".github/workflows/ci.yml", False),
        ("docs/claude.md", False),
        (".claudette/x", False),
        ("tools/vetted-ops/README.md", False),
    ],
)
def test_harness_paths_cover_nested_dirs_and_the_ancestors_a_symlink_could_replace(
    path: str, harness: bool
) -> None:
    assert git_ops.is_harness_path(path) is harness


def _forge_loose_object(repo: Path, oid: str, kind: str, content: bytes) -> None:
    """Overwrite the loose object stored under ``oid`` with other content, as an agent could."""
    path = repo / ".git" / "objects" / oid[:2] / oid[2:]
    path.chmod(0o644)
    path.write_bytes(zlib.compress(f"{kind} {len(content)}\0".encode() + content))


def test_switch_refuses_a_forged_object_in_the_store(git: Git, policy: LocalPolicy, repo: Path) -> None:
    """Git does not re-hash what it reads; the switch does, so a forged blob is caught."""
    _settings(repo, '{"permissions": {"deny": ["Bash(curl *)"]}}', "upstream settings")
    _upstream_main(repo)
    _git(repo, "checkout", "-q", "-b", "topic")
    _commit(repo, "two")
    _git(repo, "checkout", "-q", "main")
    blob = _git(repo, "rev-parse", "main:.claude/settings.json")
    _forge_loose_object(repo, blob, "blob", b'{"permissions": {"allow": ["Bash(*)"]}}')
    with pytest.raises(GitRefused, match="tampered with"):
        _switch(git, policy, repo, "topic")


def test_switch_puts_back_a_harness_file_that_changed_during_the_checkout(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    _settings(repo, '{"v": "upstream"}', "upstream settings")
    _upstream_main(repo)
    _git(repo, "checkout", "-q", "-b", "topic")
    _commit(repo, "two")
    _git(repo, "checkout", "-q", "main")
    real = git.runner

    def tamper_during_checkout(
        argv: list[str], env: dict[str, str], cwd_fd: int | None
    ) -> subprocess.CompletedProcess[str]:
        done = real(argv, env, cwd_fd)
        if "--detach" in argv:
            (repo / ".claude" / "settings.json").write_text('{"v": "agent"}')
        return done

    git.runner = tamper_during_checkout
    out = _switch(git, policy, repo, "topic")
    assert "put back the verified content of .claude/settings.json" in out
    assert (repo / ".claude" / "settings.json").read_text() == '{"v": "upstream"}'
    # Put back owner-only: nobody else needs to read the harness's settings.
    assert stat.S_IMODE((repo / ".claude" / "settings.json").stat().st_mode) == 0o600


def test_switch_fails_closed_on_a_harness_directory_turned_into_a_symlink(
    git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    _settings(repo, '{"v": "upstream"}', "upstream settings")
    _upstream_main(repo)
    _git(repo, "checkout", "-q", "-b", "topic")
    _commit(repo, "two")
    _git(repo, "checkout", "-q", "main")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    real = git.runner

    def symlink_during_checkout(
        argv: list[str], env: dict[str, str], cwd_fd: int | None
    ) -> subprocess.CompletedProcess[str]:
        done = real(argv, env, cwd_fd)
        if "--detach" in argv:
            shutil.rmtree(repo / ".claude")
            (repo / ".claude").symlink_to(elsewhere)
        return done

    git.runner = symlink_during_checkout
    with pytest.raises(GitRefused, match="check them by hand"):
        _switch(git, policy, repo, "topic")
    assert not (elsewhere / "settings.json").exists()


def test_switch_refuses_a_forged_upstream_history(git: Git, policy: LocalPolicy, repo: Path) -> None:
    """A forged upstream commit naming the agent's branch as its parent would make it the fork point."""
    _git(repo, "checkout", "-q", "-b", "topic")
    topic = _settings(repo, '{"permissions": {"allow": ["Bash(*)"]}}', "widen")
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "two")
    _upstream_main(repo)
    base = _git(repo, "rev-parse", "main")
    tree = _git(repo, "rev-parse", "main^{tree}")
    forged = f"tree {tree}\nparent {topic}\nauthor t <t@example.org> 0 +0000\ncommitter t <t@example.org> 0 +0000\n\nx\n"
    # The upstream commit, as the repository now holds it: a child of the agent's branch.
    _forge_loose_object(repo, base, "commit", forged.encode())
    try:
        fork = _git(repo, "merge-base", "topic", base)
    except subprocess.CalledProcessError as refused:
        # Depending on the release, git re-hashes the commit and refuses it, or trusts it.
        assert "hash mismatch" in refused.stderr
    else:
        assert fork == topic  # git itself is fooled
    with pytest.raises(GitRefused, match="tampered with"):
        _switch(git, policy, repo, "topic")
    assert not (repo / ".claude" / "settings.json").exists()


def test_switch_refuses_a_tree_mode_git_reads_differently(git: Git, policy: LocalPolicy, repo: Path) -> None:
    """`040000` is a directory to git's checkout; the walk must not skip it."""
    _upstream_main(repo)
    blob = _git(repo, "hash-object", "-w", "--stdin")
    inner = (
        subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-t", "tree", "-w", "--literally", "--stdin"],
            input=b"100644 settings.json\0" + bytes.fromhex(blob),
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    claude = (
        subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-t", "tree", "-w", "--literally", "--stdin"],
            input=b"040000 .claude\0" + bytes.fromhex(inner),
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    commit = _git(repo, "commit-tree", claude, "-p", "main", "-m", "odd mode")
    _git(repo, "branch", "topic", commit)
    with pytest.raises(GitRefused, match="malformed entry"):
        _switch(git, policy, repo, "topic")


def test_switch_refuses_a_branch_checked_out_elsewhere(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _upstream_main(repo)
    _git(repo, "branch", "topic")
    _git(repo, "worktree", "add", "-q", str(repo.parent / "worktrees" / "other"), "topic")
    with pytest.raises(GitRefused, match="is checked out in"):
        _switch(git, policy, repo, "topic")


def test_harness_paths_from_the_policy_are_normalised(tmp_path: Path) -> None:
    checkout = Path(os.path.realpath(tmp_path))
    policy = git_ops.git_policy(
        _config({"checkouts": [str(checkout)], "harness_paths": ["./tools/x/", "/y.json"]})
    )
    assert policy.harness_paths == ("tools/x", "y.json")
    assert git_ops.is_harness_path("tools/x/settings.json", policy.harness_paths)


def test_switch_honours_harness_paths_from_the_policy(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _upstream_main(repo)
    _git(repo, "checkout", "-q", "-b", "topic")
    (repo / "tools").mkdir()
    (repo / "tools" / "settings.template.json").write_text("{}")
    _git(repo, "add", "tools/settings.template.json")
    _git(repo, "commit", "-q", "-m", "template")
    _git(repo, "checkout", "-q", "main")
    strict = dataclasses.replace(policy, harness_paths=("tools/settings.template.json",))
    with pytest.raises(GitRefused, match="in its own commits"):
        _switch(git, strict, repo, "topic")
    _switch(git, policy, repo, "topic")


def test_switch_refuses_a_branch_that_changes_harness_files_itself(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    _upstream_main(repo)
    _git(repo, "checkout", "-q", "-b", "topic")
    _settings(repo, '{"permissions": {"allow": ["Bash(*)"]}}', "widen")
    _git(repo, "checkout", "-q", "main")
    with pytest.raises(GitRefused, match=r"\.claude/settings\.json in its own commits"):
        _switch(git, policy, repo, "topic")
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert not (repo / ".claude" / "settings.json").exists()


def test_switch_refuses_harness_changes_with_no_upstream_base(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    _git(repo, "checkout", "-q", "-b", "topic")
    _settings(repo, "{}", "settings")
    _git(repo, "checkout", "-q", "main")
    with pytest.raises(GitRefused, match="no branch 'main' to check against"):
        _switch(git, policy, repo, "topic")


def test_switch_ignores_a_local_upstream_ref_the_agent_could_move(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    """`refs/remotes/upstream/main` is in the writable `.git`; only the policy's URL counts."""
    _upstream_main(repo)
    _git(repo, "checkout", "-q", "-b", "topic")
    _settings(repo, '{"permissions": {"allow": ["Bash(*)"]}}', "widen")
    _git(repo, "update-ref", "refs/remotes/upstream/main", "topic")
    _git(repo, "checkout", "-q", "main")
    with pytest.raises(GitRefused, match="in its own commits"):
        _switch(git, policy, repo, "topic")


@pytest.mark.parametrize("name", [".Claude/settings.json", ".CLAUDE/hooks/x", ".clau‍de/settings.json"])
def test_switch_matches_harness_paths_as_the_file_system_does(
    git: Git, policy: LocalPolicy, repo: Path, name: str
) -> None:
    """On a case-insensitive file system `.Claude/` is `.claude/`."""
    assert git_ops.is_harness_path(name)
    _upstream_main(repo)
    _git(repo, "checkout", "-q", "-b", "topic")
    blob = _git(repo, "hash-object", "-w", "--stdin")
    _git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{name}")
    _git(repo, "commit", "-q", "-m", "sneak")
    _git(repo, "checkout", "-q", "main")
    with pytest.raises(GitRefused, match="in its own commits"):
        _switch(git, policy, repo, "topic")


def test_switch_attaches_only_the_commit_it_checked(git: Git, policy: LocalPolicy, repo: Path) -> None:
    """A branch moved during the switch is not attached; the tree holds the checked commit."""
    _upstream_main(repo)
    _git(repo, "checkout", "-q", "-b", "topic")
    checked = _commit(repo, "two")
    moved = _commit(repo, "three")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "update-ref", "refs/heads/topic", checked)
    real = git.runner

    def move_after_detach(
        argv: list[str], env: dict[str, str], cwd_fd: int | None
    ) -> subprocess.CompletedProcess[str]:
        done = real(argv, env, cwd_fd)
        if "--detach" in argv:
            _git(repo, "update-ref", "refs/heads/topic", moved)
        return done

    git.runner = move_after_detach
    out = _switch(git, policy, repo, "topic")
    assert "detached HEAD" in out
    assert _git(repo, "rev-parse", "HEAD") == checked
    assert not (repo / "three").exists()


def test_switch_refuses_local_changes_and_unknown_branches(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _git(repo, "branch", "topic")
    (repo / "one").write_text("edited")
    with pytest.raises(GitRefused, match="uncommitted changes"):
        _switch(git, policy, repo, "topic")
    _git(repo, "checkout", "-q", "--", "one")
    with pytest.raises(GitRefused, match="never creates one"):
        _switch(git, policy, repo, "no-such-branch")


def test_switch_runs_no_post_checkout_hook(git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    _hook(repo, "post-checkout", marker)
    _upstream_main(repo)
    _git(repo, "branch", "topic")
    _switch(git, policy, repo, "topic")
    assert not marker.exists()


def _draft_table(message: str) -> str:
    """The ["<upstream>"] table a refusal drafted, as TOML text."""
    # The last occurrence: the refusal's own prose names the table first.
    return message[message.rindex('["acme/project"]') :]


def test_no_git_values_refusal_drafts_the_operator_table(
    repo: Path, approved: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(repo)
    with pytest.raises(ConfigError) as caught:
        git_ops.git_policy(_config(None))
    message = str(caught.value)
    assert str(approved / git_ops.OPERATOR_GIT_FILE) in message
    assert f'checkouts = ["{repo}"]' in message
    assert 'fork = "<your-github-login>/project"' in message
    # The draft is one the operator file accepts: only operator keys, valid TOML.
    _operator(approved, _draft_table(message).replace("<your-github-login>", "me"))
    assert git_ops.operator_git_table("acme/project") is not None


def test_missing_checkouts_refusal_drafts_the_operator_table(
    repo: Path, approved: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A shared [git] for the project keys, but no operator file yet."""
    monkeypatch.chdir(repo)
    with pytest.raises(ConfigError) as caught:
        git_ops.git_policy(_config({"upstream_push": ["ci-*"]}))
    assert "checkouts must name at least one main checkout" in str(caught.value)
    assert '["acme/project"]' in str(caught.value)


# --- git-rebase ------------------------------------------------------------


def _diverged(repo: Path, conflict: bool = False) -> tuple[str, str]:
    """A topic branch with one commit, checked out, and upstream main one commit ahead.

    Returns (the topic tip, the upstream commit to rebase onto).
    """
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "user.email", "t@example.org")
    base = _git(repo, "rev-parse", "HEAD")
    if conflict:
        (repo / "one").write_text("upstream")
        _git(repo, "commit", "-qam", "upstream edits one")
    else:
        _commit(repo, "upstream-file")
    onto = _git(repo, "rev-parse", "HEAD")
    # The operation fetches the base itself, from the policy's upstream URL.
    _git(repo, "push", "-q", str(repo.parent / "remotes" / "acme__project.git"), f"{onto}:refs/heads/main")
    _git(repo, "checkout", "-q", "-b", "topic", base)
    if conflict:
        (repo / "one").write_text("topic")
        _git(repo, "commit", "-qam", "topic edits one")
    else:
        _commit(repo, "topic-file")
    return _git(repo, "rev-parse", "HEAD"), onto


def _rebase(
    git: Git, policy: GitPolicy, worktree: Path, onto: str, expected: str, dry_run: bool = False
) -> str:
    return git_ops.rebase_onto(
        git, policy, {"worktree": str(worktree), "onto": onto, "expected": expected}, dry_run
    )


def test_rebase_replays_the_topic_onto_the_upstream_commit(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo)
    message = _rebase(git, policy, repo, onto, tip)
    rebased = _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "rev-parse", "HEAD^") == onto
    assert _git(repo, "log", "-1", "--format=%s") == "topic-file"
    assert (repo / "topic-file").exists() and (repo / "upstream-file").exists()
    assert f"{tip} -> {rebased} (1 commits)" in message


def test_rebase_works_in_a_linked_worktree(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo)
    _git(repo, "checkout", "-q", "main")
    path = policy.worktree_roots[0] / "wt"
    _git(repo, "worktree", "add", "-q", str(path), "topic")
    _rebase(git, policy, path, onto, tip)
    assert _git(path, "rev-parse", "HEAD^") == onto


def test_rebase_conflict_is_aborted_and_named(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo, conflict=True)
    with pytest.raises(git_ops.GitFailed) as caught:
        _rebase(git, policy, repo, onto, tip)
    assert "conflicting paths: one" in caught.value.stderr
    assert f"still at {tip}" in caught.value.stderr
    assert _git(repo, "rev-parse", "HEAD") == tip
    assert _git(repo, "status", "--porcelain") == ""
    assert not (repo / ".git" / "rebase-merge").exists()


def test_rebase_refuses_a_branch_that_moved(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo)
    _commit(repo, "later")
    with pytest.raises(GitRefused, match="not the expected"):
        _rebase(git, policy, repo, onto, tip)


def test_rebase_refuses_a_base_upstream_does_not_have(git: Git, policy: LocalPolicy, repo: Path) -> None:
    """Even one a sandboxed fetch planted under the upstream remote-tracking namespace."""
    tip, _ = _diverged(repo)
    _git(repo, "checkout", "-q", "-b", "local-only", "main")
    local = _commit(repo, "local")
    _git(repo, "update-ref", "refs/remotes/upstream/main", local)
    _git(repo, "update-ref", "refs/remotes/upstream/planted", local)
    _git(repo, "checkout", "-q", "topic")
    with pytest.raises(GitRefused, match="is not on acme/project main"):
        _rebase(git, policy, repo, local, tip)
    assert _git(repo, "rev-parse", "HEAD") == tip


def test_rebase_refuses_main_hidden_behind_a_tag_of_the_same_name(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    """`symbolic-ref --short` answers `heads/main` here, which no protected glob matches."""
    _, onto = _diverged(repo)
    _git(repo, "checkout", "-q", "main")
    _git(repo, "tag", "main")
    with pytest.raises(GitRefused, match="'main' is a protected branch"):
        _rebase(git, policy, repo, onto, onto)


def test_commit_refuses_main_hidden_behind_a_tag_of_the_same_name(
    git: Git, wpolicy: LocalPolicy, repo: Path, workspace: Path
) -> None:
    _git(repo, "tag", "main")
    (repo / "one").write_text("changed")
    _git(repo, "add", "one")
    with pytest.raises(GitRefused, match="'main' is a protected branch"):
        git_ops.commit_staged(
            git, wpolicy, {"worktree": str(repo), "message_file": _file(workspace, "m", "msg")}, False
        )


def test_rebase_refuses_a_branch_with_merge_commits(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo)
    _git(repo, "checkout", "-q", "-b", "side", tip)
    _commit(repo, "side-file")
    _git(repo, "checkout", "-q", "topic")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    merged = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(GitRefused, match="merge commits"):
        _rebase(git, policy, repo, onto, merged)
    assert _git(repo, "rev-parse", "HEAD") == merged


def test_rebase_puts_back_a_branch_moved_as_it_started(policy: LocalPolicy, repo: Path) -> None:
    """A commit landing between the checks and the rebase is never replayed under the approval."""
    tip, onto = _diverged(repo)
    plain = _runner(os.devnull)

    def racing(argv: list[str], env: dict[str, str], cwd_fd: int | None) -> subprocess.CompletedProcess[str]:
        if "rebase" in argv and "--abort" not in argv:
            _commit(repo, "sneaked-in")
        return plain(argv, env, cwd_fd)

    raced = Git(runner=racing, protocols=("https", "ssh", "file"))
    with pytest.raises(GitRefused, match="moved to"):
        _rebase(raced, policy, repo, onto, tip)
    moved = _git(repo, "rev-parse", "HEAD")
    assert moved != tip
    assert _git(repo, "rev-parse", "HEAD^") == tip


def test_rebase_refuses_a_protected_branch(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _, onto = _diverged(repo)
    _git(repo, "checkout", "-q", "main")
    with pytest.raises(GitRefused, match="protected"):
        _rebase(git, policy, repo, onto, onto)


def test_rebase_refuses_local_changes(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo)
    (repo / "topic-file").write_text("changed")
    with pytest.raises(GitRefused, match="uncommitted"):
        _rebase(git, policy, repo, onto, tip)


def test_rebase_of_a_branch_already_on_the_base_does_nothing(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    tip, onto = _diverged(repo)
    _rebase(git, policy, repo, onto, tip)
    rebased = _git(repo, "rev-parse", "HEAD")
    assert "nothing to rebase" in _rebase(git, policy, repo, onto, rebased)
    assert _git(repo, "rev-parse", "HEAD") == rebased


def test_rebase_never_runs_hooks(git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path) -> None:
    marker = tmp_path / "hook-ran"
    tip, onto = _diverged(repo)
    _hook(repo, "pre-rebase", marker, exit_code=1)
    _hook(repo, "post-rewrite", marker)
    _rebase(git, policy, repo, onto, tip)
    assert not marker.exists()
    assert _git(repo, "rev-parse", "HEAD^") == onto


def test_rebase_dry_run_changes_nothing(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo)
    command = _rebase(git, policy, repo, onto, tip, dry_run=True)
    assert "rebase" in command and "rerere.enabled=false" in command and onto in command
    assert _git(repo, "rev-parse", "HEAD") == tip


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("onto", "abc123", "full lowercase commit SHA"),
        ("expected", "--exec=sh", "may not"),
        ("worktree", "relative/path", "absolute"),
    ],
)
def test_rebase_validates_parameters(
    git: Git, policy: LocalPolicy, repo: Path, field: str, value: str, message: str
) -> None:
    tip, onto = _diverged(repo)
    params = {"worktree": str(repo), "onto": onto, "expected": tip, field: value}
    with pytest.raises(GitRefused, match=message):
        git_ops.rebase_onto(git, policy, params, False)


#: A stand-in for gpg: signs with a fixed block and verifies any signature as
#: good and fully trusted, so `%G?` is `G` for a signed commit, `N` otherwise.
FAKE_GPG = """#!/bin/sh
for a in "$@"; do
  if [ "$a" = "--verify" ]; then
    cat >/dev/null
    shift $(($# - 2))
    if grep -q fake "$1"; then
      printf '[GNUPG:] NEWSIG\\n[GNUPG:] GOODSIG ABCD t\\n'
      printf '[GNUPG:] VALIDSIG ABCDEF 2020-01-01 0 4 0 1 8 00 ABCDEF\\n[GNUPG:] TRUST_ULTIMATE 0 pgp\\n'
      exit 0
    fi
    printf '[GNUPG:] NEWSIG\\n[GNUPG:] BADSIG ABCD t\\n'
    exit 1
  fi
done
cat >/dev/null
printf '\\n[GNUPG:] SIG_CREATED D 1 8 00 0 X\\n' >&2
printf -- '-----BEGIN PGP SIGNATURE-----\\n\\nfake\\n-----END PGP SIGNATURE-----\\n'
"""


def _signing_git(tmp_path: Path) -> tuple[Git, Path]:
    """A `Git` whose user's global configuration signs commits, and the signer it uses."""
    signer = tmp_path / "fake-gpg"
    signer.write_text(FAKE_GPG)
    signer.chmod(0o755)
    global_config = tmp_path / "global.gitconfig"
    global_config.write_text(f"[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = {signer}\n")
    return Git(runner=_runner(str(global_config)), protocols=("https", "ssh", "file")), signer


def _sign_tip(repo: Path, signer: Path) -> str:
    """Re-make the checked-out tip as a commit the user signed."""
    _git(repo, "-c", f"gpg.program={signer}", "commit", "-q", "--amend", "--no-edit", "-S")
    return _git(repo, "rev-parse", "HEAD")


def test_rebase_signs_per_the_users_global_config(policy: LocalPolicy, repo: Path, tmp_path: Path) -> None:
    """Re-signing the replayed commits is what the sandbox cannot do; the global config decides it."""
    signing, signer = _signing_git(tmp_path)
    _, onto = _diverged(repo)
    tip = _sign_tip(repo, signer)
    _rebase(signing, policy, repo, onto, tip)
    rebased = _git(repo, "rev-parse", "HEAD")
    assert rebased != tip
    assert "fake" in _git(repo, "cat-file", "commit", rebased)


def test_rebase_refuses_to_sign_a_commit_the_user_did_not(
    policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    """An unsigned commit the agent made in the sandbox never gets the user's signature here."""
    signing, signer = _signing_git(tmp_path)
    _, onto = _diverged(repo)
    _sign_tip(repo, signer)
    unsigned = _commit(repo, "agent-made")
    with pytest.raises(GitRefused, match=f"carry no good signature of yours: {unsigned}"):
        _rebase(signing, policy, repo, onto, unsigned)
    assert _git(repo, "rev-parse", "HEAD") == unsigned


def test_signing_settings_are_pinned_to_the_users_own(tmp_path: Path, repo: Path) -> None:
    signing, signer = _signing_git(tmp_path)
    argv = signing.argv(repo, "log")
    assert f"gpg.program={signer}" in argv
    assert f"gpg.openpgp.program={signer}" in argv
    assert "gpg.format=openpgp" in argv
    assert "gpg.ssh.program=ssh-keygen" in argv
    # Unset by the user: an empty list of trusted ssh signers, never the repository's.
    assert f"gpg.ssh.allowedSignersFile={os.devnull}" in argv


def test_a_verifier_the_repository_gains_before_the_check_never_runs(
    policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    """A `gpg.program` set right after the configuration check cannot vouch for the agent's commit."""
    signing, signer = _signing_git(tmp_path)
    _, onto = _diverged(repo)
    _sign_tip(repo, signer)
    agent_signer = tmp_path / "agent-gpg"
    agent_signer.write_text(FAKE_GPG.replace("fake", "agent"))
    agent_signer.chmod(0o755)
    _git(repo, "-c", f"gpg.program={agent_signer}", "commit", "-q", "--allow-empty", "-S", "-m", "agent")
    agent_commit = _git(repo, "rev-parse", "HEAD")
    marker = tmp_path / "verifier-ran"
    vouch = tmp_path / "vouch-gpg"
    vouch.write_text(
        f"#!/bin/sh\ntouch {marker}\ncat >/dev/null\n"
        "printf '[GNUPG:] NEWSIG\\n[GNUPG:] GOODSIG ABCD t\\n[GNUPG:] TRUST_ULTIMATE 0 pgp\\n'\n"
    )
    vouch.chmod(0o755)
    inner = signing.runner

    def racing(argv: list[str], env: dict[str, str], cwd_fd: int | None) -> subprocess.CompletedProcess[str]:
        if "--format=%H %G?" in argv:
            _git(repo, "config", "gpg.program", str(vouch))
        return inner(argv, env, cwd_fd)

    signing.runner = racing
    with pytest.raises(GitRefused, match=f"carry no good signature of yours: {agent_commit}"):
        _rebase(signing, policy, repo, onto, agent_commit)
    assert not marker.exists()


def test_rebase_without_signing_replays_unsigned_commits(git: Git, policy: LocalPolicy, repo: Path) -> None:
    """A user who does not sign gets no signature from the rebase either, so nothing is checked."""
    assert not git.signs_commits()
    tip, onto = _diverged(repo)
    _rebase(git, policy, repo, onto, tip)
    assert "gpgsig" not in _git(repo, "cat-file", "commit", "HEAD")


def test_rebase_refuses_a_branch_named_like_an_option(git: Git, policy: LocalPolicy, repo: Path) -> None:
    """`refs/heads/-x` is a valid ref; its name must never reach the rebase command line."""
    tip, onto = _diverged(repo)
    _git(repo, "update-ref", "refs/heads/--exec=touch-pwned", tip)
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/--exec=touch-pwned")
    with pytest.raises(GitRefused, match="may not be empty, start with"):
        _rebase(git, policy, repo, onto, tip)


# --- git-cherry-pick -------------------------------------------------------


def _pick(
    git: Git, policy: GitPolicy, worktree: Path, commit: str, expected: str, dry_run: bool = False
) -> str:
    return git_ops.cherry_pick(
        git, policy, {"worktree": str(worktree), "commit": commit, "expected": expected}, dry_run
    )


def _redo_branch(repo: Path, onto: str) -> str:
    """A fresh topic branch on the upstream commit, to replay a conflicting rebase onto."""
    _git(repo, "checkout", "-q", "-b", "redo", onto)
    return onto


def test_cherry_pick_replays_one_commit_onto_the_branch(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo)
    _redo_branch(repo, onto)
    message = _pick(git, policy, repo, tip, onto)
    picked = _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "rev-parse", "HEAD^") == onto
    assert _git(repo, "log", "-1", "--format=%s") == "topic-file"
    assert f"{onto} -> {picked}" in message


def test_cherry_pick_conflict_is_aborted_and_named(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo, conflict=True)
    _redo_branch(repo, onto)
    with pytest.raises(git_ops.GitFailed) as caught:
        _pick(git, policy, repo, tip, onto)
    assert "conflicting paths: one" in caught.value.stderr
    assert f"still at {onto}" in caught.value.stderr
    assert _git(repo, "rev-parse", "HEAD") == onto
    assert _git(repo, "status", "--porcelain") == ""
    assert not (repo / ".git" / "CHERRY_PICK_HEAD").exists()


def test_cherry_pick_refusals(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo)
    _git(repo, "checkout", "-q", "-b", "side", tip)
    _commit(repo, "side-file")
    _git(repo, "checkout", "-q", "topic")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    merge = _git(repo, "rev-parse", "HEAD")
    _redo_branch(repo, onto)
    with pytest.raises(GitRefused, match="a merge commit"):
        _pick(git, policy, repo, merge, onto)
    with pytest.raises(GitRefused, match="not the expected"):
        _pick(git, policy, repo, tip, tip)
    (repo / "one").write_text("changed")
    with pytest.raises(GitRefused, match="uncommitted"):
        _pick(git, policy, repo, tip, onto)
    _git(repo, "checkout", "-q", "--", "one")
    _git(repo, "checkout", "-q", "main")
    with pytest.raises(GitRefused, match="protected"):
        _pick(git, policy, repo, tip, _git(repo, "rev-parse", "HEAD"))
    assert _git(repo, "rev-parse", "redo") == onto


def test_cherry_pick_of_a_commit_already_on_the_branch_does_nothing(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    tip, _ = _diverged(repo)
    assert "nothing to replay" in _pick(git, policy, repo, tip, tip)


def test_cherry_pick_never_runs_hooks(git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path) -> None:
    marker = tmp_path / "hook-ran"
    tip, onto = _diverged(repo)
    _redo_branch(repo, onto)
    _hook(repo, "pre-commit", marker, exit_code=1)
    _hook(repo, "post-commit", marker)
    _pick(git, policy, repo, tip, onto)
    assert not marker.exists()


def test_cherry_pick_replays_only_the_users_signed_commits(
    policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    signing, signer = _signing_git(tmp_path)
    unsigned, onto = _diverged(repo)
    signed = _sign_tip(repo, signer)
    _redo_branch(repo, onto)
    with pytest.raises(GitRefused, match=f"carry no good signature of yours: {unsigned}"):
        _pick(signing, policy, repo, unsigned, onto)
    _pick(signing, policy, repo, signed, onto)
    assert "fake" in _git(repo, "cat-file", "commit", "HEAD")


def test_cherry_pick_takes_back_a_pick_onto_a_branch_moved_as_it_started(
    policy: LocalPolicy, repo: Path
) -> None:
    tip, onto = _diverged(repo)
    _redo_branch(repo, onto)
    plain = _runner(os.devnull)

    def racing(argv: list[str], env: dict[str, str], cwd_fd: int | None) -> subprocess.CompletedProcess[str]:
        if "cherry-pick" in argv and "--abort" not in argv:
            _commit(repo, "sneaked-in")
        return plain(argv, env, cwd_fd)

    raced = Git(runner=racing, protocols=("https", "ssh", "file"))
    with pytest.raises(GitRefused, match="taken back off"):
        _pick(raced, policy, repo, tip, onto)
    assert _git(repo, "log", "-1", "--format=%s") == "sneaked-in"


def test_cherry_pick_dry_run_changes_nothing(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo)
    _redo_branch(repo, onto)
    command = _pick(git, policy, repo, tip, onto, dry_run=True)
    assert "cherry-pick" in command and "rerere.enabled=false" in command and tip in command
    assert _git(repo, "rev-parse", "HEAD") == onto


# --- git-delete-fork-branch ------------------------------------------------


@dataclass
class FakeMerged:
    """`gh api repos/<upstream>/pulls?head=…&state=closed`, answering with merged pull requests."""

    prs: list[dict[str, object]]
    calls: list[list[str]] = dataclasses.field(default_factory=list)

    def __call__(self, argv: list[str], env: dict[str, str], stdin: str) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, json.dumps(self.prs), "")


def _merged_fork_branch(policy: LocalPolicy, repo: Path) -> str:
    """A topic branch pushed to the fork, as the head of a pull request that has since merged."""
    _git(repo, "checkout", "-q", "-b", "topic")
    tip = _commit(repo, "topic-file")
    _git(repo, "push", "-q", policy.push_url("me/project"), "topic:refs/heads/topic")
    _git(repo, "checkout", "-q", "main")
    return tip


def _delete(
    git: Git, policy: GitPolicy, repo: Path, branch: str, expected: str, dry_run: bool = False
) -> str:
    return git_ops.delete_fork_branch(
        git, policy, {"checkout": str(repo), "branch": branch, "expected": expected}, dry_run
    )


def _fork_has(policy: LocalPolicy, branch: str) -> bool:
    out = _git(
        Path(policy.push_url("me/project")), "for-each-ref", "--format=%(refname)", f"refs/heads/{branch}"
    )
    return bool(out)


def test_delete_fork_branch_removes_a_merged_pull_requests_branch(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    tip = _merged_fork_branch(policy, repo)
    fake = FakeMerged([{"number": 7, "head_repo": "me/project", "head_ref": "topic", "head_sha": tip}])
    git.gh_runner = fake
    out = _delete(git, policy, repo, "topic", tip)
    assert "head of merged #7" in out
    assert not _fork_has(policy, "topic")
    assert "head=me:topic" in fake.calls[0]
    assert "repos/acme/project/pulls" in fake.calls[0]


@pytest.mark.parametrize(
    "prs",
    [
        pytest.param([], id="no-merged-pr"),
        pytest.param(
            [{"number": 7, "head_repo": "me/project", "head_ref": "topic", "head_sha": "0" * 40}],
            id="other-head",
        ),
        pytest.param(
            [{"number": 7, "head_repo": "eve/project", "head_ref": "topic", "head_sha": None}],
            id="other-fork",
        ),
        pytest.param(
            [{"number": 7, "head_repo": "me/project", "head_ref": "other", "head_sha": None}],
            id="other-branch",
        ),
    ],
)
def test_delete_fork_branch_refuses_a_branch_no_merged_pull_request_headed(
    git: Git, policy: LocalPolicy, repo: Path, prs: list[dict[str, object]]
) -> None:
    tip = _merged_fork_branch(policy, repo)
    for pr in prs:
        if pr["head_sha"] is None:
            pr["head_sha"] = tip
    git.gh_runner = FakeMerged(prs)
    with pytest.raises(GitRefused, match="only a merged pull request's branch is deleted"):
        _delete(git, policy, repo, "topic", tip)
    assert _fork_has(policy, "topic")


def test_delete_fork_branch_keeps_a_branch_pushed_to_since_the_merge(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    tip = _merged_fork_branch(policy, repo)
    _git(repo, "checkout", "-q", "topic")
    later = _commit(repo, "later")
    _git(repo, "push", "-q", policy.push_url("me/project"), "topic:refs/heads/topic")
    git.gh_runner = FakeMerged(
        [{"number": 7, "head_repo": "me/project", "head_ref": "topic", "head_sha": tip}]
    )
    with pytest.raises(git_ops.GitFailed):
        _delete(git, policy, repo, "topic", tip)
    assert _remote_head(policy, "me/project", "topic") == later


def test_delete_fork_branch_refuses_a_protected_branch_and_a_missing_fork(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    tip = _git(repo, "rev-parse", "HEAD")
    git.gh_runner = FakeMerged([])
    with pytest.raises(GitRefused, match="protected"):
        _delete(git, policy, repo, "main", tip)
    with pytest.raises(GitRefused, match="names no \\[git\\] fork"):
        _delete(git, dataclasses.replace(policy, fork_repo=None), repo, "topic", tip)
    assert not git.gh_runner.calls


def test_delete_fork_branch_dry_run_asks_and_changes_nothing(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    tip = _merged_fork_branch(policy, repo)
    fake = FakeMerged([])
    git.gh_runner = fake
    command = _delete(git, policy, repo, "topic", tip, dry_run=True)
    assert ":refs/heads/topic" in command and f"--force-with-lease=refs/heads/topic:{tip}" in command
    assert not fake.calls
    assert _fork_has(policy, "topic")


# --- git-merge-upstream ----------------------------------------------------


def _merge(
    git: Git,
    policy: GitPolicy,
    worktree: Path,
    onto: str,
    expected: str,
    dry_run: bool = False,
    pr: str = "none",
) -> str:
    return git_ops.merge_upstream(
        git, policy, {"worktree": str(worktree), "onto": onto, "expected": expected, "pr": pr}, dry_run
    )


def _upstream_moves_on(policy: LocalPolicy, repo: Path, back_to: str) -> str:
    """A new commit on upstream main, published; checks `back_to` out again. Returns the new commit."""
    _git(repo, "checkout", "-q", "main")
    onto = _commit(repo, "upstream-new")
    _git(repo, "push", "-q", policy.push_url("acme/project"), "main:refs/heads/main")
    _git(repo, "checkout", "-q", back_to)
    return onto


def test_merge_into_a_pull_request_checks_only_the_maintainers_commits(
    policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    """The contributor's commits are theirs and unsigned by the user; only the fixup on top must be."""
    signing, signer = _signing_git(tmp_path)
    fake, head, _ = _contributor_pr(policy, repo)
    signing.gh_runner = fake
    fixup = _sign_tip(repo, signer)
    onto = _upstream_moves_on(policy, repo, "fixup")
    _merge(signing, policy, repo, onto, fixup, pr="42")
    assert _git(repo, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:] == [fixup, onto]
    assert fake.calls[0][4] == "repos/acme/project/pulls/42"
    # Without the pull request, the contributor's unsigned commit is one the merge would vouch for.
    _git(repo, "reset", "-q", "--hard", fixup)
    with pytest.raises(GitRefused, match=f"carry no good signature of yours: {head}"):
        _merge(signing, policy, repo, onto, fixup)


def test_merge_into_a_pull_request_still_checks_an_unsigned_fixup(
    policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    signing, _ = _signing_git(tmp_path)
    fake, _, fixup = _contributor_pr(policy, repo)
    signing.gh_runner = fake
    onto = _upstream_moves_on(policy, repo, "fixup")
    with pytest.raises(GitRefused, match=f"carry no good signature of yours: {fixup}"):
        _merge(signing, policy, repo, onto, fixup, pr="42")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        pytest.param({"state": "closed"}, "not open", id="closed"),
        pytest.param({"base_repo": "other/project"}, "not against", id="other-base"),
        pytest.param({"head_sha": "0" * 40}, "does not build on", id="unknown-head"),
        pytest.param({"head_sha": None}, "no head commit", id="no-head"),
    ],
)
def test_merge_into_a_pull_request_refuses_what_the_forge_does_not_back(
    policy: LocalPolicy, repo: Path, tmp_path: Path, overrides: dict[str, object], message: str
) -> None:
    signing, signer = _signing_git(tmp_path)
    fake, _, _ = _contributor_pr(policy, repo, **overrides)
    signing.gh_runner = fake
    fixup = _sign_tip(repo, signer)
    onto = _upstream_moves_on(policy, repo, "fixup")
    with pytest.raises(GitRefused, match=message):
        _merge(signing, policy, repo, onto, fixup, pr="42")
    assert _git(repo, "rev-parse", "HEAD") == fixup


@pytest.mark.parametrize("pr", ["0", "#42", "-1", "all"])
def test_merge_upstream_pr_must_be_a_number_or_none(
    git: Git, policy: LocalPolicy, repo: Path, pr: str
) -> None:
    tip, onto = _diverged(repo)
    with pytest.raises(GitRefused, match=r"pull request number|may not"):
        _merge(git, policy, repo, onto, tip, pr=pr)


def test_merge_upstream_merges_the_upstream_commit_into_the_topic(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    tip, onto = _diverged(repo)
    message = _merge(git, policy, repo, onto, tip)
    merged = _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "rev-list", "--parents", "-n", "1", merged).split()[1:] == [tip, onto]
    assert _git(repo, "log", "-1", "--format=%s") == "Merge acme/project main into topic"
    assert (repo / "topic-file").exists() and (repo / "upstream-file").exists()
    assert f"{tip} -> {merged}" in message


def test_merge_upstream_keeps_the_branch_history(git: Git, policy: LocalPolicy, repo: Path) -> None:
    """Unlike a rebase, nothing on the branch is rewritten: the contributor's commits stay as they are."""
    tip, onto = _diverged(repo)
    _merge(git, policy, repo, onto, tip)
    assert _git(repo, "merge-base", "--is-ancestor", tip, "HEAD") == ""


def test_merge_upstream_conflict_is_aborted_and_named(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo, conflict=True)
    with pytest.raises(git_ops.GitFailed) as caught:
        _merge(git, policy, repo, onto, tip)
    assert "conflicting paths: one" in caught.value.stderr
    assert f"still at {tip}" in caught.value.stderr
    assert _git(repo, "rev-parse", "HEAD") == tip
    assert _git(repo, "status", "--porcelain") == ""
    assert not (repo / ".git" / "MERGE_HEAD").exists()


def test_merge_upstream_refusals(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo)
    with pytest.raises(GitRefused, match="not the expected"):
        _merge(git, policy, repo, onto, onto)
    _git(repo, "checkout", "-q", "-b", "local-only", "main")
    local = _commit(repo, "local")
    _git(repo, "update-ref", "refs/remotes/upstream/main", local)
    _git(repo, "checkout", "-q", "topic")
    with pytest.raises(GitRefused, match="is not on acme/project main"):
        _merge(git, policy, repo, local, tip)
    (repo / "topic-file").write_text("changed")
    with pytest.raises(GitRefused, match="uncommitted"):
        _merge(git, policy, repo, onto, tip)
    _git(repo, "checkout", "-q", "--", "topic-file")
    _git(repo, "checkout", "-q", "main")
    with pytest.raises(GitRefused, match="protected"):
        _merge(git, policy, repo, onto, _git(repo, "rev-parse", "HEAD"))
    assert _git(repo, "rev-parse", "topic") == tip


def test_merge_upstream_of_a_branch_already_on_the_base_does_nothing(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    tip, onto = _diverged(repo)
    _merge(git, policy, repo, onto, tip)
    merged = _git(repo, "rev-parse", "HEAD")
    assert "nothing to merge" in _merge(git, policy, repo, onto, merged)
    assert _git(repo, "rev-parse", "HEAD") == merged


def test_merge_upstream_never_runs_hooks(git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path) -> None:
    marker = tmp_path / "hook-ran"
    tip, onto = _diverged(repo)
    _hook(repo, "pre-merge-commit", marker, exit_code=1)
    _hook(repo, "post-merge", marker)
    _merge(git, policy, repo, onto, tip)
    assert not marker.exists()


def test_merge_upstream_signs_and_vouches_only_for_signed_commits(
    policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    signing, signer = _signing_git(tmp_path)
    _, onto = _diverged(repo)
    unsigned = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(GitRefused, match=f"carry no good signature of yours: {unsigned}"):
        _merge(signing, policy, repo, onto, unsigned)
    tip = _sign_tip(repo, signer)
    _merge(signing, policy, repo, onto, tip)
    assert "fake" in _git(repo, "cat-file", "commit", "HEAD")


def test_merge_upstream_dry_run_changes_nothing(git: Git, policy: LocalPolicy, repo: Path) -> None:
    tip, onto = _diverged(repo)
    command = _merge(git, policy, repo, onto, tip, dry_run=True)
    assert "merge" in command and "rerere.enabled=false" in command and onto in command
    assert _git(repo, "rev-parse", "HEAD") == tip


def test_push_pr_head_takes_upstream_merged_into_the_fixup(git: Git, policy: LocalPolicy, repo: Path) -> None:
    """`git-merge-upstream` on a contributor's branch, then the fast-forward of their head."""
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "user.email", "t@example.org")
    fake, head, _ = _contributor_pr(policy, repo)
    git.gh_runner = fake
    _git(repo, "checkout", "-q", "main")
    for name in (f"upstream-{n}" for n in range(git_ops.MAX_FIXUP_COMMITS + 1)):
        _commit(repo, name)
    onto = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-q", policy.push_url("acme/project"), "main:refs/heads/main")
    _git(repo, "checkout", "-q", "fixup")
    fixup = _git(repo, "rev-parse", "HEAD")
    _merge(git, policy, repo, onto, fixup)
    merged = _git(repo, "rev-parse", "HEAD")
    # More upstream commits than a fixup may add: they are upstream's, not the fixup's.
    _push_head(git, policy, repo, head)
    assert _remote_head(policy, "alice/project", "feature") == merged


def test_merge_upstream_takes_back_a_merge_onto_a_branch_moved_as_it_started(
    policy: LocalPolicy, repo: Path
) -> None:
    tip, onto = _diverged(repo)
    plain = _runner(os.devnull)

    def racing(argv: list[str], env: dict[str, str], cwd_fd: int | None) -> subprocess.CompletedProcess[str]:
        if "merge" in argv and "--abort" not in argv and "--is-ancestor" not in argv:
            _commit(repo, "sneaked-in")
        return plain(argv, env, cwd_fd)

    raced = Git(runner=racing, protocols=("https", "ssh", "file"))
    with pytest.raises(GitRefused, match="taken back off"):
        _merge(raced, policy, repo, onto, tip)
    assert _git(repo, "log", "-1", "--format=%s") == "sneaked-in"


# --- git-switch-create -----------------------------------------------------


def _switch_create(git: Git, policy: GitPolicy, worktree: Path, branch: str, dry_run: bool = False) -> str:
    return git_ops.switch_create(git, policy, {"worktree": str(worktree), "branch": branch}, dry_run)


def _upstream_moves_with_settings(repo: Path) -> str:
    """Upstream main gains a commit that changes the settings; the checkout stays on an older branch."""
    _git(repo, "checkout", "-q", "-b", "work")
    _git(repo, "checkout", "-q", "-b", "upstream-next", "main")
    upstream = _settings(repo, '{"v": 2}', "upstream moves settings")
    _git(
        repo,
        "push",
        "-q",
        str(repo.parent / "remotes" / "acme__project.git"),
        "upstream-next:refs/heads/main",
    )
    _git(repo, "checkout", "-q", "work")
    _git(repo, "branch", "-q", "-D", "upstream-next")
    return upstream


def test_switch_create_starts_a_branch_where_upstream_is_now(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    upstream = _upstream_moves_with_settings(repo)
    out = _switch_create(git, policy, repo, "fix-thing")
    assert _git(repo, "rev-parse", "HEAD") == upstream
    assert _git(repo, "symbolic-ref", "--short", "HEAD") == "fix-thing"
    # Upstream's own settings arrive with the new branch.
    assert (repo / ".claude" / "settings.json").read_text() == '{"v": 2}'
    assert "created fix-thing at upstream main" in out


def test_switch_create_ignores_a_local_ref_naming_another_upstream(
    git: Git, policy: LocalPolicy, repo: Path
) -> None:
    """The start is asked of the policy's URL, never read from `refs/remotes/upstream/main`."""
    upstream = _upstream_moves_with_settings(repo)
    planted = _commit(repo, "agent-made")
    _git(repo, "update-ref", "refs/remotes/upstream/main", planted)
    _git(repo, "reset", "-q", "--hard", "HEAD~1")
    _switch_create(git, policy, repo, "fix-thing")
    assert _git(repo, "rev-parse", "HEAD") == upstream


def test_switch_create_refusals(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _upstream_main(repo)
    _git(repo, "branch", "existing")
    with pytest.raises(GitRefused, match="already exists"):
        _switch_create(git, policy, repo, "existing")
    with pytest.raises(GitRefused, match="protected"):
        _switch_create(git, policy, repo, "release-1.0")
    (repo / "one").write_text("changed")
    with pytest.raises(GitRefused, match="uncommitted"):
        _switch_create(git, policy, repo, "fix-thing")
    assert not _git(repo, "for-each-ref", "refs/heads/fix-thing")


def test_switch_create_removes_a_branch_it_could_not_switch_to(policy: LocalPolicy, repo: Path) -> None:
    _upstream_main(repo)
    plain = _runner(os.devnull)

    def failing(argv: list[str], env: dict[str, str], cwd_fd: int | None) -> subprocess.CompletedProcess[str]:
        if "switch" in argv:
            return subprocess.CompletedProcess(argv, 1, "", "error: simulated checkout failure\n")
        return plain(argv, env, cwd_fd)

    broken = Git(runner=failing, protocols=("https", "ssh", "file"))
    with pytest.raises(git_ops.GitFailed):
        _switch_create(broken, policy, repo, "fix-thing")
    assert not _git(repo, "for-each-ref", "refs/heads/fix-thing")
    assert _git(repo, "symbolic-ref", "--short", "HEAD") == "main"


def test_switch_create_dry_run_changes_nothing(git: Git, policy: LocalPolicy, repo: Path) -> None:
    _upstream_main(repo)
    command = _switch_create(git, policy, repo, "fix-thing", dry_run=True)
    assert "fix-thing" in command and "git-switch" in command
    assert not _git(repo, "for-each-ref", "refs/heads/fix-thing")
