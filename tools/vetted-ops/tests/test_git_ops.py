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
import subprocess
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


def test_the_checks_command_is_never_excluded_from_the_sandbox() -> None:
    """It runs the working tree's hooks; out of the sandbox it would be the very escape it prevents."""
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())
    template = REPO_ROOT / "tools" / "agent-isolation" / "claude-settings.local.template.json"
    excluded = [
        *settings.get("sandbox", {}).get("excludedCommands", []),
        *json.loads(template.read_text()).get("sandbox", {}).get("excludedCommands", []),
    ]
    command = f"uvx --from ~/.claude/magpie/vetted-ops {checks.PROG} /wt /ws/p"
    assert not [p for p in excluded if fnmatch.fnmatchcase(command, p)]


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
