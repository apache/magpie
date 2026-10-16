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
need, and complete Git, Mercurial, Fossil, and Subversion backends. Further
VCS bridges (Jujutsu #603, Perforce #605) plug in as new backends.

A skill calls the abstract operation (``magpie-vcs diff``) instead of a raw
``git`` command; the active backend is detected from the working copy (or
forced with ``--backend`` / ``MAGPIE_VCS``), so the same skill text works
whatever VCS the project enables under *Tools enabled -> Source control*.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import re
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from magpie_vcs import publication

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
    "probe",
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
    def update(self) -> None:
        """Bring the working copy up to date with its upstream, never by merging."""

    @classmethod
    def checkout(cls, url: str, dest: Path) -> None:
        """Create a new working copy of ``url`` at ``dest`` (which must not exist)."""
        raise VCSError(f"{cls.name}: checkout is not supported on this backend")

    @abstractmethod
    def push(self, remote: str, ref: str, set_upstream: bool = False) -> None:
        """Publish a ref to the forge."""

    @abstractmethod
    def reset_worktree(self) -> None:
        """Discard all uncommitted changes (the per-run reset protocol)."""

    @abstractmethod
    def cat(self, rev: str, path: str) -> str:
        """Return the contents of *path* at revision *rev*."""

    def changed_paths(self) -> list[tuple[str, str]]:
        """``(item, path)`` per changed path, ``item`` in svn's ``wc-status`` vocabulary.

        Only the centralized backend needs it (its commit takes every change,
        so a proposal must list them); the others raise.
        """
        raise VCSError(f"{self.name}: changed-paths listing is only implemented for svn")


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


def _require_new_dest(dest: Path) -> None:
    """Refuse a checkout onto an existing path, or under a missing parent."""
    if dest.exists():
        raise VCSError(f"checkout: {dest} already exists")
    if not dest.parent.is_dir():
        raise VCSError(f"checkout: parent directory {dest.parent} does not exist")


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

    def update(self) -> None:
        # Fast-forward only: a diverged local branch is an error, never a merge.
        _run(["git", "pull", "--ff-only"], self.root, capture=False)

    @classmethod
    def checkout(cls, url: str, dest: Path) -> None:
        _require_new_dest(dest)
        _run(["git", "clone", "--", url, str(dest)], dest.parent, capture=False)

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

    def cat(self, rev: str, path: str) -> str:
        return _run(["git", "show", f"{rev}:{path}"], self.root)


class MercurialBackend(VCSBackend):
    """Mercurial (Hg) backend implementation."""

    name = "hg"
    distributed = True

    @classmethod
    def detect(cls, start: Path) -> Path | None:
        for d in (start, *start.parents):
            if (d / ".hg").exists():
                return d
        return None

    @classmethod
    def is_available(cls) -> bool:
        try:
            subprocess.run(["hg", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            return False
        return True

    def status(self) -> str:
        return _run(["hg", "status"], self.root)

    def current_branch(self) -> str:
        # Prefer the active bookmark (analogous to Git branches in our usage)
        # and fall back to the named branch if no bookmark is active.
        active = _run(["hg", "log", "-r", ".", "-T", "{activebookmark}"], self.root).strip()
        if active:
            return active
        return _run(["hg", "branch"], self.root).strip()

    def diff(self, base: str | None = None, cached: bool = False, paths: Sequence[str] = ()) -> str:
        if cached:
            raise VCSError("hg does not support staging area/cached diff")
        args = ["hg", "diff"]
        if base:
            args.extend(["-r", base])
        if paths:
            args.extend(["--", *paths])
        return _run(args, self.root)

    def log(
        self,
        max_count: int | None = None,
        grep: str | None = None,
        author: str | None = None,
        since: str | None = None,
        paths: Sequence[str] = (),
    ) -> str:
        args = ["hg", "log", "--template", "{node|short} {desc|firstline}\n"]
        if max_count is not None:
            args.extend(["-l", str(max_count)])
        if grep:
            args.extend(["-k", grep])
        if author:
            args.extend(["-u", author])
        if since:
            args.extend(["-d", f">= {since}"])
        if paths:
            args.extend(["--", *paths])
        return _run(args, self.root)

    def create_branch(self, name: str) -> None:
        # Creates and automatically activates the bookmark on the current revision,
        # switching the working directory to this bookmark for subsequent commits.
        _run(["hg", "bookmark", name], self.root, capture=False)

    def switch(self, ref: str) -> None:
        _run(["hg", "update", ref], self.root, capture=False)

    def stage(self, paths: Sequence[str]) -> None:
        if not paths:
            raise VCSError("stage: refusing to stage nothing")
        _run(["hg", "add", "--", *paths], self.root, capture=False)

    def commit(self, message: str) -> None:
        _run(["hg", "commit", "-m", message], self.root, capture=False)

    def fetch(self, remote: str | None = None, ref: str | None = None) -> None:
        args = ["hg", "pull"]
        if remote:
            args.append(remote)
        _run(args, self.root, capture=False)

    def update(self) -> None:
        # `pull -u` updates only when it can do so without a merge.
        _run(["hg", "pull", "-u"], self.root, capture=False)

    @classmethod
    def checkout(cls, url: str, dest: Path) -> None:
        _require_new_dest(dest)
        _run(["hg", "clone", "--", url, str(dest)], dest.parent, capture=False)

    def push(self, remote: str, ref: str, set_upstream: bool = False) -> None:
        args = ["hg", "push", "-B", ref, remote]
        _run(args, self.root, capture=False)

    def reset_worktree(self) -> None:
        _run(["hg", "update", "--clean"], self.root, check=False, capture=False)
        _run(["hg", "purge", "--config", "extensions.purge="], self.root, check=False, capture=False)

    def cat(self, rev: str, path: str) -> str:
        return _run(["hg", "cat", "-r", rev, path], self.root)


class FossilBackend(VCSBackend):
    """Fossil SCM binding of the source-control capability."""

    name = "fossil"
    distributed = True

    @classmethod
    def detect(cls, start: Path) -> Path | None:
        for d in (start, *start.parents):
            if (d / ".fslckout").exists() or (d / "_FOSSIL_").exists():
                return d
        return None

    @classmethod
    def is_available(cls) -> bool:
        try:
            subprocess.run(["fossil", "version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            return False
        return True

    def status(self) -> str:
        try:
            out = _run(["fossil", "changes"], self.root)
        except VCSError:
            out = ""
        try:
            extras = _run(["fossil", "extras"], self.root)
        except VCSError:
            extras = ""

        lines = []
        for line in out.splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                status_type, path = parts
                status_char = "M"
                if "ADDED" in status_type:
                    status_char = "A"
                elif "DELETED" in status_type:
                    status_char = "D"
                lines.append(f"{status_char} {path}")
        for path in extras.splitlines():
            if path.strip():
                lines.append(f"? {path.strip()}")
        return "\n".join(lines) + ("\n" if lines else "")

    def current_branch(self) -> str:
        return _run(["fossil", "branch", "current"], self.root).strip()

    def diff(self, base: str | None = None, cached: bool = False, paths: Sequence[str] = ()) -> str:
        if cached:
            raise VCSError("fossil does not support staging area/cached diff")
        args = ["fossil", "diff"]
        if base:
            args.extend(["-r", base])
        if paths:
            args.extend(paths)
        return _run(args, self.root)

    def log(
        self,
        max_count: int | None = None,
        grep: str | None = None,
        author: str | None = None,
        since: str | None = None,
        paths: Sequence[str] = (),
    ) -> str:
        args = ["fossil", "timeline", "checkin"]
        if max_count is not None:
            args.extend(["-n", str(max_count)])
        if author:
            args.extend(["-u", author])
        if paths:
            args.extend(["-p", paths[0]])

        out = _run(args, self.root)

        lines = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("===") and line.endswith("==="):
                continue
            if " [" in line and "] " in line:
                parts = line.split(" [", 1)
                if len(parts) == 2:
                    h_parts = parts[1].split("] ", 1)
                    if len(h_parts) == 2:
                        rev_hash = h_parts[0]
                        comment = h_parts[1]
                        if " (user: " in comment:
                            comment = comment.rsplit(" (user: ", 1)[0]
                        if grep and grep.lower() not in comment.lower():
                            continue
                        lines.append(f"{rev_hash} {comment}")
        return "\n".join(lines) + ("\n" if lines else "")

    def create_branch(self, name: str) -> None:
        basis = self.current_branch()
        _run(["fossil", "branch", "new", name, basis], self.root, capture=False)
        _run(["fossil", "update", name], self.root, capture=False)

    def switch(self, ref: str) -> None:
        _run(["fossil", "update", ref], self.root, capture=False)

    def stage(self, paths: Sequence[str]) -> None:
        if not paths:
            raise VCSError("stage: refusing to stage nothing")
        _run(["fossil", "add", "--", *paths], self.root, capture=False)

    def commit(self, message: str) -> None:
        _run(["fossil", "commit", "-m", message, "--no-warnings"], self.root, capture=False)

    def fetch(self, remote: str | None = None, ref: str | None = None) -> None:
        args = ["fossil", "pull"]
        if remote:
            args.append(remote)
        _run(args, self.root, capture=False)

    def update(self) -> None:
        # With autosync (fossil's default) `update` pulls before it updates.
        _run(["fossil", "update"], self.root, capture=False)

    def push(self, remote: str, ref: str, set_upstream: bool = False) -> None:
        args = ["fossil", "push"]
        if remote:
            args.append(remote)
        _run(args, self.root, capture=False)

    def reset_worktree(self) -> None:
        _run(["fossil", "revert"], self.root, check=False, capture=False)
        _run(["fossil", "clean", "--force"], self.root, check=False, capture=False)

    def cat(self, rev: str, path: str) -> str:
        return _run(["fossil", "cat", path, "-r", rev], self.root)


def _split_layout(base: str, parts: Sequence[str]) -> tuple[str, str, str] | None:
    """Split the path ``parts`` below ``base`` at the line of work.

    Returns ``(project base URL, line of work, path below the line)`` for a path
    under ``trunk`` / ``branches/<name>`` / ``tags/<name>``, or ``None`` outside
    that layout. The rightmost marker wins (see :meth:`SubversionBackend._layout`).
    """
    for i in reversed(range(len(parts))):
        if i > 0 and parts[i - 1] in ("branches", "tags"):
            # The segment after branches/ or tags/ is a name, even `trunk`.
            start, width = i - 1, 2
        elif parts[i] == "trunk":
            start, width = i, 1
        else:
            continue
        project = "/".join([base, *parts[:start]])
        return project, "/".join(parts[start : start + width]), "/".join(parts[start + width :])
    return None


class SubversionBackend(VCSBackend):
    """Apache Subversion (SVN) binding of the source-control capability.

    SVN is centralized (see ``tools/asf-svn/source-control.md``): ``commit``
    writes straight to the server, so there is nothing to ``fetch`` or ``push``;
    there is no staging area, so ``commit`` records every change in the working
    copy; and a line of work is a server-side directory under the conventional
    ``trunk`` / ``branches/<name>`` / ``tags/<name>`` layout.
    """

    name = "svn"
    distributed = False

    @classmethod
    def detect(cls, start: Path) -> Path | None:
        # SVN 1.7+ keeps a single .svn directory at the working-copy root.
        for d in (start, *start.parents):
            if (d / ".svn").exists():
                return d
        return None

    #: `svn info --show-item` and `svn cleanup --remove-unversioned` arrived in 1.9.
    min_version: tuple[int, int] = (1, 9)

    @staticmethod
    @functools.cache
    def _version() -> tuple[int, int] | None:
        try:
            out = subprocess.run(
                ["svn", "--version", "--quiet"], capture_output=True, text=True, check=True
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            return None
        match = re.match(r"(\d+)\.(\d+)", out.strip())
        return (int(match[1]), int(match[2])) if match else None

    @classmethod
    def is_available(cls) -> bool:
        version = cls._version()
        return version is not None and version >= cls.min_version

    def _svn(self, *args: str, capture: bool = True, check: bool = True) -> str:
        version = self._version()
        if version is not None and version < self.min_version:
            have = ".".join(map(str, version))
            need = ".".join(map(str, self.min_version))
            raise VCSError(f"svn {have} is too old: the svn backend needs Subversion {need}+")
        # --non-interactive: never block on an auth or conflict prompt the caller cannot answer.
        return _run(["svn", "--non-interactive", *args], self.root, capture=capture, check=check)

    @staticmethod
    def _relative_ref(ref: str) -> str:
        """Validate a layout-relative ref (``trunk``, ``feature``, ``branches/a/b``) and URL-quote it."""
        segments = ref.split("/")
        if any(seg in ("", ".", "..") for seg in segments):
            raise VCSError(f"svn: invalid branch or ref name {ref!r} (empty, '.' or '..' path segment)")
        return quote(ref, safe="/")

    def _url(self) -> str:
        return self._svn("info", "--show-item", "url").strip()

    def _layout(self) -> tuple[str, str, str] | None:
        """Split the working copy's URL at its line of work.

        Returns ``(project base URL, line of work, path below the line)`` for a
        URL under ``trunk`` / ``branches/<name>`` / ``tags/<name>`` — e.g.
        ``(".../asf/foo", "branches/fix", "sub")`` — or ``None`` outside that layout.
        The rightmost marker wins, so a project nested under a directory that is
        itself named ``branches`` (``^/branches/projects/foo/trunk``) resolves to
        ``foo``'s ``trunk``.
        """
        info = ET.fromstring(self._svn("info", "--xml"))
        root = info.findtext("entry/repository/root", "")
        rel = info.findtext("entry/relative-url", "").removeprefix("^").strip("/")
        return _split_layout(root, rel.split("/") if rel else [])

    def _require_layout(self, op: str) -> tuple[str, str, str]:
        layout = self._layout()
        if layout is None:
            raise VCSError(
                f"svn {op}: {self._url()} is not under a trunk/branches/tags layout; "
                f"pass a full URL (or ^/ repository-relative path) instead"
            )
        return layout

    def status(self) -> str:
        return self._svn("status", "--ignore-externals")

    def current_branch(self) -> str:
        # relative-url is URL-encoded; report the name decoded so it round-trips
        # through switch / new-branch, which quote exactly once.
        layout = self._layout()
        if layout is not None:
            return unquote(layout[1])
        # Outside the conventional layout, the repository-relative path is the line of work.
        return unquote(self._svn("info", "--show-item", "relative-url").strip().removeprefix("^").strip("/"))

    def diff(self, base: str | None = None, cached: bool = False, paths: Sequence[str] = ()) -> str:
        if cached:
            raise VCSError("svn does not support staging area/cached diff")
        args = ["diff"]
        if base:
            # svn compares the working copy against a *revision*; a line-of-work
            # name (`trunk`, a branch) would end in svn's own syntax error.
            if not re.fullmatch(r"\d+|HEAD|BASE|COMMITTED|PREV|\{[^{}]+\}", base):
                raise VCSError(
                    f"svn diff --base takes a revision (a number, HEAD, BASE, COMMITTED, PREV "
                    f"or {{DATE}}), not {base!r}"
                )
            args.extend(["-r", base])
        return self._svn(*args, "--", *paths)

    def log(
        self,
        max_count: int | None = None,
        grep: str | None = None,
        author: str | None = None,
        since: str | None = None,
        paths: Sequence[str] = (),
    ) -> str:
        # History lives on the server: read the line of work up to HEAD. svn log
        # takes one working-copy target, or a URL plus paths relative to it.
        targets = [self._url(), *paths] if len(paths) > 1 else list(paths) or ["."]
        since_dt: datetime | None = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError as exc:
                raise VCSError(f"svn log --since needs an ISO 8601 date, got {since!r}") from exc
            if since_dt.tzinfo is None:
                since_dt = since_dt.astimezone()  # naive dates are local time, as svn's {DATE} is
            # {DATE} resolves to the last revision *before* the date; the boundary is filtered below.
            rev_range = f"HEAD:{{{since}}}"
        else:
            rev_range = "HEAD:1"
        filtered = bool(grep or author or since)
        args = ["log", "--xml", "-r", rev_range]
        if max_count is not None and not filtered:
            args.extend(["-l", str(max_count)])
        try:
            grep_re = re.compile(grep) if grep else None
            author_re = re.compile(author) if author else None
        except re.error as exc:
            raise VCSError(f"svn log: invalid pattern: {exc}") from exc

        lines: list[str] = []
        for entry in ET.fromstring(self._svn(*args, "--", *targets)).iter("logentry"):
            msg = entry.findtext("msg", "")
            if grep_re and not grep_re.search(msg):
                continue
            if author_re and not author_re.search(entry.findtext("author", "")):
                continue
            if since_dt and datetime.fromisoformat(entry.findtext("date", "")) < since_dt:
                continue
            first_line = msg.splitlines()[0] if msg else ""
            lines.append(f"r{entry.get('revision')} {first_line}")
            if max_count is not None and len(lines) >= max_count:
                break
        return "".join(f"{line}\n" for line in lines)

    def create_branch(self, name: str) -> None:
        # A branch is a server-side copy of the current line of work at the
        # working copy's revision; the working copy then switches onto it,
        # carrying any local modifications, as `git checkout -b` does.
        base, line, sub = self._require_layout("new-branch")
        rev = self._svn("info", "--show-item", "revision").strip()
        if "/" in name:
            # The layout reads a line of work as branches/<one segment>.
            raise VCSError(f"svn: invalid branch or ref name {name!r} (a branch name is one path segment)")
        target = f"{base}/branches/{self._relative_ref(name)}"
        self._svn("copy", f"{base}/{line}@{rev}", target, "-m", f"Create branch {name} from {line}@{rev}")
        self._svn("switch", "/".join(filter(None, [target, sub])), capture=False)

    def switch(self, ref: str) -> None:
        # A URL or ^/ path is used as-is; otherwise `trunk`, `branches/<n>` and
        # `tags/<n>` name a line of work, and a bare name is a branch (the name
        # create_branch was given).
        if "://" in ref or ref.startswith("^/"):
            target = ref
        else:
            base, _, sub = self._require_layout("switch")
            if ref == "trunk" or ref.startswith(("branches/", "tags/")):
                line = ref
            elif "/" in ref:
                raise VCSError(f"svn: invalid branch or ref name {ref!r} (a branch name is one path segment)")
            else:
                line = f"branches/{ref}"
            target = "/".join(filter(None, [base, self._relative_ref(line), sub]))
        self._svn("switch", target, capture=False)

    def stage(self, paths: Sequence[str]) -> None:
        if not paths:
            raise VCSError("stage: refusing to stage nothing (pass explicit paths)")
        # `svn add` schedules new paths (and their unversioned parents) and
        # skips versioned ones; a versioned path gone from disk, given directly
        # or found under a given directory (`!` in `svn status`), is scheduled
        # for deletion, as `git add <dir>` stages removals.
        # lexists, not exists: a versioned symlink whose target is missing is
        # still on disk and must not be scheduled for deletion.
        missing = [p for p in paths if not os.path.lexists(self.root / p)]
        present = [p for p in paths if p not in missing]
        if present:
            status = ET.fromstring(self._svn("status", "--xml", "--", *present))
            missing += [
                entry.get("path", "")
                for entry in status.iter("entry")
                if entry.find("wc-status[@item='missing']") is not None
            ]
        if missing:
            self._svn("delete", "--", *missing, capture=False)
        if present:
            self._svn("add", "--force", "--parents", "--", *present, capture=False)

    def commit(self, message: str) -> None:
        # No staging area: this writes every change in the working copy to the server.
        self._svn("commit", "-m", message, capture=False)

    def changed_paths(self) -> list[tuple[str, str]]:
        status = ET.fromstring(self._svn("status", "--xml", "--ignore-externals"))
        out: list[tuple[str, str]] = []
        for entry in status.iter("entry"):
            wc = entry.find("wc-status")
            if wc is None:
                continue
            item = wc.get("item", "")
            if item in ("normal", "external", "ignored", "none") and wc.get("props") == "modified":
                item = "modified"  # a property-only change is still committed
            if item in ("normal", "external", "ignored", "none"):
                continue
            path = Path(entry.get("path", ""))
            rel = path.relative_to(self.root) if path.is_absolute() else path
            out.append((item, rel.as_posix()))
        return out

    def fetch(self, remote: str | None = None, ref: str | None = None) -> None:
        # Nothing to sync: refs live on the server and every history read
        # (log, cat, diff --base) queries it directly. `svn update` would
        # change the working copy, which fetch must not do.
        return None

    def update(self) -> None:
        # A commit from an out-of-date working copy fails, so callers update first.
        self._svn("update", capture=False)

    @classmethod
    def checkout(cls, url: str, dest: Path) -> None:
        _require_new_dest(dest)
        _run(["svn", "--non-interactive", "checkout", "--", url, str(dest)], dest.parent, capture=False)

    def push(self, remote: str, ref: str, set_upstream: bool = False) -> None:
        raise VCSError(
            "svn is centralized: `commit` already published the change to the server; there is nothing to push"
        )

    def reset_worktree(self) -> None:
        self._svn("revert", "--recursive", ".", capture=False)
        # Removes unversioned files but keeps ignored ones, like `git clean -fd`.
        self._svn("cleanup", "--remove-unversioned", capture=False)

    def cat(self, rev: str, path: str) -> str:
        # Operative revision on the working-copy path (pegged at BASE) follows
        # copy history, so a pre-branch revision resolves through trunk. A
        # trailing "@" keeps an "@" inside the path from being read as a peg.
        try:
            return self._svn("cat", "-r", rev, "--", f"{path}@")
        except VCSError:
            pass
        # The path is no longer in the working copy. Find the revision on this
        # line of work that deleted it (or a parent) and read it through the
        # revision before that, so copy history is still followed back past
        # the branch point.
        info = ET.fromstring(self._svn("info", "--xml"))
        root = info.findtext("entry/repository/root", "")
        line = unquote(info.findtext("entry/relative-url", "").removeprefix("^")).rstrip("/")
        target = f"{line}/{path.strip('/')}"
        for entry in ET.fromstring(self._svn("log", "--xml", "-v", "-r", "HEAD:1", ".")).iter("logentry"):
            for changed in entry.iter("path"):
                gone = changed.text or ""
                if changed.get("action") in ("D", "R") and (target == gone or target.startswith(f"{gone}/")):
                    peg = int(entry.get("revision", "0")) - 1
                    return self._svn("cat", "-r", rev, f"{root}{quote(target)}@{peg}")
        # Never deleted on this line: resolve it as it was at rev.
        return self._svn("cat", f"{root}{quote(target)}@{rev}")


# Registry, in detection-priority order. New VCS bridges register here.
BACKENDS: tuple[type[VCSBackend], ...] = (
    GitBackend,
    MercurialBackend,
    FossilBackend,
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
# Hosting probe — is the project Subversion-hosted? (read by `setup`)
# --------------------------------------------------------------------------

#: The trailer git-svn writes into every commit it imports from Subversion.
_GIT_SVN_ID = re.compile(r"^git-svn-id: (\S+)@(\d+) ([0-9a-fA-F-]{36})\s*$", re.MULTILINE)

#: The layout the svn backend supports, as `probe` reports it.
STANDARD_LAYOUT = "trunk/branches/tags"


def _svn_location(url: str, repository_root: str | None) -> dict[str, str | None]:
    """Describe an svn URL: its repository root, project base URL, line of work and layout."""
    url = url.rstrip("/")
    root = repository_root.rstrip("/") if repository_root else None
    if root and (url == root or url.startswith(root + "/")):
        base, rel = root, url[len(root) :].strip("/")
    else:
        # Root unknown: split the URL's path, which the rightmost-marker rule makes safe.
        split = urlsplit(url)
        base, rel = f"{split.scheme}://{split.netloc}", split.path.strip("/")
    layout = _split_layout(base, rel.split("/") if rel else [])
    return {
        "url": url,
        "repository_root": root,
        "project_url": layout[0] if layout else url,
        "line_of_work": unquote(layout[1]) if layout else None,
        "layout": STANDARD_LAYOUT if layout else "other",
    }


def _probe_svn_wc(root: Path, notes: list[str]) -> dict[str, str | None] | None:
    """Read an svn working copy's URL and repository from local metadata only."""
    if SubversionBackend.is_available():
        try:
            # `svn info` on a working-copy path reads .svn/ only; it never contacts the server.
            info = ET.fromstring(_run(["svn", "--non-interactive", "info", "--xml", "."], root))
        except (VCSError, ET.ParseError) as exc:
            notes.append(f"`svn info` failed ({exc}); read .svn/wc.db instead")
        else:
            url = info.findtext("entry/url")
            if url:
                location = _svn_location(url, info.findtext("entry/repository/root") or None)
                return {
                    **location,
                    "uuid": info.findtext("entry/repository/uuid") or None,
                    "source": "svn info",
                }
    else:
        notes.append("svn 1.9+ is not installed; read .svn/wc.db instead")
    db = root / ".svn" / "wc.db"
    try:
        con = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
        try:
            row = con.execute(
                "SELECT r.root, r.uuid, n.repos_path FROM nodes n JOIN repository r ON r.id = n.repos_id "
                "WHERE n.local_relpath = '' AND n.op_depth = 0"
            ).fetchone()
        finally:
            con.close()
    except sqlite3.Error as exc:
        notes.append(f"could not read {db}: {exc}")
        return None
    if row is None:
        notes.append(f"{db} names no repository for the working-copy root")
        return None
    repository_root, uuid, repos_path = (str(v) if v is not None else "" for v in row)
    url = repository_root.rstrip("/") + (f"/{quote(repos_path)}" if repos_path else "")
    return {**_svn_location(url, repository_root or None), "uuid": uuid or None, "source": ".svn/wc.db"}


def _git_read(root: Path, *args: str) -> str | None:
    try:
        return _run(["git", *args], root)
    except VCSError:
        return None


def _probe_git(root: Path, notes: list[str]) -> tuple[str, dict[str, str | None] | None]:
    """Classify a Git checkout: a git-svn clone, a git-svn mirror, or plain Git."""
    remotes: dict[str, dict[str, str]] = {}
    for line in (_git_read(root, "config", "--get-regexp", r"^svn-remote\.") or "").splitlines():
        key, _, value = line.partition(" ")
        name, _, field = key.removeprefix("svn-remote.").rpartition(".")
        remotes.setdefault(name, {}).setdefault(field, value)  # first `fetch` wins
    named = {n: r for n, r in remotes.items() if r.get("url")}
    if named:
        name = "svn" if "svn" in named else sorted(named)[0]
        remote = named[name]
        fetched = remote.get("fetch", "").partition(":")[0].strip("/")
        url = remote["url"].rstrip("/") + (f"/{fetched}" if fetched else "")
        repository_root = uuid = None
        common = _git_read(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
        metadata = Path(common.strip()) / "svn" / ".metadata" if common else None
        if metadata is not None and metadata.is_file():
            repository_root = _git_read(root, "config", "-f", str(metadata), f"svn-remote.{name}.reposRoot")
            uuid = _git_read(root, "config", "-f", str(metadata), f"svn-remote.{name}.uuid")
        if not repository_root:
            notes.append("git-svn has not recorded the repository root yet (no .git/svn/.metadata)")
        location = _svn_location(url, repository_root.strip() if repository_root else None)
        return "git-svn-clone", {
            **location,
            "uuid": uuid.strip() if uuid else None,
            "source": "git-svn config",
        }
    match = _GIT_SVN_ID.search(_git_read(root, "log", "-n", "1", "--format=%B", "HEAD") or "")
    if match:
        notes.append(
            "HEAD carries a git-svn-id trailer but there is no svn-remote: a read-only mirror of "
            "Subversion; its repository root is not knowable offline"
        )
        return "git-svn-mirror", {**_svn_location(match[1], None), "uuid": match[3], "source": "git-svn-id"}
    return "git", None


def probe(start: Path) -> dict[str, object]:
    """Report whether the project at ``start`` is Subversion-hosted, and where.

    Read-only and offline: it reads working-copy metadata (``svn info``, ``.svn/wc.db``,
    git config, ``.git/svn/.metadata``, HEAD's message) and never runs a command that
    reaches a server. ``kind`` is ``svn-working-copy``, ``git-svn-clone``, ``git-svn-mirror``,
    another backend's name (``git``, ``hg``, ``fossil``) or ``none``; ``proposal`` holds the
    ``project.md`` values a Subversion-hosted project would declare, else ``None``.
    """
    notes: list[str] = []
    backend = detect_backend(start)
    kind = backend.name if backend else "none"
    svn: dict[str, str | None] | None = None
    if isinstance(backend, SubversionBackend):
        kind = "svn-working-copy"
        svn = _probe_svn_wc(backend.root, notes)
    elif isinstance(backend, GitBackend):
        kind, svn = _probe_git(backend.root, notes)
        svn_root = SubversionBackend.detect(start)
        if svn_root is not None:
            notes.append(
                f"an svn working copy at {svn_root} also contains this path; magpie-vcs uses git here"
            )
    svn_hosted = kind in ("svn-working-copy", "git-svn-clone", "git-svn-mirror")
    proposal: dict[str, str | None] | None = None
    if svn_hosted:
        proposal = {
            "vcs_backend": "svn",
            "svn_url": svn["project_url"] if svn else None,
            "svn_repository_root": svn["repository_root"] if svn else None,
            "upstream_default_branch": "trunk" if svn and svn["layout"] == STANDARD_LAYOUT else None,
        }
        if svn and svn["layout"] != STANDARD_LAYOUT:
            notes.append(
                f"{svn['url']} is not under a trunk/branches/tags layout: the svn backend's "
                "new-branch and name-based switch refuse there"
            )
        if kind != "svn-working-copy":
            notes.append(
                "this checkout is Git: magpie-vcs drives it with the git backend, which cannot commit "
                "to Subversion; the svn backend needs an `svn checkout` of the project"
            )
    return {
        "path": str(start),
        "backend": backend.name if backend else None,
        "root": str(backend.root) if backend else None,
        "kind": kind,
        "svn_hosted": svn_hosted,
        "svn": svn,
        "proposal": proposal,
        "notes": notes,
    }


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
    sub.add_parser("probe", help="JSON: is the project Subversion-hosted, and where (read-only, offline)")
    sub.add_parser("status", help="porcelain working-tree status")
    sub.add_parser("clean", help="exit 0 if clean, 1 if dirty")
    sub.add_parser("branch", help="print the current branch")

    p = sub.add_parser("diff", help="show changes")
    p.add_argument("--base", help="diff against this ref")
    p.add_argument("--cached", action="store_true", help="diff the staged change")
    p.add_argument("-o", "--output", help="write the diff to this file (a patch) instead of stdout")
    p.add_argument("paths", nargs="*")

    p = sub.add_parser("log", help="history read")
    p.add_argument("-n", "--max-count", type=int)
    p.add_argument("--grep")
    p.add_argument("--author")
    p.add_argument("--since")
    p.add_argument("paths", nargs="*")

    p = sub.add_parser("new-branch", help="create + switch to a branch")
    _add_scrub_args(p, gate=True)
    p.add_argument("name")

    p = sub.add_parser("switch", help="switch to an existing ref")
    p.add_argument("ref")

    p = sub.add_parser("stage", help="stage paths for commit")
    p.add_argument("paths", nargs="+")

    p = sub.add_parser("commit", help="record the staged change")
    msg = p.add_mutually_exclusive_group(required=True)
    msg.add_argument("-m", "--message")
    msg.add_argument("-F", "--message-file", help="read the message from this file")
    _add_scrub_args(p, gate=True)

    p = sub.add_parser("fix-flow", help="print (JSON) the security fix flow for this working copy")
    p.add_argument("--declared", help="the manifest's Tools enabled -> Source control value")

    p = sub.add_parser("scrub", help="embargo scrub of a message, the working-copy diff and a branch name")
    p.add_argument("-F", "--message-file", help="the commit message to scrub")
    p.add_argument("--diff", action="store_true", help="scrub the lines the working-copy diff adds")
    p.add_argument("--diff-file", help="scrub the lines this patch file adds")
    p.add_argument("--branch", help="a branch name to scrub")
    _add_scrub_args(p, gate=False)

    p = sub.add_parser(
        "propose-commit", help="print (JSON) the scrubbed commit proposal (centralized backends)"
    )
    p.add_argument("-F", "--message-file", required=True, help="the agreed commit message")
    p.add_argument("--branch", help="also propose new-branch <name> before the commit")
    p.add_argument(
        "--expect", action="append", required=True, help="an agreed path (file or directory); repeatable"
    )
    _add_scrub_args(p, gate=False)

    p = sub.add_parser("fetch", help="sync refs from the forge")
    p.add_argument("remote", nargs="?")
    p.add_argument("ref", nargs="?")

    sub.add_parser("update", help="bring the working copy up to date (never merges)")

    p = sub.add_parser("checkout", help="create a new working copy (needs --backend)")
    p.add_argument("url")
    p.add_argument("dest")

    p = sub.add_parser("push", help="publish a ref to the forge")
    p.add_argument("-u", "--set-upstream", action="store_true")
    p.add_argument("remote")
    p.add_argument("ref")

    sub.add_parser("reset-worktree", help="discard all uncommitted changes")

    p = sub.add_parser("cat", help="print file content at a specific revision")
    p.add_argument("rev", help="revision or ref")
    p.add_argument("path", help="file path relative to repository root")

    return parser


def _add_scrub_args(p: argparse.ArgumentParser, *, gate: bool) -> None:
    if gate:
        p.add_argument(
            "--scrub",
            action="store_true",
            help="refuse (exit 3) before running the VCS when the publication scrub finds a hit",
        )
    p.add_argument("--term", action="append", default=[], help="an extra forbidden term; repeatable")
    p.add_argument(
        "--allow", action="append", default=[], help="drop a default term by its label (the user's call)"
    )
    p.add_argument(
        "--private-file",
        action="append",
        default=[],
        help="private text (e.g. the tracker issue) the message must not quote; repeatable",
    )


def _read(path: str) -> str:
    try:
        return Path(path).read_text()
    except OSError as exc:
        raise VCSError(f"cannot read {path}: {exc.strerror}") from exc


def _scrub_kwargs(ns: argparse.Namespace) -> dict[str, Any]:
    return {
        "extra_terms": ns.term,
        "allow": ns.allow,
        "private_texts": [_read(f) for f in ns.private_file],
    }


def _gate(ns: argparse.Namespace, **surfaces: Any) -> int | None:
    """Run the publication scrub for a gated write; return 3 (and say why) on a hit."""
    if not getattr(ns, "scrub", False):
        return None
    result = publication.scrub(**surfaces, **_scrub_kwargs(ns))
    if result["clean"]:
        return None
    print(f"magpie-vcs: {ns.op} refused by the publication scrub:", file=sys.stderr)
    print(json.dumps(result["hits"], indent=2), file=sys.stderr)
    return 3


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
        if ns.op == "probe":
            print(json.dumps(probe(start), indent=2))
            return 0

        if ns.op == "fix-flow":
            try:
                found: VCSBackend | None = get_backend(start, ns.backend)
            except VCSError:
                if not ns.declared:
                    raise
                found = None
            flow = publication.fix_flow(
                found.name if found else None, found.distributed if found else None, ns.declared
            )
            print(json.dumps(flow, indent=2))
            return 0

        if ns.op == "checkout":
            # There is no working copy to detect yet, so the backend is named.
            forced = ns.backend or os.environ.get(BACKEND_ENV) or ""
            checkout_cls = _BACKENDS_BY_NAME.get(forced)
            if checkout_cls is None:
                known = ", ".join(sorted(_BACKENDS_BY_NAME))
                raise VCSError(f"checkout needs --backend (or ${BACKEND_ENV}) naming one of: {known}")
            checkout_cls.checkout(ns.url, (start / ns.dest).resolve())
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
            patch = backend.diff(base=ns.base, cached=ns.cached, paths=ns.paths)
            if ns.output:
                Path(ns.output).write_text(patch)
            else:
                sys.stdout.write(patch)
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
            refused = _gate(ns, branch=ns.name)
            if refused:
                return refused
            backend.create_branch(ns.name)
        elif ns.op == "switch":
            backend.switch(ns.ref)
        elif ns.op == "stage":
            backend.stage(ns.paths)
        elif ns.op == "commit":
            message = ns.message if ns.message is not None else _read(ns.message_file)
            if ns.scrub:
                # What the commit publishes: staged changes on a distributed
                # backend, every change in the working copy on svn.
                diff = backend.diff(cached=True) if backend.distributed else backend.diff()
                refused = _gate(ns, message=message, diff=diff)
                if refused:
                    return refused
            backend.commit(message)
        elif ns.op == "scrub":
            result = publication.scrub(
                message=_read(ns.message_file) if ns.message_file else None,
                diff=(backend.diff() if ns.diff else "") + (_read(ns.diff_file) if ns.diff_file else ""),
                branch=ns.branch,
                **_scrub_kwargs(ns),
            )
            print(json.dumps(result, indent=2))
            return 0 if result["clean"] else 1
        elif ns.op == "propose-commit":
            proposal = publication.commit_proposal(
                backend,
                message=_read(ns.message_file),
                message_file=str(Path(ns.message_file).resolve()),
                branch=ns.branch,
                expect=ns.expect,
                extra_terms=ns.term,
                allow=ns.allow,
                private_files=[str(Path(f).resolve()) for f in ns.private_file],
            )
            print(json.dumps(proposal, indent=2))
            return 0 if proposal["ready"] else 1
        elif ns.op == "fetch":
            backend.fetch(ns.remote, ns.ref)
        elif ns.op == "update":
            backend.update()
        elif ns.op == "push":
            backend.push(ns.remote, ns.ref, set_upstream=ns.set_upstream)
        elif ns.op == "reset-worktree":
            backend.reset_worktree()
        elif ns.op == "cat":
            sys.stdout.write(backend.cat(ns.rev, ns.path))
        else:  # pragma: no cover - argparse enforces the choices
            parser.error(f"unknown operation {ns.op!r}")
    except (VCSError, publication.PublicationError) as exc:
        print(f"magpie-vcs: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
