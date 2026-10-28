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
"""A writable bind never covers a file that configures or runs code outside the sandbox.

The harness refuses sandboxed writes to `.claude/settings*.json`,
`.claude/hooks`, `.claude/skills` and the git directory's `hooks` and
`config`; a container is started by the daemon, which the sandbox does not
confine, so the gateway refuses any writable bind that is, contains or sits
under one of them. A read-only bind of the same source is allowed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from container_gateway.policy import Deny, PolicyContext, check_create, write_protected_paths


def _ctx(root: Path, *extra: Path) -> PolicyContext:
    return PolicyContext(
        slug="-proj",
        project_root=root,
        bind_roots=(root, *extra),
        proxy_env=None,
        egress_mode="off",
    )


@pytest.fixture
def root(tmp_path: Path) -> Path:
    r = tmp_path / "proj"
    (r / ".git" / "hooks").mkdir(parents=True)
    (r / ".git" / "config").write_text("[core]\n")
    (r / ".claude" / "hooks").mkdir(parents=True)
    (r / ".claude" / "settings.json").write_text("{}\n")
    (r / "src").mkdir()
    return r.resolve()


def _binds(spec: str) -> dict[str, Any]:
    return {"Image": "alpine", "HostConfig": {"Binds": [spec]}}


def _compat_mount(source: Path, read_only: bool | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"Type": "bind", "Source": str(source), "Target": "/w"}
    if read_only is not None:
        entry["ReadOnly"] = read_only
    return {"Image": "alpine", "HostConfig": {"Mounts": [entry]}}


def _libpod_mount(source: Path, options: list[str] | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"type": "bind", "source": str(source), "destination": "/w"}
    if options is not None:
        entry["options"] = options
    return {"image": "alpine", "mounts": [entry]}


def _refused(body: dict[str, Any], ctx: PolicyContext, *, libpod: bool = False) -> bool:
    d = check_create(body, ctx, libpod=libpod)
    if d is None:
        return False
    assert isinstance(d, Deny) and d.reason.startswith("bind-mount:"), d.reason
    return True


# --- covering binds ---------------------------------------------------------------


@pytest.mark.parametrize(
    "rel",
    [
        "",  # the project root
        ".claude",
        ".claude/hooks",
        ".claude/hooks/pre.sh",
        ".claude/skills",  # missing today: still protected, a writable parent could create it
        ".claude/settings.json",
        ".claude/settings.local.json",
        ".git",
        ".git/hooks",
        ".git/config",
    ],
)
def test_a_writable_bind_covering_a_protected_path_is_refused(root: Path, rel: str) -> None:
    src = root / rel if rel else root
    ctx = _ctx(root)
    assert _refused(_binds(f"{src}:/w"), ctx)
    assert _refused(_binds(f"{src}:/w:rw"), ctx)
    assert _refused(_compat_mount(src), ctx)
    assert _refused(_compat_mount(src, read_only=False), ctx)
    assert _refused(_libpod_mount(src), ctx, libpod=True)
    assert _refused(_libpod_mount(src, ["rbind"]), ctx, libpod=True)


def test_the_refusal_names_the_path_and_the_way_out(root: Path) -> None:
    d = check_create(_binds(f"{root}:/w"), _ctx(root), libpod=False)
    assert isinstance(d, Deny)
    assert "is writable and covers" in d.reason
    assert "read-only (:ro)" in d.reason


@pytest.mark.parametrize("rel", ["", ".claude", ".git", ".claude/settings.json"])
def test_a_read_only_bind_of_the_same_source_is_allowed(root: Path, rel: str) -> None:
    src = root / rel if rel else root
    ctx = _ctx(root)
    assert check_create(_binds(f"{src}:/w:ro"), ctx, libpod=False) is None
    assert check_create(_binds(f"{src}:/w:ro,z"), ctx, libpod=False) is None
    assert check_create(_compat_mount(src, read_only=True), ctx, libpod=False) is None
    assert check_create(_libpod_mount(src, ["rbind", "ro"]), ctx, libpod=True) is None


@pytest.mark.parametrize(
    "options",
    [
        ["ro", "rw"],  # a writable option alongside undoes it
        ["RO"],  # not a spelling the policy trusts the daemon to read as read-only
        ["readonly=false"],
        ["ro=false"],
        # runc reads these as filesystem data, not as the read-only flag
        ["ro=true"],
        ["readonly=true"],
        ["readonly"],
        # `U` chowns the source on the host, read-only or not
        ["ro", "U"],
    ],
)
def test_an_ambiguous_read_only_option_counts_as_writable(root: Path, options: list[str]) -> None:
    assert _refused(_libpod_mount(root, options), _ctx(root), libpod=True)


def test_a_truthy_but_non_boolean_read_only_counts_as_writable(root: Path) -> None:
    body = _compat_mount(root)
    body["HostConfig"]["Mounts"][0]["ReadOnly"] = "true"
    assert check_create(body, _ctx(root), libpod=False) is not None


def test_a_binds_entry_with_rw_after_ro_counts_as_writable(root: Path) -> None:
    assert _refused(_binds(f"{root}:/w:ro,rw"), _ctx(root))


@pytest.mark.parametrize(
    "options",
    [["O"], ["O", "upperdir=/tmp/up", "workdir=/tmp/work"], ["ro", "upperdir=/tmp/up"]],
)
def test_overlay_options_are_refused(root: Path, options: list[str]) -> None:
    src = root / "src"
    ctx = _ctx(root)
    assert check_create(_binds(f"{src}:/w:{','.join(options)}"), ctx, libpod=False) is not None
    assert check_create(_libpod_mount(src, options), ctx, libpod=True) is not None


def test_a_binds_entry_with_ro_and_chown_counts_as_writable(root: Path) -> None:
    assert _refused(_binds(f"{root}:/w:ro,U"), _ctx(root))


@pytest.mark.parametrize("rel", [".claude/commands", ".claude/agents", ".mcp.json"])
def test_agent_config_paths_are_protected(root: Path, rel: str) -> None:
    assert _refused(_binds(f"{root / rel}:/w"), _ctx(root))


@pytest.mark.parametrize(
    "rel",
    [
        ".agents",
        ".agents/hooks.json",
        ".agents/mcp_config.json",
        ".agent/hooks.json",
        ".codex",
        ".codex/config.toml",
        ".codex/rules",
        ".github/hooks",
        ".github/copilot/settings.json",
        ".github/skills",
        ".gemini/settings.json",
        ".grok/hooks",
        ".junie/mcp/mcp.json",
        ".kiro/agents",
        ".opencode/plugin",
        "opencode.json",
        ".pi",
        ".cursor/rules",
        ".aider.conf.yml",
    ],
)
def test_other_harnesses_config_paths_are_protected(root: Path, rel: str) -> None:
    """Each harness the gateway may serve runs code from its workspace config."""
    assert _refused(_binds(f"{root / rel}:/w"), _ctx(root))


def test_the_worktrees_directory_is_protected_before_any_worktree_exists(root: Path) -> None:
    """A worktree created while the container runs would sit under the bind."""
    worktrees = root / ".claude" / "worktrees"
    worktrees.mkdir(parents=True)
    ctx = _ctx(root)
    assert _refused(_binds(f"{worktrees}:/w"), ctx)
    assert _refused(_binds(f"{root / '.claude'}:/w"), ctx)
    assert _refused(_binds(f"{worktrees}:/w"), _ctx(root.parent / "elsewhere", root))


def test_a_worktrees_own_worktrees_directory_is_protected(root: Path) -> None:
    wt = root / ".claude" / "worktrees" / "wt"
    (wt / ".claude" / "worktrees").mkdir(parents=True)
    (wt / "build").mkdir()
    ctx = _ctx(root)
    assert _refused(_binds(f"{wt / '.claude' / 'worktrees'}:/w"), ctx)
    assert check_create(_binds(f"{wt / 'build'}:/w"), ctx, libpod=False) is None


# --- what keeps working ---------------------------------------------------------


def test_a_writable_bind_of_a_subdirectory_without_protected_paths_is_allowed(root: Path) -> None:
    ctx = _ctx(root)
    src = root / "src"
    assert check_create(_binds(f"{src}:/w"), ctx, libpod=False) is None
    assert check_create(_compat_mount(src), ctx, libpod=False) is None
    assert check_create(_libpod_mount(src, ["rbind"]), ctx, libpod=True) is None


def test_a_sibling_under_dot_claude_stays_bindable(root: Path) -> None:
    """Only the listed entries are protected, not every file under `.claude/`."""
    other = root / ".claude" / "output-styles"
    other.mkdir(parents=True)
    assert check_create(_binds(f"{other}:/w"), _ctx(root), libpod=False) is None


def test_nested_agent_worktrees_are_protected(root: Path) -> None:
    """Each `.claude/worktrees/<name>` has its own `.git` and `.claude/`."""
    wt = root / ".claude" / "worktrees" / "wt"
    (wt / "build").mkdir(parents=True)
    ctx = _ctx(root)
    assert _refused(_binds(f"{wt}:/w"), ctx)
    assert _refused(_binds(f"{wt / '.claude' / 'settings.json'}:/w"), ctx)
    assert check_create(_binds(f"{wt / 'build'}:/w"), ctx, libpod=False) is None


# --- other spellings of the same path -----------------------------------------------


def test_a_symlink_into_a_protected_path_is_refused(root: Path) -> None:
    link = root / "src" / "hooks-link"
    link.symlink_to(root / ".git" / "hooks")
    assert _refused(_binds(f"{link}:/w"), _ctx(root))


def test_a_case_variant_spelling_is_refused(root: Path) -> None:
    """`.Claude/hooks` is `.claude/hooks` on a case-insensitive file system."""
    assert _refused(_binds(f"{root}/.Claude/hooks:/w"), _ctx(root))
    assert _refused(_binds(f"{root}/.GIT:/w"), _ctx(root))


def test_a_symlinked_dot_claude_is_protected_where_it_points(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    elsewhere = root / "src" / "real-claude"
    elsewhere.mkdir(parents=True)
    (root / ".claude").symlink_to(elsewhere)
    root = root.resolve()
    assert _refused(_binds(f"{root / 'src' / 'real-claude'}:/w"), _ctx(root))
    assert check_create(_binds(f"{root / 'src' / 'real-claude'}:/w:ro"), _ctx(root), libpod=False) is None


def test_the_worktrees_directory_behind_a_symlinked_dot_claude_is_protected(tmp_path: Path) -> None:
    """Before it exists, so file identity cannot match it: `-v` would create it."""
    root = tmp_path / "proj"
    root.mkdir()
    elsewhere = root / "src" / "real-claude"
    elsewhere.mkdir(parents=True)
    (root / ".claude").symlink_to(elsewhere)
    root = root.resolve()
    assert _refused(_binds(f"{root / 'src' / 'real-claude' / 'worktrees'}:/w"), _ctx(root))


# --- linked worktrees -------------------------------------------------------------


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    common = main / ".git"
    (common / "hooks").mkdir(parents=True)
    (common / "config").write_text("[core]\n")
    (common / "HEAD").write_text("ref: refs/heads/main\n")
    (common / "objects").mkdir()
    wt_gitdir = common / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    (wt / "src").mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    (wt_gitdir / "gitdir").write_text(f"{wt / '.git'}\n")
    return main.resolve(), wt.resolve()


def test_write_protected_paths_resolve_the_real_git_dir_of_a_worktree(tmp_path: Path) -> None:
    main, wt = _linked_worktree(tmp_path)
    paths = write_protected_paths(wt)
    assert wt / ".git" in paths
    assert main / ".git" / "hooks" in paths
    assert main / ".git" / "config" in paths
    assert main / ".git" / "worktrees" / "wt" in paths


def test_a_worktrees_dot_git_file_is_never_under_a_writable_bind(tmp_path: Path) -> None:
    _, wt = _linked_worktree(tmp_path)
    ctx = _ctx(wt)
    assert _refused(_binds(f"{wt}:/w"), ctx)
    assert _refused(_binds(f"{wt / '.git'}:/w"), ctx)
    assert check_create(_binds(f"{wt / 'src'}:/w"), ctx, libpod=False) is None


def test_the_common_git_dir_under_an_extra_bind_root_is_protected(tmp_path: Path) -> None:
    """The main checkout's git dir is outside the worktree, but an extra root can reach it."""
    main, wt = _linked_worktree(tmp_path)
    ctx = _ctx(wt, main)
    assert _refused(_binds(f"{main / '.git' / 'hooks'}:/w"), ctx)
    assert _refused(_binds(f"{main / '.git' / 'config'}:/w"), ctx)
    assert _refused(_binds(f"{main / '.git' / 'worktrees' / 'wt'}:/w"), ctx)
    assert _refused(_binds(f"{main}:/w"), ctx)
    (main / "lib").mkdir()
    assert check_create(_binds(f"{main / 'lib'}:/w"), ctx, libpod=False) is None


