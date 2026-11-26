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

"""`vetted-op-checks`: run a change's checks in the sandbox and record what passed.

`git-commit` runs outside the sandbox, so it runs no hook: a hook is code from
the working tree, which the agent can edit, and out there it would run with
the user's keys in reach. Skipping the checks is not the answer either. So the
checks run here, inside the sandbox (this command is never excluded from it),
and on success record each listed path's content. `git-commit` then refuses
any staged path whose content that record does not match.

The record lives in the vetted-ops workspace, which sandboxed commands can
write: it keeps an agent honest the way CI does, it is not a proof against
one set on forging it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROG = "vetted-op-checks"
#: Where the records live, next to the path lists they were made from.
STAMP_DIR = "checks"
#: The hook configurations this command knows how to run, and the command for each.
CHECKERS = ((".pre-commit-config.yaml", ("prek", "run", "--files")),)
DELETED = "deleted"


def stamp_path(workspace: Path, worktree: Path) -> Path:
    """Where the record for `worktree` lives in `workspace`."""
    key = hashlib.sha256(os.path.realpath(worktree).encode()).hexdigest()[:16]
    return workspace / STAMP_DIR / f"{key}.json"


def content_id(worktree: Path, path: str) -> str:
    """The blob id `git-stage` would record for `path` (no filters: it stages with none), or `deleted`."""
    full = worktree / path
    if not os.path.lexists(full):
        return DELETED
    done = subprocess.run(
        ["git", "-C", str(worktree), "hash-object", "--no-filters", "--", path],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def read_paths(paths_file: Path) -> list[str]:
    paths = [line.strip() for line in paths_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not paths:
        raise ValueError("the path list is empty")
    return paths


def run_checks(worktree: Path, paths: list[str]) -> str:
    """Run the worktree's hook configuration on `paths`; the checker's name, or `none`."""
    present = [p for p in paths if os.path.lexists(worktree / p)]
    for config, command in CHECKERS:
        if (worktree / config).is_file():
            if present:
                done = subprocess.run([*command, *present], cwd=worktree, check=False)
                if done.returncode != 0:
                    raise RuntimeError(f"{command[0]} failed (exit {done.returncode}); fix and run again")
            return command[0]
    return "none"


def record(worktree: Path, paths_file: Path) -> Path:
    """Run the checks on the listed paths and write the record; returns its path."""
    worktree = Path(os.path.realpath(worktree))
    paths_file = Path(os.path.realpath(paths_file))
    paths = read_paths(paths_file)
    checker = run_checks(worktree, paths)
    stamp = {
        "worktree": str(worktree),
        "checks": checker,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": {path: content_id(worktree, path) for path in paths},
    }
    target = stamp_path(paths_file.parent, worktree)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


def main(argv: list[str] | None = None) -> int:
    """The ``vetted-op-checks`` console script; runs inside the sandbox."""
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Run a change's checks inside the sandbox and record what passed, for git-commit.",
        allow_abbrev=False,
    )
    parser.add_argument("worktree", type=Path, help="the worktree the change is in")
    parser.add_argument(
        "paths_file",
        type=Path,
        help="the git-stage path list in the vetted-ops workspace; the record is written beside it",
    )
    args = parser.parse_args(argv)
    try:
        target = record(args.worktree, args.paths_file)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return 1
    print(f"{PROG}: checks passed; recorded in {target}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
