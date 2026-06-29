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

"""Backend-dispatching implementation of the source-control (VCS) capability.

This module extracts the abstraction documented in
``tools/github/source-control.md`` into runnable code: one abstract
:class:`VCSBackend` interface listing the operations the dev-loop skills
need, a complete :class:`GitBackend`, and explicit extension points for the
non-Git VCS bridges (Mercurial #601, Subversion #602, Jujutsu #603,
Fossil #604, Perforce #605).

A skill calls the abstract operation (``magpie-vcs diff``) instead of a raw
``git`` command; the active backend is detected from the working copy (or
forced with ``--backend`` / ``MAGPIE_VCS``), so the same skill text works
whatever VCS the project enables under *Tools enabled -> Source control*.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

__all__ = [
    "BACKENDS",
    "GitBackend",
    "MercurialBackend",
    "SubversionBackend",
    "VCSBackend",
    "VCSError",
    "detect_backend",
    "get_backend",
    "main",
]

# Env var a project / skill can set to force a backend instead of detecting it.
BACKEND_ENV = "MAGPIE_VCS"

# Location-redirecting VCS env vars. The tool resolves the working copy from
# its --cwd, so these must not leak in from an outer context (e.g. when a skill
# invokes magpie-vcs from inside a git hook, which exports GIT_DIR / GIT_INDEX_FILE
# and would otherwise point operations at the wrong repository).
_LOCATION_ENV_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
)


def _clean_env() -> dict[str, str]:
    """Process environment with location-redirecting VCS vars removed."""
    return {k: v for k, v in os.environ.items() if k not in _LOCATION_ENV_VARS}


class VCSError(Exception):
    """A source-control operation failed, or is unsupported on this backend."""


class VCSBackend(ABC):
    """Abstract source-control capability.

    Each concrete backend binds these abstract operations to one VCS. The
    operation set mirrors the *What the skills require* table in
    ``tools/github/source-control.md``. Backends that cannot satisfy an
    operation raise :class:`VCSError` rather than silently degrading.
    """

    #: Short backend name (``git``, ``hg``, ``svn`` ...).
    name: str = ""
    #: Whether the backend is distributed (local commits + fetch/push split)
    #: as opposed to centralized (server-side commits, e.g. Subversion).
    distributed: bool = True

    def __init__(self, root: Path) -> None:
        self.root = root

    # -- detection ---------------------------------------------------------

    @classmethod
    @abstractmethod
    def detect(cls, start: Path) -> Path | None:
        """Return the working-copy root governed by this backend, or ``None``.

        ``start`` is any path inside (or equal to) a candidate working copy.
        """

    @classmethod
    def is_available(cls) -> bool:
        """Whether the backend's CLI binary is installed and runnable."""
        return False

    # -- read operations ---------------------------------------------------

    @abstractmethod
    def status(self) -> str:
        """Porcelain working-tree status (one line per changed path)."""

    def is_clean(self) -> bool:
        """Whether the working tree has no uncommitted changes."""
        return self.status().strip() == ""

    @abstractmethod
    def current_branch(self) -> str:
        """Name of the current branch / bookmark / equivalent."""

    @abstractmethod
    def diff(self, base: str | None = None, cached: bool = False, paths: Sequence[str] = ()) -> str:
        """Unified diff of the working copy (optionally vs ``base`` / staged)."""

    @abstractmethod
    def log(
        self,
        max_count: int | None = None,
        grep: str | None = None,
        author: str | None = None,
        since: str | None = None,
        paths: Sequence[str] = (),
    ) -> str:
        """History read, optionally filtered."""

    # -- write operations (callers gate these on explicit confirmation) ----

    @abstractmethod
    def create_branch(self, name: str) -> None:
        """Create and switch to a new line of work."""

    @abstractmethod
    def switch(self, ref: str) -> None:
        """Switch the working copy to an existing ref."""

    @abstractmethod
    def stage(self, paths: Sequence[str]) -> None:
        """Mark paths for inclusion in the next commit."""

    @abstractmethod
    def commit(self, message: str) -> None:
        """Record the staged change."""

    @abstractmethod
    def fetch(self, remote: str | None = None, ref: str | None = None) -> None:
        """Sync refs from the forge without changing the working copy."""

    @abstractmethod
    def push(self, remote: str, ref: str, set_upstream: bool = False) -> None:
        """Publish a ref to the forge."""

    @abstractmethod
    def reset_worktree(self) -> None:
        """Discard all uncommitted changes (the per-run reset protocol)."""


