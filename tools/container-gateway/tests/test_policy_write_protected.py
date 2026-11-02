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

from container_gateway import policy
from container_gateway.policy import (
    Deny,
    PolicyContext,
    apply_create_rewrites,
    check_create,
    write_protected_paths,
)


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


def _split(src: Path, ctx: PolicyContext) -> dict[str, bool]:
    """The binds a writable `Binds` entry of `src` becomes: container path -> read-only."""
    body = _binds(f"{src}:/w")
    assert check_create(body, ctx, libpod=False) is None
    out = apply_create_rewrites(body, ctx, libpod=False)
    split: dict[str, bool] = {}
    for spec in out["HostConfig"]["Binds"]:
        parts = spec.split(":")
        split[parts[1]] = len(parts) == 3 and "ro" in parts[2].split(",")
    return split


def _writable(split: dict[str, bool], target: str) -> bool:
    """Whether `target` is writable inside the container: its nearest mount decides."""
    covering = [t for t in split if target == t or target.startswith(t.rstrip("/") + "/")]
    return not split[max(covering, key=len)]


# --- covering binds ---------------------------------------------------------------


@pytest.mark.parametrize(
    "rel",
    [
        # The project root is split instead (see the "splitting a checkout root" tests).
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
    d = check_create(_binds(f"{root / '.claude'}:/w"), _ctx(root), libpod=False)
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
        ".env",
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


def test_a_path_in_a_worktree_that_does_not_exist_yet_is_refused(root: Path) -> None:
    """`-v` would create it, and the container would fill it before a worktree is made."""
    (root / ".claude" / "worktrees").mkdir(parents=True)
    ctx = _ctx(root)
    assert _refused(_binds(f"{root / '.claude' / 'worktrees' / 'new'}:/w"), ctx)
    assert _refused(_binds(f"{root / '.claude' / 'worktrees' / 'new' / 'src'}:/w"), ctx)


def test_worktrees_nested_at_any_depth_are_protected(root: Path) -> None:
    deep = root / ".claude" / "worktrees" / "a" / ".claude" / "worktrees" / "b"
    (deep / "build").mkdir(parents=True)
    (deep / ".claude" / "worktrees").mkdir(parents=True)
    ctx = _ctx(root)
    assert _refused(_binds(f"{deep / '.claude' / 'settings.json'}:/w"), ctx)
    assert _refused(_binds(f"{deep / '.git'}:/w"), ctx)
    assert _refused(_binds(f"{deep / '.claude' / 'worktrees'}:/w"), ctx)
    assert _refused(_binds(f"{deep / '.claude' / 'worktrees' / 'c'}:/w"), ctx)
    assert check_create(_binds(f"{deep / 'build'}:/w"), ctx, libpod=False) is None


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
    split = _split(wt, ctx)
    assert not _writable(split, "/w/.git")
    assert _writable(split, "/w/src")
    assert _refused(_binds(f"{wt / '.git'}:/w"), ctx)
    assert check_create(_binds(f"{wt / 'src'}:/w"), ctx, libpod=False) is None


def test_the_common_git_dir_under_an_extra_bind_root_is_protected(tmp_path: Path) -> None:
    """The main checkout's git dir is outside the worktree, but an extra root can reach it."""
    main, wt = _linked_worktree(tmp_path)
    ctx = _ctx(wt, main)
    assert _refused(_binds(f"{main / '.git' / 'hooks'}:/w"), ctx)
    assert _refused(_binds(f"{main / '.git' / 'config'}:/w"), ctx)
    assert _refused(_binds(f"{main / '.git' / 'worktrees' / 'wt'}:/w"), ctx)
    split = _split(main, ctx)
    for rel in (".git", ".git/hooks", ".git/config", ".git/worktrees/wt"):
        assert not _writable(split, f"/w/{rel}")
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
    split = _split(real, ctx)
    assert not _writable(split, "/w/.claude/hooks")
    assert _refused(_binds(f"{link / '.claude' / 'hooks'}:/w"), ctx)


# --- splitting a checkout root ------------------------------------------------------


def test_a_writable_checkout_root_is_split_rather_than_refused(root: Path) -> None:
    split = _split(root, _ctx(root))
    assert split["/w"] is True  # the root itself is read-only
    assert _writable(split, "/w/src")
    assert _writable(split, "/w/src/pkg/module.py")
    for rel in (".claude/settings.json", ".claude/hooks", ".git", ".git/hooks", ".git/config"):
        assert not _writable(split, f"/w/{rel}"), rel


@pytest.mark.parametrize("rel", [".mcp.json", ".claude/skills", ".claude/settings.local.json", ".env"])
def test_a_protected_path_missing_today_cannot_be_created_through_the_split(root: Path, rel: str) -> None:
    """The root and `.claude` are read-only, so the container cannot create these."""
    assert not (root / rel).exists()
    assert not _writable(_split(root, _ctx(root)), f"/w/{rel}")


def test_a_compat_mount_of_a_checkout_root_is_split(root: Path) -> None:
    ctx = _ctx(root)
    body = _compat_mount(root)
    assert check_create(body, ctx, libpod=False) is None
    mounts = apply_create_rewrites(body, ctx, libpod=False)["HostConfig"]["Mounts"]
    by_target = {m["Target"]: m["ReadOnly"] for m in mounts}
    assert by_target["/w"] is True
    assert by_target["/w/src"] is False
    assert all(m["Type"] == "bind" for m in mounts)


def test_a_libpod_mount_of_a_checkout_root_is_split(root: Path) -> None:
    ctx = _ctx(root)
    body = _libpod_mount(root, ["rbind"])
    assert check_create(body, ctx, libpod=True) is None
    mounts = apply_create_rewrites(body, ctx, libpod=True)["mounts"]
    by_target = {m["destination"]: m["options"] for m in mounts}
    assert by_target["/w"] == ["rbind", "ro"]
    assert by_target["/w/src"] == ["rbind"]


def test_the_split_keeps_the_relabel_option_on_every_mount(root: Path) -> None:
    ctx = _ctx(root)
    body = _binds(f"{root}:/w:rw,z")
    assert check_create(body, ctx, libpod=False) is None
    binds = apply_create_rewrites(body, ctx, libpod=False)["HostConfig"]["Binds"]
    assert f"{root}:/w:z,ro" in binds
    assert f"{root / 'src'}:/w/src:z" in binds


@pytest.mark.parametrize("options", ["rprivate", "ro,rw", "U"])
def test_a_checkout_root_with_options_the_split_cannot_reproduce_is_still_refused(
    root: Path, options: str
) -> None:
    assert _refused(_binds(f"{root}:/w:{options}"), _ctx(root))


def test_a_claude_code_worktree_root_is_split_with_its_own_entries_protected(root: Path) -> None:
    wt = root / ".claude" / "worktrees" / "feature"
    (wt / "src").mkdir(parents=True)
    (wt / ".claude").mkdir()
    (wt / ".claude" / "settings.json").write_text("{}\n")
    (wt / ".git").write_text("gitdir: ../../../.git/worktrees/feature\n")
    split = _split(wt, _ctx(root))
    assert _writable(split, "/w/src")
    assert not _writable(split, "/w/.claude/settings.json")
    assert not _writable(split, "/w/.git")


def test_new_worktrees_cannot_be_created_through_the_split(root: Path) -> None:
    (root / ".claude" / "worktrees").mkdir()
    assert not _writable(_split(root, _ctx(root)), "/w/.claude/worktrees/new")


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="needs symlinks")
def test_a_symlinked_child_stays_read_only(root: Path, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (root / "linked").symlink_to(elsewhere)
    split = _split(root, _ctx(root))
    assert "/w/linked" not in split
    assert not _writable(split, "/w/linked")


def test_a_subdirectory_that_is_not_a_checkout_root_is_not_split(root: Path) -> None:
    """Only checkout roots are split: a writable bind of `.claude` is refused, not split."""
    assert _refused(_binds(f"{root / '.claude'}:/w"), _ctx(root))


def test_a_split_past_the_mount_limit_is_refused(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy, "_SPLIT_MAX_MOUNTS", 1)
    assert _refused(_binds(f"{root}:/w"), _ctx(root))


def test_a_split_that_can_no_longer_be_computed_fails_safe_to_read_only(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the tree changes between the check and the rewrite, the bind becomes read-only."""
    ctx = _ctx(root)
    body = _binds(f"{root}:/w")
    assert check_create(body, ctx, libpod=False) is None
    monkeypatch.setattr(policy, "split_writable_bind", lambda src, ctx: None)
    assert apply_create_rewrites(body, ctx, libpod=False)["HostConfig"]["Binds"] == [f"{root}:/w:ro"]


def test_a_bind_without_protected_paths_is_left_alone(root: Path) -> None:
    ctx = _ctx(root)
    body = _binds(f"{root / 'src'}:/w")
    assert apply_create_rewrites(body, ctx, libpod=False)["HostConfig"]["Binds"] == [f"{root / 'src'}:/w"]


def test_an_explicit_nested_mount_wins_over_the_split(root: Path) -> None:
    """`-v $PWD:/w -v $PWD/src:/w/src:ro` must not also generate a writable /w/src."""
    ctx = _ctx(root)
    body = {"Image": "alpine", "HostConfig": {"Binds": [f"{root}:/w", f"{root / 'src'}:/w/src:ro"]}}
    assert check_create(body, ctx, libpod=False) is None
    binds = apply_create_rewrites(body, ctx, libpod=False)["HostConfig"]["Binds"]
    at_src = [b for b in binds if b.split(":")[1] == "/w/src"]
    assert at_src == [f"{root / 'src'}:/w/src:ro"]


def test_an_explicit_mount_above_the_split_target_does_not_shadow_it(root: Path) -> None:
    ctx = _ctx(root)
    body = {"Image": "alpine", "HostConfig": {"Binds": [f"{root}:/w/proj"], "Tmpfs": {"/w": ""}}}
    assert check_create(body, ctx, libpod=False) is None
    binds = apply_create_rewrites(body, ctx, libpod=False)["HostConfig"]["Binds"]
    assert f"{root / 'src'}:/w/proj/src" in binds


def test_a_child_with_a_colon_in_its_name_becomes_a_structured_mount(root: Path) -> None:
    (root / "cache:dev").mkdir()
    ctx = _ctx(root)
    body = _binds(f"{root}:/w")
    assert check_create(body, ctx, libpod=False) is None
    hc = apply_create_rewrites(body, ctx, libpod=False)["HostConfig"]
    assert not any("cache:dev" in b for b in hc["Binds"])
    assert {
        "Type": "bind",
        "Source": str(root / "cache:dev"),
        "Target": "/w/cache:dev",
        "ReadOnly": False,
    } in hc["Mounts"]


def test_a_colon_child_with_relabelling_stays_read_only_under_its_parent(root: Path) -> None:
    (root / "cache:dev").mkdir()
    ctx = _ctx(root)
    body = _binds(f"{root}:/w:z")
    assert check_create(body, ctx, libpod=False) is None
    hc = apply_create_rewrites(body, ctx, libpod=False)["HostConfig"]
    assert not any("cache:dev" in b for b in hc["Binds"])
    assert not any("cache:dev" in str(m) for m in hc.get("Mounts") or [])
    assert f"{root}:/w:z,ro" in hc["Binds"]


def test_an_anonymous_volume_is_not_overridden_by_a_generated_bind(root: Path) -> None:
    (root / "node_modules").mkdir()
    ctx = _ctx(root)
    body = {"Image": "alpine", "Volumes": {"/w/node_modules": {}}, "HostConfig": {"Binds": [f"{root}:/w"]}}
    assert check_create(body, ctx, libpod=False) is None
    binds = apply_create_rewrites(body, ctx, libpod=False)["HostConfig"]["Binds"]
    assert not any(b.split(":")[1] == "/w/node_modules" for b in binds)


def test_an_explicit_mount_spelled_with_a_dot_segment_still_wins(root: Path) -> None:
    ctx = _ctx(root)
    body = {"Image": "alpine", "HostConfig": {"Binds": [f"{root}:/w", f"{root / 'src'}:/w/./src:ro"]}}
    assert check_create(body, ctx, libpod=False) is None
    binds = apply_create_rewrites(body, ctx, libpod=False)["HostConfig"]["Binds"]
    assert not any(b.split(":")[1] == "/w/src" for b in binds)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="needs symlinks")
def test_the_read_only_root_survives_a_symlink_to_a_checkout_with_a_colon(tmp_path: Path) -> None:
    real = tmp_path / "real:checkout"
    (real / ".git").mkdir(parents=True)
    (real / ".claude").mkdir()
    (real / ".claude" / "settings.json").write_text("{}\n")
    (real / "src").mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    ctx = _ctx(real.resolve())
    body = _binds(f"{link}:/w:z")
    assert check_create(body, ctx, libpod=False) is None
    hc = apply_create_rewrites(body, ctx, libpod=False)["HostConfig"]
    assert hc["Binds"] == [f"{link}:/w:z,ro"]
    assert not hc.get("Mounts")
