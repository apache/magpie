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

"""Where a project's Magpie configuration lives.

Two layers, personal first:

* **Personal** — gitignored, one user's.  In an *adopted* repository (one
  with a committed `.apache-magpie.lock`) it is `<repo>/.apache-magpie-local/`.
  In a repository that has **not** adopted Magpie it is
  `<git-common-dir>/apache-magpie/`: inside the repository's git directory,
  never in the working tree, so it is never committed, needs no ignore
  entry, and is shared by every worktree of the clone.  Outside a git
  repository an unadopted project has no personal layer at all — nothing is
  ever placed in a working tree that did not ask for Magpie.
  A linked worktree of an adopted repository (`git worktree add`) has no
  `.apache-magpie-local/` of its own, since the directory is gitignored, so
  its main checkout's is read after its own, file by file, and written to
  when the worktree has none (`main_worktree`).
* **Committed** — `<repo>/.apache-magpie-overrides/`, written only by
  `adopt`.  It is read wherever it exists.

An unadopted repository that still carries the old in-tree
`.apache-magpie-local/` keeps working: that directory is read after the
personal layer as a legacy fallback, and the pre-flight reports it so the
user can move it.

Nothing here creates a directory.  A read that created the personal layer
would fake the "configured" state the pre-flight reads from its presence.

Run as a module it prints where each layer is, for a skill that has to
write the personal layer rather than read it:

    python3 -m setup_preflight.layers [--project-root .]

The git common directory is computed by reading files, never by spawning
`git`: the pre-flight runs on every skill invocation, often sandboxed.
The tools under `tools/` that resolve configuration carry an identical copy
of `git_common_dir` and the same test vectors; keep them in step.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

LOCK_NAME = ".apache-magpie.lock"
LOCAL_DIR = ".apache-magpie-local"
OVERRIDES_DIR = ".apache-magpie-overrides"
#: The personal layer's name inside the git common directory.
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


def main_worktree(root: Path) -> Path | None:
    """The main checkout of the linked worktree `root`, or `None`.

    `<root>/.git` a file whose common git directory is named `.git` and is
    the `.git` directory of its parent (a non-bare main checkout) → that
    parent.  `None` for the main checkout itself, a bare repository, a
    submodule, or no repository.  Reads files only, never spawns `git`.

    The main checkout is located from the worktree's `.git` file, which an
    agent able to write the worktree can rewrite.  That only selects
    configuration the agent could already write into the worktree's own
    `.apache-magpie-local/`, so following it grants no new capability.
    """
    if not (_absolute(root) / ".git").is_file():
        return None
    common = git_common_dir(root)
    if common is None or common.name != ".git":
        return None
    main = common.parent
    return main if (main / ".git").is_dir() else None


def personal_dir(root: Path) -> Path | None:
    """Where this user's configuration for `root` is written; never created here.

    Adopted → `<root>/.apache-magpie-local`, except in a linked worktree
    that has none while its main checkout has one: then the main
    checkout's, so a worktree writes where it already reads.  Not adopted →
    `<git-common-dir>/apache-magpie`.  May not exist yet.  `None` means
    there is nowhere to keep it: not adopted and not a git repository.
    """
    if adopted(root):
        own = root / LOCAL_DIR
        main = main_worktree(root)
        if own.is_dir() or main is None or not (main / LOCAL_DIR).is_dir():
            return own
        return main / LOCAL_DIR
    common = git_common_dir(root)
    return common / GIT_HOME_NAME if common is not None else None


def personal_layers(root: Path) -> list[Path]:
    """Every personal directory a config file is looked up in, first match wins.

    Adopted → `<root>/.apache-magpie-local`, then, in a linked worktree,
    the main checkout's when it exists: `.apache-magpie-local/` is
    gitignored, so a new worktree has none, and a file missing from its own
    is found in the main checkout's.  Not adopted →
    `<git-common-dir>/apache-magpie` (already shared by every worktree),
    then a legacy in-tree `.apache-magpie-local/`.
    """
    if adopted(root):
        found = [root / LOCAL_DIR]
        main = main_worktree(root)
        if main is not None and (main / LOCAL_DIR).is_dir():
            found.append(main / LOCAL_DIR)
        return found
    common = git_common_dir(root)
    found = [] if common is None else [common / GIT_HOME_NAME]
    legacy = root / LOCAL_DIR
    if legacy.is_dir() and legacy not in found:
        found.append(legacy)
    return found


def legacy_local_dir(root: Path) -> Path | None:
    """The old in-tree personal layer of an unadopted repository, if present."""
    if adopted(root):
        return None
    legacy = root / LOCAL_DIR
    return legacy if legacy.is_dir() else None


def config_layers(root: Path) -> list[Path]:
    """Every directory a config file is looked up in, first match wins."""
    return [*personal_layers(root), root / OVERRIDES_DIR]


def resolve(root: Path, name: str) -> Path | None:
    """The first existing `<layer>/<name>`, or `None`."""
    for layer in config_layers(root):
        candidate = layer / name
        if candidate.exists():
            return candidate
    return None


def describe(root: Path) -> dict[str, object]:
    home = personal_dir(root)
    legacy = legacy_local_dir(root)
    main = main_worktree(root)
    return {
        "adopted": adopted(root),
        "main_worktree": str(main) if main is not None else None,
        "personal_dir": str(home) if home is not None else None,
        "personal_dir_exists": bool(home is not None and home.is_dir()),
        "personal_layers": [str(p) for p in personal_layers(root)],
        "legacy_local_dir": str(legacy) if legacy is not None else None,
        "config_layers": [str(p) for p in config_layers(root)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="setup_preflight.layers", description="Print where Magpie config lives."
    )
    parser.add_argument("--project-root", default=".", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(describe(args.project_root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
