# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""The working copy under the tracker: Git or SVN.

Only three things are needed from it: what changed under the tracker root,
a history-preserving move (closing a report in a folder-per-state tracker),
and the commit-and-push that shares a session's work with the team. All of
it is scoped to the tracker root — nothing outside it is ever staged.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path


class VcsError(RuntimeError):
    pass


class VcsRefused(VcsError):
    """A publish that would send something other than tracker changes."""


# Every git call runs with the helpers git can execute switched off. These
# operations may run outside the sandbox (vetted-op-read / vetted-op-tracker),
# and the repository is chosen by a policy file; its own configuration must
# not be able to start a program there.
_GIT_SAFE = (
    "-c", "core.fsmonitor=false",
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.sshCommand=ssh",
    # No automatic gc or maintenance: gc.recentObjectsHook and friends are commands.
    "-c", "gc.auto=0",
    "-c", "maintenance.auto=false",
    # Only network transports: a local-path or file:// remote would run
    # receive-pack — and that repository's own hooks — on this machine.
    "-c", "protocol.allow=never",
    "-c", "protocol.https.allow=always",
    "-c", "protocol.ssh.allow=always",
)  # fmt: skip

#: Push URL schemes publish accepts. Tests widen this; production cannot.
_PUSH_SCHEMES = ("https", "ssh")
_SCP_LIKE = re.compile(r"^(?:[A-Za-z0-9._-]+@)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}:(?!/)")


def push_url_allowed(url: str) -> bool:
    """An https:// or ssh:// URL with a host, or scp-style ``user@host.tld:path``."""
    url = url.strip()
    if "://" in url:
        parts = urllib.parse.urlsplit(url)
        return parts.scheme.lower() in _PUSH_SCHEMES and bool(parts.hostname)
    return "ssh" in _PUSH_SCHEMES and bool(_SCP_LIKE.match(url))


# Repository-local configuration keys known not to run anything. Any other
# key set in the repository's own config (filter drivers, merge or diff
# drivers, aliases, include files, url rewrites, gpg.program, …) refuses the
# operation: a helper there could run a program outside the sandbox.
_SAFE_LOCAL_KEY = re.compile(
    r"^(?:"
    r"core\.(?:repositoryformatversion|filemode|bare|logallrefupdates|ignorecase|precomposeunicode"
    r"|autocrlf|safecrlf|eol|symlinks|sparsecheckout|untrackedcache|splitindex|commitgraph|longpaths"
    r"|quotepath|checkstat|trustctime)"
    r"|extensions\.(?:objectformat|worktreeconfig|refstorage)"
    r"|remote\.[^\s]+\.(?:url|pushurl|fetch|push|prune|tagopt|mirror|skipdefaultupdate|promisor)"
    r"|branch\.[^\s]+\.(?:remote|merge|pushremote|rebase|description)"
    r"|user\.(?:name|email|signingkey|useconfigonly)"
    r"|push\.(?:default|autosetupremote|followtags)|pull\.(?:rebase|ff)|fetch\.prune"
    r"|init\.defaultbranch|commit\.gpgsign|tag\.gpgsign|gpg\.format"
    r"|index\.(?:version|threads|skiphash)|feature\.(?:manyfiles|experimental)"
    r")$",
    re.IGNORECASE,
)


#: The empty tree, per object format: attributes are read from it (see `_run`).
_EMPTY_TREE = {
    "sha1": "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
    "sha256": "6ef19b41225c5369f1c104d45d8d85efa9b057b53b14b4b9b939dd74decc5321",
}


