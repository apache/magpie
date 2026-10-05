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

"""Where a project's Magpie configuration lives (personal layer first).

A copy of the rule in `setup_preflight/layers.py`, duplicated so this
package depends on nothing else in the framework.  Keep `git_common_dir`
identical to that copy; `tools/setup-preflight/tests/test_layers.py`
checks every copy against it, and this package's tests carry the same
vectors.

* Adopted repository (a committed `.apache-magpie.lock`): the personal
  layer is `<repo>/.apache-magpie-local/`.
* Not adopted: it is `<git-common-dir>/apache-magpie/` — inside the git
  directory, never the working tree, shared by every worktree.  Outside a
  git repository there is none.  A legacy in-tree `.apache-magpie-local/`
  is still read after it.
* The committed layer, `<repo>/.apache-magpie-overrides/`, comes last.

Nothing here creates a directory.
"""

from __future__ import annotations

import os
from pathlib import Path

LOCK_NAME = ".apache-magpie.lock"
LOCAL_DIR = ".apache-magpie-local"
OVERRIDES_DIR = ".apache-magpie-overrides"
GIT_HOME_NAME = "apache-magpie"


def _absolute(path: Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(path)))


def git_common_dir(root: Path) -> Path | None:
    """The repository's common git directory, or `None` when `root` is not a repo.

    `<root>/.git` a directory → that directory.  A file reading
    `gitdir: <path>` (a linked worktree, or a submodule) → that worktree git
    directory, and then the directory its `commondir` file names (relative
    to the worktree git directory), when it has one.  Relative paths resolve
    against the file that holds them.
    """
    dotgit = _absolute(root) / ".git"
    if dotgit.is_dir():
        return dotgit
    if not dotgit.is_file():
        return None
    try:
        first = dotgit.read_text(encoding="utf-8").splitlines()[0].strip()
    except (OSError, UnicodeDecodeError, IndexError):
        return None
    if not first.startswith("gitdir:"):
        return None
    target = first.removeprefix("gitdir:").strip()
    if not target:
        return None
    gitdir = _absolute(dotgit.parent / target)
    if not gitdir.is_dir():
        return None
    commondir = gitdir / "commondir"
    if not commondir.is_file():
        return gitdir
    try:
        common = commondir.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not common:
        return gitdir
    resolved = _absolute(gitdir / common)
    return resolved if resolved.is_dir() else None


def adopted(root: Path) -> bool:
    """Whether the project has adopted Magpie: a committed lock exists."""
    return (root / LOCK_NAME).is_file()


def personal_dir(root: Path) -> Path | None:
    """Where this user's configuration for `root` lives (may not exist yet)."""
    if adopted(root):
        return root / LOCAL_DIR
    common = git_common_dir(root)
    return common / GIT_HOME_NAME if common is not None else None


def personal_layers(root: Path) -> list[Path]:
    """The personal layer, then a legacy in-tree one in an unadopted repository."""
    layers = [] if (home := personal_dir(root)) is None else [home]
    legacy = root / LOCAL_DIR
    if not adopted(root) and legacy.is_dir() and legacy not in layers:
        layers.append(legacy)
    return layers


def config_layers(root: Path) -> list[Path]:
    """Every directory a config file is looked up in, first match wins."""
    return [*personal_layers(root), root / OVERRIDES_DIR]
