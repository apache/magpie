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

"""Tests for ``ci-pytest-batches.py``: which members the `tests` workflow runs, in which jobs."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "ci-pytest-batches.py"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ci_pytest_batches", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cpb = _load()


def _workspace(tmp_path: Path, members: dict[str, str]) -> Path:
    """`members` maps a member path to its pyproject `[tool]` text."""
    listed = ", ".join(f'"{p}"' for p in members)
    (tmp_path / "pyproject.toml").write_text(f"[tool.uv.workspace]\nmembers = [{listed}]\n")
    for path, tool in members.items():
        (tmp_path / path / "tests").mkdir(parents=True)
        (tmp_path / path / "pyproject.toml").write_text(
            f'[project]\nname = "pkg-{path.rsplit("/", 1)[-1]}"\n' + tool
        )
    return tmp_path


PYTEST = "[tool.pytest.ini_options]\ntestpaths = ['tests']\n"


def test_only_members_with_pytest_and_no_opt_out_are_picked(tmp_path):
    root = _workspace(
        tmp_path,
        {
            "tools/a": PYTEST,
            "tools/b": "[tool.ruff]\n",
            "tools/c": PYTEST + "[tool.magpie.checks]\nskip = ['pytest']\n",
        },
    )
    assert cpb.select(root, None) == ["tools/a"]


@pytest.mark.parametrize(
    ("changed", "picked"),
    [
        (["tools/a/src/x.py"], ["tools/a"]),
        (["tools/a/tests/fixtures/data.json"], ["tools/a"]),
        (["tools/a/README.md"], []),
        (["tools/a/scripts/run.sh"], ["tools/a"]),
        (["tools/a/pyproject.toml"], ["tools/a"]),
        (["tools/a/.claude-plugin/plugin.json"], []),
        (["uv.lock"], ["tools/a", "tools/b"]),
        (["tools/dev/ci-pytest-batches.py"], ["tools/a", "tools/b"]),
        ([], []),
    ],
)
def test_a_pull_request_picks_only_what_it_changed(tmp_path, changed, picked):
    root = _workspace(tmp_path, {"tools/a": PYTEST, "tools/b": PYTEST})
    assert cpb.select(root, changed) == picked


def test_a_change_behind_a_member_symlink_picks_the_member(tmp_path):
    root = _workspace(tmp_path, {"tools/a": PYTEST, "tools/b": PYTEST})
    (root / "plugins" / "shared").mkdir(parents=True)
    (root / "tools" / "a" / "src").mkdir()
    try:
        (root / "tools" / "a" / "src" / "shared").symlink_to(
            root / "plugins" / "shared", target_is_directory=True
        )
    except OSError as exc:
        pytest.skip(f"symlinks not supported on this platform: {exc}")
    assert cpb.select(root, ["plugins/shared/x.py"]) == ["tools/a"]


@pytest.mark.parametrize(
    ("changed", "picked"),
    [
        (["tools/c/src/z.py"], ["tools/a", "tools/b", "tools/c"]),
        (["tools/b/src/y.py"], ["tools/a", "tools/b"]),
        (["tools/a/src/x.py"], ["tools/a"]),
    ],
)
def test_a_change_picks_the_members_depending_on_it(tmp_path, changed, picked):
    root = _workspace(
        tmp_path,
        {
            "tools/a": '[project.optional-dependencies]\nall = ["pkg-b>=1"]\n' + PYTEST,
            "tools/b": 'dependencies = ["Pkg_C"]\n' + PYTEST,
            "tools/c": PYTEST,
        },
    )
    assert cpb.select(root, changed) == picked


def test_a_dependency_group_makes_a_dependent(tmp_path):
    root = _workspace(
        tmp_path,
        {"tools/a": '[dependency-groups]\ndev = ["pkg-b"]\n' + PYTEST, "tools/b": PYTEST},
    )
    assert cpb.select(root, ["tools/b/src/y.py"]) == ["tools/a", "tools/b"]


def test_the_shared_toolchain_does_not_make_a_dependent(tmp_path):
    root = _workspace(
        tmp_path,
        {
            "tools/a": '[dependency-groups]\ndev = ["magpie-dev"]\n' + PYTEST,
            "tools/dev": PYTEST,
        },
    )
    (root / "tools" / "dev" / "pyproject.toml").write_text('[project]\nname = "magpie-dev"\n' + PYTEST)
    assert cpb.select(root, ["tools/dev/src/z.py"]) == ["tools/dev"]


def test_the_cli_reads_stdin_with_dash(tmp_path, monkeypatch, capsys):
    root = _workspace(tmp_path, {"tools/a": PYTEST, "tools/b": PYTEST})
    monkeypatch.setattr("sys.stdin", io.StringIO("tools\\a\\src\\x.py\ntools/b/tests/test_y.py\n"))
    assert cpb.main(["--root", str(root), "--changed-file", "-", "--paths"]) == 0
    assert capsys.readouterr().out == "tools/a\ntools/b\n"


def test_the_cli_prints_the_picked_paths(tmp_path, capsys):
    root = _workspace(tmp_path, {"tools/a": PYTEST, "tools/b": PYTEST})
    changed = tmp_path / "changed.txt"
    changed.write_text("tools/a/src/x.py\ntools/b/tests/test_y.py\n")
    assert cpb.main(["--root", str(root), "--changed-file", str(changed), "--paths"]) == 0
    assert capsys.readouterr().out == "tools/a\ntools/b\n"


def test_up_to_solo_max_members_get_one_job_each_named_after_the_member():
    paths = [f"tools/m{i}" for i in range(cpb.SOLO_MAX)]
    out = cpb.batches(paths, dict.fromkeys(paths, 1))
    assert [b["name"] for b in out] == [f"m{i}" for i in range(cpb.SOLO_MAX)]
    assert [b["paths"] for b in out] == paths


def test_more_members_are_capped_at_max_batches_and_balanced():
    paths = [f"tools/m{i:02}" for i in range(49)]
    weights = {p: (i % 7 + 1) * 100 for i, p in enumerate(paths)}
    out = cpb.batches(paths, weights)
    assert len(out) == cpb.MAX_BATCHES
    grouped = [b["paths"].split() for b in out]
    assert sorted(p for g in grouped for p in g) == paths
    loads = [sum(weights[p] for p in g) for g in grouped]
    assert max(loads) - min(loads) <= max(weights.values())
    assert [b["key"] for b in out] == [f"batch-{i}" for i in range(1, cpb.MAX_BATCHES + 1)]


def test_a_batch_name_lists_three_members_then_a_count():
    paths = [f"tools/m{i:02}" for i in range(cpb.MAX_BATCHES * 5)]
    first = cpb.batches(paths, dict.fromkeys(paths, 1))[0]
    assert first["name"].startswith(f"1/{cpb.MAX_BATCHES}: ")
    assert first["name"].endswith(", +2")


def test_the_split_is_deterministic():
    paths = [f"tools/m{i:02}" for i in range(20)]
    weights = dict.fromkeys(paths, 5)
    assert cpb.batches(paths, weights) == cpb.batches(list(reversed(paths)), weights)


def test_the_cli_prints_the_matrix(tmp_path, capsys):
    root = _workspace(tmp_path, {"tools/a": PYTEST, "tools/b": PYTEST})
    changed = tmp_path / "changed.txt"
    changed.write_text("tools/b/src/y.py\n")
    assert cpb.main(["--root", str(root), "--changed-file", str(changed)]) == 0
    assert json.loads(capsys.readouterr().out) == [
        {"key": "b", "name": "b", "paths": "tools/b", "packages": "pkg-b"}
    ]


def test_packages_follow_the_paths_of_each_batch(tmp_path, capsys):
    members = {f"tools/m{i:02}": PYTEST for i in range(cpb.SOLO_MAX + 3)}
    root = _workspace(tmp_path, members)
    assert cpb.main(["--root", str(root)]) == 0
    for batch in json.loads(capsys.readouterr().out):
        names = [p.rsplit("/", 1)[-1] for p in batch["paths"].split()]
        assert batch["packages"].split() == [f"pkg-{n}" for n in names]


@pytest.mark.skipif(not (REPO_ROOT / "pyproject.toml").is_file(), reason="needs the framework tree")
def test_the_real_workspace_splits_into_the_capped_batches():
    paths = cpb.select(REPO_ROOT, None)
    assert len(paths) > cpb.SOLO_MAX
    out = cpb.batches(paths, {p: cpb.weight(REPO_ROOT, p) for p in paths})
    assert len(out) == cpb.MAX_BATCHES
    assert sorted(p for b in out for p in b["paths"].split()) == sorted(paths)