def _run(
    args: Sequence[str],
    cwd: Path,
    *,
    capture: bool = True,
    check: bool = True,
) -> str:
    """Run a subprocess, returning stdout. Raise :class:`VCSError` on failure."""
    try:
        proc = subprocess.run(
            list(args),
            cwd=cwd,
            text=True,
            capture_output=capture,
            check=False,
            env=_clean_env(),
        )
    except FileNotFoundError as exc:  # binary not installed
        raise VCSError(f"{args[0]}: command not found") from exc
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() if capture else ""
        raise VCSError(f"`{' '.join(args)}` failed (rc={proc.returncode}): {detail}")
    return proc.stdout if capture else ""


class GitBackend(VCSBackend):
    """Git binding of the source-control capability (GitHub's native VCS)."""

    name = "git"
    distributed = True

    @classmethod
    def detect(cls, start: Path) -> Path | None:
        for d in (start, *start.parents):
            if (d / ".git").exists():
                return d
        return None

    @classmethod
    def is_available(cls) -> bool:
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            return False
        return True

    def status(self) -> str:
        return _run(["git", "status", "--porcelain"], self.root)

    def current_branch(self) -> str:
        return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.root).strip()

    def diff(self, base: str | None = None, cached: bool = False, paths: Sequence[str] = ()) -> str:
        args = ["git", "diff"]
        if cached:
            args.append("--cached")
        if base:
            args.append(base)
        if paths:
            args = [*args, "--", *paths]
        return _run(args, self.root)

    def log(
        self,
        max_count: int | None = None,
        grep: str | None = None,
        author: str | None = None,
        since: str | None = None,
        paths: Sequence[str] = (),
    ) -> str:
        args = ["git", "log", "--oneline"]
        if max_count is not None:
            args.append(f"-n{max_count}")
        if grep:
            args.append(f"--grep={grep}")
        if author:
            args.append(f"--author={author}")
        if since:
            args.append(f"--since={since}")
        if paths:
            args = [*args, "--", *paths]
        return _run(args, self.root)

    def create_branch(self, name: str) -> None:
        _run(["git", "checkout", "-b", name], self.root, capture=False)

    def switch(self, ref: str) -> None:
        _run(["git", "checkout", ref], self.root, capture=False)

    def stage(self, paths: Sequence[str]) -> None:
        if not paths:
            raise VCSError("stage: refusing to stage nothing (pass explicit paths)")
        _run(["git", "add", "--", *paths], self.root, capture=False)

    def commit(self, message: str) -> None:
        _run(["git", "commit", "-m", message], self.root, capture=False)

    def fetch(self, remote: str | None = None, ref: str | None = None) -> None:
        args = ["git", "fetch"]
        if remote:
            args.append(remote)
        if ref:
            args.append(ref)
        _run(args, self.root, capture=False)

    def push(self, remote: str, ref: str, set_upstream: bool = False) -> None:
        args = ["git", "push"]
        if set_upstream:
            args.append("-u")
        args.extend([remote, ref])
        _run(args, self.root, capture=False)

    def reset_worktree(self) -> None:
        # The Git binding of the reset protocol in
        # tools/github/source-control.md / issue-reproducer runtime-recipes.
        _run(["git", "stash", "--include-untracked"], self.root, check=False, capture=False)
        _run(["git", "clean", "-fd"], self.root, capture=False)
        _run(["git", "checkout", "--", "."], self.root, capture=False)


