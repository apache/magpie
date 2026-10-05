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

"""Where config lives — the same vectors as `tools/setup-preflight/tests/test_layers.py`."""

from __future__ import annotations

from pathlib import Path

from container_gateway import layers

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


# --- the layers ---------------------------------------------------------------------


def test_layers_unadopted_repo_uses_the_git_dir_home(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert layers.config_layers(tmp_path) == [
        tmp_path / ".git" / "apache-magpie",
        tmp_path / ".apache-magpie-overrides",
    ]


def test_layers_adopted_repo_uses_the_in_tree_local_dir(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".apache-magpie.lock").write_text("method: local\n")
    (tmp_path / ".apache-magpie-local").mkdir()
    assert layers.config_layers(tmp_path) == [
        tmp_path / ".apache-magpie-local",
        tmp_path / ".apache-magpie-overrides",
    ]


def test_layers_legacy_in_tree_dir_is_a_read_fallback(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".apache-magpie-local").mkdir()
    assert layers.config_layers(tmp_path) == [
        tmp_path / ".git" / "apache-magpie",
        tmp_path / ".apache-magpie-local",
        tmp_path / ".apache-magpie-overrides",
    ]


def test_layers_not_a_repo_and_not_adopted_has_no_personal_layer(tmp_path: Path) -> None:
    assert layers.personal_dir(tmp_path) is None
    assert layers.config_layers(tmp_path) == [tmp_path / ".apache-magpie-overrides"]


def test_layers_never_create_anything(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    layers.config_layers(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == [".git"]
    assert list((tmp_path / ".git").iterdir()) == []


# --- the gateway's run directory ----------------------------------------------------


def test_run_dir_adopted_is_in_tree(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".apache-magpie.lock").write_text("method: local\n")
    assert layers.default_run_dir(tmp_path) == tmp_path / ".apache-magpie-local" / "run"


def test_run_dir_unadopted_is_in_the_git_dir(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert layers.default_run_dir(tmp_path) == tmp_path / ".git" / "apache-magpie" / "run" / "main"


def test_run_dir_of_a_linked_worktree_is_under_the_common_dir(tmp_path: Path) -> None:
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    assert layers.default_run_dir(wt) == main / ".git" / "apache-magpie" / "run" / "wt"
    assert layers.default_run_dir(main) == main / ".git" / "apache-magpie" / "run" / "main"


def test_run_dir_ignores_a_legacy_in_tree_dir_when_unadopted(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".apache-magpie-local" / "run").mkdir(parents=True)
    assert layers.default_run_dir(tmp_path) == tmp_path / ".git" / "apache-magpie" / "run" / "main"


def test_run_dir_outside_a_repo_unadopted_is_none(tmp_path: Path) -> None:
    assert layers.default_run_dir(tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_run_dir_candidates_name_both_locations(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert layers.run_dir_candidates(tmp_path) == [
        tmp_path / ".apache-magpie-local" / "run",
        tmp_path / ".git" / "apache-magpie" / "run" / "main",
    ]


def test_worktree_ids(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert layers.worktree_id(tmp_path) == "main"
    assert layers.worktree_id(tmp_path / "nowhere") is None


def test_an_unsafe_worktree_name_is_refused(tmp_path: Path) -> None:
    import pytest

    bad = tmp_path / "main" / ".git" / "worktrees" / "we ird$"
    bad.mkdir(parents=True)
    (bad / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {bad}\n")
    with pytest.raises(layers.InvalidWorktreeId):
        layers.default_run_dir(wt)
    # Recognition never raises: it just offers no git-directory candidate.
    assert layers.run_dir_candidates(wt) == [wt / ".apache-magpie-local" / "run"]


def test_valid_worktree_id() -> None:
    assert layers.valid_worktree_id("feat.x_1-2")
    for bad in ("", ".", "..", "a/b", "a b", "ä"):
        assert not layers.valid_worktree_id(bad)


# --- the CLI's default, the guards, and the bind policy -----------------------------


def _ns(project: Path):
    import argparse

    return argparse.Namespace(project=project, run_dir=None, pid_file=None)


def _git_dir(path: Path) -> None:
    """Just enough of a git directory for the gateway's anchor check."""
    (path / "objects").mkdir(parents=True)
    (path / "HEAD").write_text("ref: refs/heads/main\n")


def _link_worktree(main: Path, wt: Path, name: str) -> Path:
    """Link `wt` to `main` the way `git worktree add` does, both directions."""
    wt_gitdir = main / ".git" / "worktrees" / name
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    (wt_gitdir / "gitdir").write_text(f"{wt / '.git'}\n")
    return wt_gitdir


def _worktree(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    _git_dir(main / ".git")
    wt = tmp_path / "wt"
    _link_worktree(main, wt, "wt")
    return main, wt


def test_config_unadopted_serves_from_the_git_dir_home(tmp_path: Path) -> None:
    from container_gateway import __main__ as cli
    from container_gateway import daemon

    (tmp_path / ".git").mkdir()
    cfg = cli._config(_ns(tmp_path), serving=True)
    root = tmp_path.resolve()
    assert cfg.run_dir == root / ".git" / "apache-magpie" / "run" / "main"
    assert cfg.pid_file == root / ".git" / "apache-magpie" / "run" / "main" / "container-gateway.pid"
    # The guards walk `.git`, then create `apache-magpie`, `run` and `main` 0700.
    daemon.check_run_dir(cfg.run_dir, cfg.project_root)
    assert (cfg.run_dir.stat().st_mode & 0o777) == 0o700
    assert daemon.validate_run_dir(cfg.run_dir, cfg.project_root)
    assert not (tmp_path / ".apache-magpie-local").exists()


def test_config_adopted_serves_from_the_in_tree_local_dir(tmp_path: Path) -> None:
    from container_gateway import __main__ as cli
    from container_gateway import daemon

    (tmp_path / ".git").mkdir()
    (tmp_path / ".apache-magpie.lock").write_text("method: local\n")
    cfg = cli._config(_ns(tmp_path), serving=True)
    assert cfg.run_dir == tmp_path.resolve() / ".apache-magpie-local" / "run"
    daemon.check_run_dir(cfg.run_dir, cfg.project_root)
    assert not (tmp_path / ".git" / "apache-magpie").exists()


def test_config_in_a_linked_worktree_serves_from_the_common_dir(tmp_path: Path) -> None:
    from container_gateway import __main__ as cli
    from container_gateway import daemon

    main, wt = _worktree(tmp_path)
    cfg = cli._config(_ns(wt), serving=True)
    assert cfg.run_dir == main.resolve() / ".git" / "apache-magpie" / "run" / "wt"
    # `apache-magpie` does not exist yet: the common dir is the anchor and
    # every component below it is created 0700, rather than refused.
    daemon.check_run_dir(cfg.run_dir, cfg.project_root)
    assert cfg.run_dir.is_dir()
    for level in (cfg.run_dir, cfg.run_dir.parent, cfg.run_dir.parent.parent):
        assert (level.stat().st_mode & 0o777) == 0o700
    assert daemon.validate_run_dir(cfg.run_dir, cfg.project_root)
    assert sorted(p.name for p in wt.iterdir()) == [".git"]


def test_two_worktrees_get_separate_run_dirs(tmp_path: Path) -> None:
    from container_gateway import __main__ as cli

    main, wt = _worktree(tmp_path)
    wt2 = tmp_path / "wt2"
    _link_worktree(main, wt2, "wt2")
    dirs = {cli._config(_ns(p), serving=True).run_dir for p in (main, wt, wt2)}
    assert len(dirs) == 3


def test_a_symlinked_worktree_run_dir_is_refused(tmp_path: Path) -> None:
    import pytest

    from container_gateway import __main__ as cli
    from container_gateway import daemon

    main, wt = _worktree(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (main / ".git" / "apache-magpie" / "run").mkdir(parents=True, mode=0o700)
    (main / ".git" / "apache-magpie").chmod(0o700)
    (main / ".git" / "apache-magpie" / "run" / "wt").symlink_to(elsewhere)
    cfg = cli._config(_ns(wt), serving=True)
    with pytest.raises(SystemExit):
        daemon.check_run_dir(cfg.run_dir, cfg.project_root)
    assert list(elsewhere.iterdir()) == []


def test_an_unsafe_worktree_name_refuses_to_serve(tmp_path: Path) -> None:
    import pytest

    from container_gateway import __main__ as cli

    bad = tmp_path / "main" / ".git" / "worktrees" / "we ird$"
    bad.mkdir(parents=True)
    (bad / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {bad}\n")
    with pytest.raises(SystemExit):
        cli._config(_ns(wt), serving=True)


def test_serve_refuses_a_socket_path_over_the_sun_path_limit_before_creating_anything(
    tmp_path: Path, capsys
) -> None:
    import argparse

    import pytest

    from container_gateway import __main__ as cli

    main = tmp_path / ("m" * 40)
    long_name = "w" * 60
    wt_gitdir = main / ".git" / "worktrees" / long_name
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    ns = argparse.Namespace(project=wt, run_dir=None, pid_file=None, daemon=False)
    with pytest.raises(SystemExit):
        cli.cmd_serve(ns)
    assert "socket path too long" in capsys.readouterr().err
    assert not (main / ".git" / "apache-magpie").exists()


def test_a_realistic_worktree_socket_path_fits() -> None:
    from container_gateway import daemon

    run_dir = Path("/Users/someuser/code/project/.git/apache-magpie/run/curried-discovering-catmull")
    for key in ("podman", "docker"):
        assert len(str(daemon.paths(run_dir)[key]).encode()) <= daemon.MAX_SUN_PATH


def test_a_symlinked_personal_layer_in_the_common_dir_is_refused(tmp_path: Path) -> None:
    import pytest

    from container_gateway import __main__ as cli
    from container_gateway import daemon

    main, wt = _worktree(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (main / ".git" / "apache-magpie").symlink_to(elsewhere)
    cfg = cli._config(_ns(wt), serving=True)
    with pytest.raises(SystemExit):
        daemon.check_run_dir(cfg.run_dir, cfg.project_root)
    assert list(elsewhere.iterdir()) == []


def test_serving_outside_a_repo_unadopted_refuses(tmp_path: Path) -> None:
    import pytest

    from container_gateway import __main__ as cli

    with pytest.raises(SystemExit):
        cli._config(_ns(tmp_path), serving=True)
    # Read-only commands still answer, and create nothing.
    cfg = cli._config(_ns(tmp_path))
    assert cfg.run_dir == tmp_path.resolve() / ".apache-magpie-local" / "run"
    assert list(tmp_path.iterdir()) == []


def _context(project: Path):
    from container_gateway import __main__ as cli
    from container_gateway import daemon
    from container_gateway.backends import Backend

    cfg = cli._config(_ns(project), serving=True)
    return daemon.build_context(cfg, Backend("podman", Path("/x.sock"), "host.containers.internal"), None)


def test_the_git_dir_home_and_run_dir_are_never_bind_sources(tmp_path: Path) -> None:
    from container_gateway.policy import resolve_bind_source

    (tmp_path / ".git").mkdir()
    ctx = _context(tmp_path)
    root = tmp_path.resolve()
    assert resolve_bind_source(str(root), ctx)
    assert resolve_bind_source(str(root / "src"), ctx)
    assert not resolve_bind_source(str(root / ".git" / "apache-magpie"), ctx)
    assert not resolve_bind_source(str(root / ".git" / "apache-magpie" / "run"), ctx)
    assert not resolve_bind_source(str(root / ".git" / "apache-magpie" / "run" / "podman.sock"), ctx)


def test_the_in_tree_local_dir_is_never_a_bind_source_when_adopted(tmp_path: Path) -> None:
    from container_gateway.policy import resolve_bind_source

    (tmp_path / ".git").mkdir()
    (tmp_path / ".apache-magpie.lock").write_text("method: local\n")
    ctx = _context(tmp_path)
    root = tmp_path.resolve()
    assert resolve_bind_source(str(root), ctx)
    assert not resolve_bind_source(str(root / ".apache-magpie-local"), ctx)
    assert not resolve_bind_source(str(root / ".apache-magpie-local" / "run" / "docker.sock"), ctx)


def test_a_worktrees_common_dir_home_is_not_bindable(tmp_path: Path) -> None:
    """Outside the worktree root, and excluded besides."""
    from container_gateway.policy import _mounts_deny, resolve_bind_source

    main, wt = _worktree(tmp_path)
    ctx = _context(wt)
    home = main.resolve() / ".git" / "apache-magpie"
    assert resolve_bind_source(str(wt.resolve()), ctx)
    assert not resolve_bind_source(str(home), ctx)
    deny = _mounts_deny({}, {"Binds": [f"{home}/run:/run"]}, ctx, libpod=False)
    assert deny is not None and "run directory or the personal config layer" in deny.reason


# --- the common-dir anchor must really be this repository's ----------------------


def _forged(tmp_path: Path, *, head: bool, backlink: bool, under_worktrees: bool) -> Path:
    """A worktree whose `.git` file names a directory the agent planted."""
    fake = tmp_path / "planted"
    gitdir = fake / ("worktrees" if under_worktrees else "elsewhere") / "wt"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n")
    if head:
        _git_dir(fake)
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {gitdir}\n")
    if backlink:
        (gitdir / "gitdir").write_text(f"{wt / '.git'}\n")
    return wt


def _serve_refuses(wt: Path) -> None:
    import pytest

    from container_gateway import __main__ as cli
    from container_gateway import daemon

    cfg = cli._config(_ns(wt), serving=True)
    with pytest.raises(SystemExit):
        daemon.check_run_dir(cfg.run_dir, cfg.project_root)
    assert not cfg.run_dir.exists()


def test_a_planted_common_dir_without_head_is_refused(tmp_path: Path) -> None:
    _serve_refuses(_forged(tmp_path, head=False, backlink=True, under_worktrees=True))


def test_a_planted_common_dir_without_a_backlink_is_refused(tmp_path: Path) -> None:
    _serve_refuses(_forged(tmp_path, head=True, backlink=False, under_worktrees=True))


def test_a_worktree_gitdir_outside_worktrees_is_refused(tmp_path: Path) -> None:
    _serve_refuses(_forged(tmp_path, head=True, backlink=True, under_worktrees=False))


def test_a_backlink_to_another_worktree_is_refused(tmp_path: Path) -> None:
    main, wt = _worktree(tmp_path)
    (main / ".git" / "worktrees" / "wt" / "gitdir").write_text(f"{tmp_path / 'other' / '.git'}\n")
    _serve_refuses(wt)


def test_a_group_writable_common_dir_is_refused(tmp_path: Path) -> None:
    main, wt = _worktree(tmp_path)
    (main / ".git").chmod(0o775)
    _serve_refuses(wt)


def test_an_excluded_root_reached_through_a_symlink_still_excludes(tmp_path: Path) -> None:
    from container_gateway.policy import PolicyContext, resolve_bind_source

    real = tmp_path / "real"
    run = real / ".git" / "apache-magpie" / "run" / "main"
    run.mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(real)
    ctx = PolicyContext(
        slug="x",
        project_root=link,
        bind_roots=(link,),
        proxy_env=None,
        excluded_bind_roots=(link / ".git" / "apache-magpie",),
    )
    assert resolve_bind_source(str(real / "src"), ctx)
    assert not resolve_bind_source(str(run), ctx)
    assert not resolve_bind_source(str(link / ".git" / "apache-magpie" / "run"), ctx)
