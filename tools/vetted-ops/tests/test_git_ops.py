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

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from vetted_ops import git_ops
from vetted_ops.config import Config, ConfigError, account_home
from vetted_ops.git_ops import Git, GitPolicy, GitRefused


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
    hooks: str = "verify",
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
            "hooks": hooks,
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


def test_a_failing_hooks_stdout_is_kept(git: Git, policy: LocalPolicy, repo: Path) -> None:
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\necho 'static checks failed: run prek'\nexit 1\n")
    hook.chmod(0o755)
    _git(repo, "branch", "topic")
    with pytest.raises(git_ops.GitFailed) as failed:
        _push(git, policy, repo, "topic", "fork", "topic", "new")
    assert "static checks failed" in failed.value.stdout + failed.value.stderr


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


def test_push_runs_the_pre_push_hook(git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path) -> None:
    marker = tmp_path / "hook-ran"
    _hook(repo, "pre-push", marker)
    _git(repo, "branch", "topic")
    message = _push(git, policy, repo, "topic", "fork", "topic", "new")
    assert marker.exists()
    assert "skipped" not in message


def test_a_failing_pre_push_hook_stops_the_push(
    git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    _hook(repo, "pre-push", tmp_path / "hook-ran", exit_code=1)
    _git(repo, "branch", "topic")
    with pytest.raises(git_ops.GitFailed):
        _push(git, policy, repo, "topic", "fork", "topic", "new")
    with pytest.raises(subprocess.CalledProcessError):
        _remote_head(policy, "me/project", "topic")


def test_no_verify_skips_the_pre_push_hook_and_says_so(
    git: Git, policy: LocalPolicy, repo: Path, tmp_path: Path
) -> None:
    marker = tmp_path / "hook-ran"
    _hook(repo, "pre-push", marker, exit_code=1)
    _git(repo, "branch", "topic")
    message = _push(git, policy, repo, "topic", "fork", "topic", "new", hooks="no-verify")
    assert not marker.exists()
    assert "pre-push hook skipped" in message


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
        ("hooks", "maybe", "verify"),
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
        "hooks": "verify",
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
    assert "core.hooksPath" not in printed
    assert "--no-verify" not in printed
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


def test_clean_env_drops_git_variables() -> None:
    env = git_ops.clean_env({"PATH": "/bin", "GIT_SSH_COMMAND": "evil", "GIT_DIR": "/x"})
    assert env == {"PATH": "/bin", "HOME": str(account_home()), "GIT_TERMINAL_PROMPT": "0"}


def test_parse_config_scopes_handles_both_separators() -> None:
    assert git_ops.parse_config_scopes("local\x00core.bare\x00global\x00user.name\x00") == [
        ("local", "core.bare"),
        ("global", "user.name"),
    ]
    assert git_ops.parse_config_scopes("local\tcore.bare\x00") == [("local", "core.bare")]