class _UnimplementedBackend(VCSBackend):
    """Shared base for detected-but-not-yet-implemented non-Git backends.

    The detection logic is real (so ``magpie-vcs detect`` correctly reports
    the working copy's VCS); every operation raises a clear, actionable
    :class:`VCSError` pointing at the tracking issue for the full bridge.
    """

    marker: str = ""
    issue: str = ""

    @classmethod
    def detect(cls, start: Path) -> Path | None:
        for d in (start, *start.parents):
            if (d / cls.marker).exists():
                return d
        return None

    def _unsupported(self, op: str) -> VCSError:
        return VCSError(
            f"{self.name}: operation '{op}' is not implemented yet — "
            f"the {self.name} backend is a tracked extension point ({self.issue}). "
            f"Implement it by completing this backend in tools/vcs/."
        )

    def status(self) -> str:
        raise self._unsupported("status")

    def current_branch(self) -> str:
        raise self._unsupported("current_branch")

    def diff(self, base: str | None = None, cached: bool = False, paths: Sequence[str] = ()) -> str:
        raise self._unsupported("diff")

    def log(
        self,
        max_count: int | None = None,
        grep: str | None = None,
        author: str | None = None,
        since: str | None = None,
        paths: Sequence[str] = (),
    ) -> str:
        raise self._unsupported("log")

    def create_branch(self, name: str) -> None:
        raise self._unsupported("create_branch")

    def switch(self, ref: str) -> None:
        raise self._unsupported("switch")

    def stage(self, paths: Sequence[str]) -> None:
        raise self._unsupported("stage")

    def commit(self, message: str) -> None:
        raise self._unsupported("commit")

    def fetch(self, remote: str | None = None, ref: str | None = None) -> None:
        raise self._unsupported("fetch")

    def push(self, remote: str, ref: str, set_upstream: bool = False) -> None:
        raise self._unsupported("push")

    def reset_worktree(self) -> None:
        raise self._unsupported("reset_worktree")


class MercurialBackend(_UnimplementedBackend):
    """Mercurial (Hg) extension point — see apache/magpie#601."""

    name = "hg"
    distributed = True
    marker = ".hg"
    issue = "apache/magpie#601"


class SubversionBackend(_UnimplementedBackend):
    """Apache Subversion (SVN) extension point — see apache/magpie#602."""

    name = "svn"
    distributed = False
    marker = ".svn"
    issue = "apache/magpie#602"


# Registry, in detection-priority order. New VCS bridges register here.
BACKENDS: tuple[type[VCSBackend], ...] = (
    GitBackend,
    MercurialBackend,
    SubversionBackend,
)

_BACKENDS_BY_NAME: dict[str, type[VCSBackend]] = {b.name: b for b in BACKENDS}


def detect_backend(start: Path) -> VCSBackend | None:
    """Detect the backend governing the working copy at/above ``start``.

    When working copies of two VCS nest, the innermost (longest root path)
    wins, matching how the VCS tools themselves resolve the active repo.
    """
    best: VCSBackend | None = None
    best_len = -1
    for backend_cls in BACKENDS:
        root = backend_cls.detect(start)
        if root is not None and len(root.parts) > best_len:
            best = backend_cls(root)
            best_len = len(root.parts)
    return best