def test_the_snapshot_taken_at_start_still_protects_after_the_git_file_moves(tmp_path: Path) -> None:
    """Rewriting `.git` mid-session must not move the real git dir out of view."""
    main, wt = _linked_worktree(tmp_path)
    common = main / ".git"
    # The extra root is the common dir itself, so only the worktree's `.git`
    # file leads to its hooks, config and worktree git dir.
    snapshot = write_protected_paths(wt, common)
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (wt / ".git").write_text(f"gitdir: {decoy}\n")
    live_only = _ctx(wt, common)
    with_snapshot = PolicyContext(
        slug="-wt",
        project_root=wt,
        bind_roots=(wt, common),
        proxy_env=None,
        egress_mode="off",
        write_protected=snapshot,
    )
    for rel in ("hooks", "config", "worktrees/wt"):
        spec = f"{common / rel}:/w"
        assert check_create(_binds(spec), live_only, libpod=False) is None  # what the snapshot is for
        assert _refused(_binds(spec), with_snapshot)


def test_the_daemon_context_snapshots_the_protected_paths(tmp_path: Path) -> None:
    import argparse

    from container_gateway import __main__ as cli
    from container_gateway import daemon
    from container_gateway.backends import Backend

    main, wt = _linked_worktree(tmp_path)
    ns = argparse.Namespace(project=wt, run_dir=tmp_path / "run", pid_file=None)
    cfg = cli._config(ns, serving=True)
    ctx = daemon.build_context(cfg, Backend("podman", Path("/x.sock"), "host.containers.internal"), None)
    assert main / ".git" / "hooks" in ctx.write_protected
    assert main / ".git" / "config" in ctx.write_protected
    assert wt / ".claude" / "settings.json" in ctx.write_protected
    # The main checkout of a linked worktree carries its own harness settings.
    assert main / ".claude" / "settings.local.json" in ctx.write_protected


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="needs symlinks")
def test_a_bind_root_reached_through_a_symlink_still_protects(tmp_path: Path) -> None:
    real = tmp_path / "real"
    (real / ".claude" / "hooks").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(real)
    ctx = _ctx(link)
    assert _refused(_binds(f"{real}:/w"), ctx)
    assert _refused(_binds(f"{link / '.claude' / 'hooks'}:/w"), ctx)
