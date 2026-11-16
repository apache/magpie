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

import errno
import functools
import os
import re
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from vetted_ops import config
from vetted_ops.config import DEFAULT_RELATIVE_PATH

Discovered = Callable[[Callable[[list[str]], int], list[str], Path], int]


@pytest.fixture()
def approved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty approved-policy directory standing in for ~/.config/apache-magpie/vetted-ops."""
    root = tmp_path / "approved-policies"
    root.mkdir()
    monkeypatch.setattr(config, "approved_dir", lambda: root)
    return root


@pytest.fixture()
def discovered(monkeypatch: pytest.MonkeyPatch, approved: Path) -> Discovered:
    """Run an entry point against ``cfg_path`` found by discovery and approved.

    The write entry points refuse `--config` whenever an operation runs and act
    only on a discovered policy that is also an approved copy, so a test that
    executes one installs the policy at the committed path in its own directory,
    copies it into the approved directory, and runs from there.
    """

    def run(main: Callable[[list[str]], int], argv: list[str], cfg_path: Path) -> int:
        root = cfg_path.parent
        target = root / DEFAULT_RELATIVE_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(cfg_path.read_bytes())
        (approved / "project.toml").write_bytes(cfg_path.read_bytes())
        monkeypatch.chdir(root)
        return main(argv)

    return run


#: The policy locations the secure setup denies to every sandboxed write
#: (`Edit(//**/.apache-magpie-overrides/tools/vetted-ops/**)` and the personal
#: layers beside it), wherever they sit: a policy planted under any directory
#: could otherwise steer the unprompted read dispatcher. Tests that build a
#: policy there cannot run inside that sandbox; CI runs them outside it.
_POLICY_PATH = re.compile(
    r"/(?:\.apache-magpie-overrides|\.apache-magpie-local|\.git(?:/[^/]+)*/apache-magpie|\.svn/apache-magpie)"
    r"/tools/vetted-ops(?:/|$)"
)


@functools.cache
def _policy_paths_writable() -> bool:
    """Whether this process may create a policy directory at all (False inside the secure sandbox)."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.makedirs(Path(tmp) / DEFAULT_RELATIVE_PATH.parent)
        except PermissionError:
            return False
    return True


def _denied_policy_path(exc: BaseException) -> str | None:
    for err in (exc, exc.__cause__, exc.__context__):
        if isinstance(err, OSError) and err.errno in (errno.EPERM, errno.EACCES):
            for name in (err.filename, err.filename2):
                if name and _POLICY_PATH.search(os.fspath(name)):
                    return os.fspath(name)
    return None


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Iterator[None]:
    """Skip, rather than fail, a test the secure sandbox stops from writing a policy."""
    try:
        return (yield)
    except OSError as exc:
        path = _denied_policy_path(exc)
        if path is None or _policy_paths_writable():
            raise
        pytest.skip(f"the sandbox denies writes to vetted-ops policy paths ({path}); CI runs this test")