def get_backend(start: Path, override: str | None = None) -> VCSBackend:
    """Resolve the backend: explicit ``override`` / ``MAGPIE_VCS`` else detect."""
    forced = override or os.environ.get(BACKEND_ENV)
    if forced:
        backend_cls = _BACKENDS_BY_NAME.get(forced)
        if backend_cls is None:
            known = ", ".join(sorted(_BACKENDS_BY_NAME))
            raise VCSError(f"unknown backend '{forced}' (known: {known})")
        root = backend_cls.detect(start) or start
        return backend_cls(root)
    backend = detect_backend(start)
    if backend is None:
        raise VCSError(f"no supported VCS working copy found at or above {start}")
    return backend


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="magpie-vcs",
        description="Source-control capability — backend-dispatching VCS operations.",
    )
    parser.add_argument("-C", "--cwd", default=".", help="working-copy path (default: .)")
    parser.add_argument("--backend", help=f"force a backend (else detect / ${BACKEND_ENV})")
    sub = parser.add_subparsers(dest="op", required=True)

    sub.add_parser("detect", help="print the detected backend name")
    sub.add_parser("backends", help="list registered backends + availability")
    sub.add_parser("root", help="print the working-copy root")
    sub.add_parser("status", help="porcelain working-tree status")
    sub.add_parser("clean", help="exit 0 if clean, 1 if dirty")
    sub.add_parser("branch", help="print the current branch")

    p = sub.add_parser("diff", help="show changes")
    p.add_argument("--base", help="diff against this ref")
    p.add_argument("--cached", action="store_true", help="diff the staged change")
    p.add_argument("paths", nargs="*")

    p = sub.add_parser("log", help="history read")
    p.add_argument("-n", "--max-count", type=int)
    p.add_argument("--grep")
    p.add_argument("--author")
    p.add_argument("--since")
    p.add_argument("paths", nargs="*")

    p = sub.add_parser("new-branch", help="create + switch to a branch")
    p.add_argument("name")

    p = sub.add_parser("switch", help="switch to an existing ref")
    p.add_argument("ref")

    p = sub.add_parser("stage", help="stage paths for commit")
    p.add_argument("paths", nargs="+")

    p = sub.add_parser("commit", help="record the staged change")
    p.add_argument("-m", "--message", required=True)

    p = sub.add_parser("fetch", help="sync refs from the forge")
    p.add_argument("remote", nargs="?")
    p.add_argument("ref", nargs="?")

    p = sub.add_parser("push", help="publish a ref to the forge")
    p.add_argument("-u", "--set-upstream", action="store_true")
    p.add_argument("remote")
    p.add_argument("ref")

    sub.add_parser("reset-worktree", help="discard all uncommitted changes")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = _build_parser()
    ns = parser.parse_args(argv)
    start = Path(ns.cwd).resolve()

    try:
        if ns.op == "backends":
            for backend_cls in BACKENDS:
                avail = "available" if backend_cls.is_available() else "not installed"
                print(f"{backend_cls.name}\t{avail}")
            return 0

        backend = get_backend(start, ns.backend)

        if ns.op == "detect":
            print(backend.name)
        elif ns.op == "root":
            print(str(backend.root))
        elif ns.op == "status":
            sys.stdout.write(backend.status())
        elif ns.op == "clean":
            return 0 if backend.is_clean() else 1
        elif ns.op == "branch":
            print(backend.current_branch())
        elif ns.op == "diff":
            sys.stdout.write(backend.diff(base=ns.base, cached=ns.cached, paths=ns.paths))
        elif ns.op == "log":
            sys.stdout.write(
                backend.log(
                    max_count=ns.max_count,
                    grep=ns.grep,
                    author=ns.author,
                    since=ns.since,
                    paths=ns.paths,
                )
            )
        elif ns.op == "new-branch":
            backend.create_branch(ns.name)
        elif ns.op == "switch":
            backend.switch(ns.ref)
        elif ns.op == "stage":
            backend.stage(ns.paths)
        elif ns.op == "commit":
            backend.commit(ns.message)
        elif ns.op == "fetch":
            backend.fetch(ns.remote, ns.ref)
        elif ns.op == "push":
            backend.push(ns.remote, ns.ref, set_upstream=ns.set_upstream)
        elif ns.op == "reset-worktree":
            backend.reset_worktree()
        else:  # pragma: no cover - argparse enforces the choices
            parser.error(f"unknown operation {ns.op!r}")
    except VCSError as exc:
        print(f"magpie-vcs: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