@dataclass
class WorkingCopy:
    kind: str  # "git", "svn", or "none"
    top: Path
    _empty_tree: str = field(default=_EMPTY_TREE["sha1"], repr=False)

    def _check_git_config(self) -> None:
        """Refuse a repository whose own config sets anything outside the
        known-safe keys (see `_SAFE_LOCAL_KEY`). Reading config runs nothing."""
        proc = subprocess.run(
            ["git", "config", "--list", "--show-scope", "--null"],
            cwd=self.top,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise VcsRefused(f"cannot read the repository's git config: {proc.stderr.strip()}")
        risky = []
        sha256 = False
        # With --show-scope --null git emits "scope\0key\nvalue\0" per entry.
        fields = proc.stdout.split("\0")
        for scope, entry in zip(fields[0::2], fields[1::2], strict=False):
            key, _, value = entry.partition("\n")
            if scope in ("local", "worktree") and not _SAFE_LOCAL_KEY.match(key):
                risky.append(key)
            if key.lower() == "extensions.objectformat" and value.strip().lower() == "sha256":
                sha256 = True
        self._empty_tree = _EMPTY_TREE["sha256" if sha256 else "sha1"]
        if risky:
            raise VcsRefused(
                "the repository's own git config sets "
                + ", ".join(sorted(set(risky))[:5])
                + ", which could run a program when git runs here outside the sandbox; "
                "remove it from .git/config, or run the git step by hand"
            )

    def _run(self, *args: str, check: bool = True) -> str:
        env = None
        if args and args[0] == "git":
            # Checked before *every* git command, not once: the window between
            # the check and the command is as small as it can be made.
            self._check_git_config()
            args = ("git", *_GIT_SAFE, *args[1:])
            # And within that window, attributes come from the empty tree, not
            # the working tree the agent can write: no `.gitattributes` there can
            # switch on a filter, diff or merge driver whatever the config says
            # by then. Git older than 2.42 ignores the variable.
            env = {**os.environ, "GIT_ATTR_SOURCE": self._empty_tree}
        try:
            proc = subprocess.run(args, cwd=self.top, capture_output=True, text=True, check=False, env=env)
        except FileNotFoundError as exc:
            raise VcsError(f"{args[0]} not found on PATH") from exc
        if check and proc.returncode != 0:
            raise VcsError(f"{' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
        return proc.stdout

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.top.resolve()).as_posix()

    # ------------------------------------------------------------ status

    def status(self, root: Path) -> list[dict[str, str]]:
        if self.kind == "git":
            out = self._run("git", "status", "--porcelain=v1", "--untracked-files=all", "--", self.rel(root))
            return [{"status": ln[:2].strip() or "?", "path": ln[3:]} for ln in out.splitlines() if ln]
        if self.kind == "svn":
            out = self._run("svn", "status", self.rel(root))
            return [
                {"status": ln[0], "path": ln[8:].strip()} for ln in out.splitlines() if ln and ln[0] != " "
            ]
        return []

    def push_destination(self) -> str | None:
        """The remote-tracking ref `git push` sends this branch to (`@{push}`), or None.

        Outgoing commits are measured against that ref, not against "every
        remote": a commit already on `origin/feature` but not on `origin/main`
        would still be sent when the branch pushes to `main`.
        """
        if self.kind != "git":
            return None
        try:
            ref = self._run("git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{push}").strip()
            if not ref:
                return None
            self._run("git", "rev-parse", "--verify", "--quiet", ref)
        except VcsError:
            return None
        return ref

    def outgoing(self) -> list[str] | None:
        """Commits a push would send; None when the push destination is unknown."""
        if self.kind != "git":
            return []
        dest = self.push_destination()
        if dest is None:
            return None
        out = self._run("git", "rev-list", "HEAD", "--not", dest)
        return [ln for ln in out.split() if ln]

    def push_target(self) -> tuple[str, str] | None:
        """``(remote, remote ref)`` this branch pushes to, or None when unknown.

        The remote is git's own push resolution (``%(push:remotename)``), so a
        remote whose name contains ``/`` is not split in the wrong place. The
        ref is ``%(push:remoteref)`` when git fills it in; otherwise it is what
        ``push.default`` would push to: the upstream branch for ``simple`` /
        ``upstream`` (git's default), the same name for ``current`` /
        ``matching``.
        """
        if self.kind != "git":
            return None
        branch = self._run("git", "symbolic-ref", "-q", "HEAD", check=False).strip()
        if not branch.startswith("refs/heads/"):
            return None
        out = self._run(
            "git", "for-each-ref", "--format=%(push:remotename)%00%(push:remoteref)", branch, check=False
        ).strip()
        remote, _, ref = out.partition("\0")
        if remote and not ref:
            short = branch.removeprefix("refs/heads/")
            mode = self._run("git", "config", "--get", "push.default", check=False).strip().lower()
            if mode in ("", "simple", "upstream", "tracking"):
                ref = self._run("git", "config", "--get", f"branch.{short}.merge", check=False).strip()
            elif mode in ("current", "matching"):
                ref = branch
        return (remote, ref) if remote and ref.startswith("refs/heads/") else None

    def _push(self, target: tuple[str, str]) -> None:
        """Push HEAD to exactly the checked ref: an explicit refspec, so neither
        ``push.default=matching`` nor a remote's ``push`` refspecs nor
        ``push.followTags`` can add other branches or tags to the push."""
        remote, ref = target
        self._run("git", "push", "--no-verify", "--no-follow-tags", remote, f"HEAD:{ref}")

    def _check_outgoing_scoped(self, rel_root: str) -> tuple[list[str], tuple[str, str]]:
        """Refuse a push that would also publish anything outside the tracker
        folder — on a shared branch that is someone else's work — or whose
        destination cannot be established. Returns the outgoing commits and the
        ``(remote, ref)`` they were checked against, which is all a push sends."""
        commits = self.outgoing()
        target = self.push_target()
        if commits is None or target is None:
            raise VcsRefused(
                "cannot tell where `git push` would send this branch (no upstream or push destination); "
                "set one (for example `git push -u origin <branch>` once, by hand) before publishing"
            )
        dest = self.push_destination() or ""
        remote = target[0]
        url = self._run("git", "remote", "get-url", "--push", remote).strip()
        if not push_url_allowed(url):
            raise VcsRefused(
                f"refusing to push to {url!r}: publish pushes only to an https:// or ssh:// remote "
                "(a local path or file:// remote would run that repository's hooks on this machine)"
            )
        prefix = "" if rel_root in ("", ".") else rel_root.rstrip("/") + "/"
        for sha in commits:
            # A plain commit is compared with its parent. A merge is compared
            # with --cc: only paths that differ from *every* parent, i.e. changes
            # made in the merge itself. What a merge brings in from a parent is
            # judged where it was made — that parent's commits are either
            # already at the destination or outgoing and checked here too.
            # -z: paths unquoted.
            parents = self._run("git", "rev-list", "--parents", "-n", "1", sha).split()[1:]
            mode = ["--cc"] if len(parents) > 1 else ["--root"]
            out = self._run("git", "diff-tree", *mode, "-r", "--no-commit-id", "--name-only", "-z", sha)
            paths = [p for p in out.split("\0") if p]
            stray = [p for p in paths if prefix and not p.startswith(prefix)]
            if stray:
                raise VcsRefused(
                    f"the branch has unpushed commit {sha[:12]} touching files outside {rel_root}/ "
                    f"({', '.join(stray[:3])}); pushing would publish them too. Push or move that work "
                    "first, or keep the tracker on its own branch."
                )
        # Per-commit checks cannot see a merge that keeps an *old* version of a
        # file the destination has since changed (-s ours): that is a revert the
        # push would publish. Compare the trees too.
        tree = self._run("git", "diff", "--name-only", "-z", dest, "HEAD")
        stray = [p for p in tree.split("\0") if p and prefix and not p.startswith(prefix)]
        if stray:
            raise VcsRefused(
                f"pushing would change files outside {rel_root}/ at the destination "
                f"({', '.join(stray[:3])}); refusing"
            )
        return commits, target

    def unpushed(self) -> int | None:
        """Commits not yet at the push destination; None when that is unknown.

        A publish whose commit succeeded but whose push failed leaves the tracker
        clean yet unpublished; this is how `pending` and `publish` still see it.
        """
        if self.kind != "git":
            return 0
        commits = self.outgoing()
        return None if commits is None else len(commits)

    def remotes(self) -> list[str]:
        if self.kind == "git":
            out = self._run("git", "remote", "-v", check=False)
            return sorted({ln.split()[1] for ln in out.splitlines() if len(ln.split()) >= 2})
        if self.kind == "svn":
            out = self._run("svn", "info", "--show-item", "url", check=False)
            return [out.strip()] if out.strip() else []
        return []

    # ------------------------------------------------------------ move

    def _tracked(self, path: Path) -> bool:
        if self.kind == "git":
            return bool(self._run("git", "ls-files", "--", self.rel(path), check=False).strip())
        if self.kind == "svn":
            out = self._run("svn", "status", "--depth", "empty", self.rel(path), check=False)
            return not out.startswith("?")
        return False

    def move(self, src: Path, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if self.kind == "git" and self._tracked(src):
            self._run("git", "mv", self.rel(src), self.rel(dst))
        elif self.kind == "svn" and self._tracked(src):
            self._run(
                "svn", "add", "--parents", "--force", "--depth", "empty", self.rel(dst.parent), check=False
            )
            self._run("svn", "mv", self.rel(src), self.rel(dst))
        else:
            shutil.move(str(src), str(dst))

    # ------------------------------------------------------------ publish

    def publish(self, root: Path, message: str, trailers: list[str], push: bool) -> dict[str, object]:
        rel_root = self.rel(root)
        if self.kind == "git":
            if push:
                self._check_outgoing_scoped(rel_root)
            self._run("git", "add", "-A", "--", rel_root)
            if not self._run("git", "diff", "--cached", "--name-only", "--", rel_root).strip():
                # An earlier publish may have committed without pushing; with
                # --push, push it now (an unknown destination was refused above).
                commits, target = self._check_outgoing_scoped(rel_root) if push else ([], ("", ""))
                if push and commits:
                    self._push(target)
                    revision = self._run("git", "rev-parse", "HEAD").strip()
                    return {
                        "committed": False,
                        "pushed": True,
                        "revision": revision,
                        "note": "pushed earlier commits",
                    }
                return {"committed": False, "pushed": False, "revision": None, "note": "nothing to commit"}
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
                fh.write(message)
                msg_path = fh.name
            args = ["git", "commit", "--no-verify", "-F", msg_path]
            for trailer in trailers:
                args += ["--trailer", trailer]
            args += ["--", rel_root]
            try:
                self._run(*args)
            finally:
                Path(msg_path).unlink(missing_ok=True)
            revision = self._run("git", "rev-parse", "HEAD").strip()
            pushed = False
            if push:
                _, target = self._check_outgoing_scoped(rel_root)
                self._push(target)
                pushed = True
            return {"committed": True, "pushed": pushed, "revision": revision}
        if self.kind == "svn":
            for entry in self.status(root):
                if entry["status"] == "?":
                    self._run("svn", "add", "--parents", "--force", entry["path"])
                elif entry["status"] == "!":
                    self._run("svn", "rm", "--force", entry["path"])
            if not self.status(root):
                return {"committed": False, "pushed": False, "revision": None, "note": "nothing to commit"}
            full = message.rstrip("\n") + ("\n\n" + "\n".join(trailers) if trailers else "") + "\n"
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
                fh.write(full)
                msg_path = fh.name
            try:
                out = self._run("svn", "commit", "-F", msg_path, rel_root)
            finally:
                Path(msg_path).unlink(missing_ok=True)
            m = re.search(r"Committed revision (\d+)", out)
            # An SVN commit is the publish: there is no separate push.
            return {"committed": True, "pushed": True, "revision": m.group(1) if m else None}
        raise VcsError("the tracker root is not inside a Git or SVN working copy")


def detect(root: Path) -> WorkingCopy:
    """Find the working copy that contains ``root`` (nearest ``.git`` / ``.svn``)."""
    start = root.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return WorkingCopy("git", candidate)
        if (candidate / ".svn").is_dir():
            return WorkingCopy("svn", candidate)
    return WorkingCopy("none", start)
