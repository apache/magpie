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
"""
``vetted-op-git``: the git operations a sandboxed agent cannot run, as closed shapes.

Three things a sandboxed session routinely cannot do, and used to hand to the
user as a command to paste:

* **Push over SSH.** The sandbox routes network through an HTTP proxy, so an
  SSH transport gets no TCP at all, and a hardware key's touch prompt cannot
  reach the user from inside it.
* **Write a linked worktree's administrative directory.** Harnesses keep
  ``.git/worktrees/<name>/`` read-only for worktrees the session did not
  create, so moving such a worktree to a rebased commit fails half-way.
* **Add or remove a linked worktree**, for the same reason.

Each operation here is one of those, with every parameter validated and every
target bounded by the approved policy's ``[git]`` table. The entry point runs
outside the sandbox and stays behind the harness's confirmation (``ask``), like
``vetted-op``: it removes the copy and paste, not the human decision.

What makes running git outside the sandbox safe here, beyond the closed shapes:

* **The pre-push checks run in the sandbox, not here.** A push never runs a
  hook. Whatever a ``pre-push`` hook would run — ``.git/hooks/pre-push``, or a
  hook manager reading its configuration from the working tree — is code the
  agent can write, and running it here would run that code outside the
  sandbox; the harness confirmation shows the push, not the code the hook
  would execute. The caller runs the same checks inside the sandbox first
  (for prek: ``prek run --hook-stage pre-push --from-ref <base> --to-ref
  <branch>``), fixes what they report, and only then pushes. The checks still
  run; they just run where working-tree code belongs.
* **No repository code runs.** Every operation switches hooks off
  (``core.hooksPath=/dev/null``, plus ``--no-verify`` on the push), so neither
  a ``pre-push`` nor a ``post-checkout`` hook can run code from the working
  tree.
* **No repository configuration steers git.** A key that makes git run a
  program, rewrite a URL, or pick credentials (``core.sshCommand``,
  ``url.*.insteadOf``, ``filter.*``, ``core.fsmonitor``, ``include.path``, …)
  can be planted in a repository's own config by anything that writes it. The
  operation refuses to run when the local or worktree config holds any key
  outside a short list of inert ones (`SAFE_LOCAL_KEY`). Global and system
  configuration are the user's own and stay in effect, so an SSH wrapper or a
  signing setup there keeps working.
* **No environment steers git.** Every ``GIT_*`` variable is dropped, and
  ``HOME`` comes from the password database, so the global configuration read
  is the account's own.
* **What is re-checked cannot change in between.** The configuration check
  runs again right before the command that acts, and the keys that could start
  a program in that window are pinned on the command line (`PINNED_CONFIG`,
  ``core.sshCommand`` set to the user's global value, hooks off where they are
  not wanted). Attributes come from the empty tree, so no ``.gitattributes``
  can switch on a filter. ``GIT_ALLOW_PROTOCOL`` limits transports whatever
  the configuration says. Validated directories are opened without following
  a symlink and git runs inside them by descriptor, so a directory swapped for
  a symlink after the checks cannot redirect it. Git itself still finds a
  repository's ``.git`` by name; its identity is re-checked, by name, right
  before the acting command, and a linked worktree's validated git directory
  is passed explicitly (``--git-dir``, ``--work-tree=.``) so its agent-writable
  ``.git`` file is never read again. That the git directory cannot be swapped
  in the moment between rests, like the next point, on the harness protecting
  it. A rewrite
  such as ``url.*.insteadOf`` cannot be
  pinned away; that it cannot appear while the confirmed command runs rests on
  the harness keeping ``.git/config`` write-protected, as Claude Code's sandbox
  does.
* **The destination is not addressable.** A push goes to a URL built from the
  policy's repository names, never to a remote the repository configures.
  Protected branches are refused whatever the policy says, and the upstream
  repository accepts only branches matching the policy's globs.
* **Nothing is lost silently.** A push always uses ``--force-with-lease`` with
  the full SHA the caller expects the remote branch to have (or ``new``), and
  a worktree moves with ``reset --keep`` only when it has no local changes;
  the previous commit is printed and stays in the reflog.
"""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import json
import os
import re
import stat
import subprocess
import sys
import tomllib
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .config import (
    OPERATOR_GIT_FILE,
    Config,
    ConfigError,
    _expand_home,
    account_home,
    approved_dir,
    describe,
    load,
)
from .layers import main_worktree
from .safe_read import TamperedPath, read_regular_file

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_POLICY = 3
EXIT_COMMAND = 4

PROG = "vetted-op-git"

#: A full object name. Short SHAs are refused: they can become ambiguous, and
#: the caller always has the full one from `git rev-parse` or the forge.
_SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
#: A branch name, before `git check-ref-format --branch` has its say.
_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/+-]{0,199}$")
#: The last component of a new worktree's path.
_WORKTREE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,99}$")
#: `owner/name`, as in `config._REPO`.
_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}/[A-Za-z0-9][A-Za-z0-9._-]{0,100}$")
_HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$")
#: A remote name: no `/` or `:`, so it can neither nest nor read as a URL.
_REMOTE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
#: Paths one `git-stage` call may name, at most.
MAX_STAGE_PATHS = 500
#: Longest commit message `git-commit` accepts, in characters.
MAX_COMMIT_MESSAGE = 20000

#: Branches no operation pushes to, whatever the policy adds or grants.
DEFAULT_PROTECTED = (
    "main",
    "master",
    "trunk",
    "develop",
    "gh-pages",
    "release",
    "release/*",
    "release-*",
    "v*-test",
    "v*-stable",
    "*-stable",
    "asf-site",
)

#: Repository-scope configuration keys that cannot make git run a program,
#: pick a credential, change a destination or transform file contents. Every
#: other key at `local` or `worktree` scope makes an operation refuse.
SAFE_LOCAL_KEY = re.compile(
    r"""^(?:
      core\.(?:repositoryformatversion|filemode|bare|logallrefupdates|ignorecase|precomposeunicode
              |symlinks|autocrlf|eol|safecrlf|quotepath|abbrev|commitgraph|untrackedcache
              |splitindex|multipackindex|sparsecheckout|sparsecheckoutcone|checkstat|trustctime)
    | extensions\.(?:worktreeconfig|objectformat|refstorage|preciousobjects|partialclone|noop)
    # A remote name without `:` or `/`: git applies the settings of a remote named exactly
    # like the URL a push goes to, so a URL-shaped name could redirect it.
    | remote\.[A-Za-z0-9._-]+\.(?:url|pushurl|fetch|tagopt|prune|prunetags|promisor|partialclonefilter
                         |mirror|skipdefaultupdate|skipfetchall|gh-resolved)
    | branch\.[^\x00]+\.(?:remote|pushremote|merge|rebase|description|vscode-merge-base)
    | user\.(?:name|email)
    | (?:pull|fetch)\.(?:rebase|ff|prune|prunetags|parallel|writecommitgraph)
    | push\.(?:default|autosetupremote|followtags)
    | rerere\.(?:enabled|autoupdate)
    | gc\.(?:auto|autopacklimit|autodetach|reflogexpire|reflogexpireunreachable|prunexpire|worktreepruneexpire)
    | maintenance\.(?:auto|strategy|repo)
    | index\.(?:version|threads|skiphash)
    | feature\.(?:manyfiles|experimental)
    | color\.[a-z.]+
    | advice\.[a-z]+
    | (?:commit|tag)\.gpgsign
    | init\.defaultbranch
    | merge\.conflictstyle
    | diff\.(?:renames|algorithm|colormoved)
    | log\.(?:date|decorate|follow)
    | status\.(?:showuntrackedfiles|submodulesummary)
    )$""",
    re.VERBOSE,
)


class GitRefused(ValueError):
    """A parameter or the repository state that the operation does not accept."""


class GitFailed(RuntimeError):
    """A git command that ran and failed."""

    def __init__(self, argv: Sequence[str], returncode: int, stderr: str, stdout: str = "") -> None:
        command = " ".join(a for a in argv if a != "-c" and "=" not in a)
        super().__init__(f"{command} exited {returncode}")
        self.returncode = returncode
        self.stderr = stderr
        #: A hook may explain its failure on stdout; it is shown with stderr.
        self.stdout = stdout


@dataclass(frozen=True)
class GitPolicy:
    """The validated ``[git]`` table of the policy."""

    #: Main checkouts (their top-level directories) the operations may act on,
    #: together with the linked worktrees that share their ``.git``.
    checkouts: tuple[Path, ...]
    upstream_repo: str
    fork_repo: str | None = None
    #: Globs of the branches a push may create or move on the upstream
    #: repository. Empty: no push to upstream at all.
    upstream_push: tuple[str, ...] = ()
    protected: tuple[str, ...] = DEFAULT_PROTECTED
    #: Directories new linked worktrees may be created in (directly).
    worktree_roots: tuple[Path, ...] = ()
    host: str = "github.com"
    transport: str = "ssh"
    #: The policy's workspace: commit messages, path lists and pull-request
    #: texts are read from files there only (see `ops.read_body`).
    workspace: Path | None = None
    #: The remote-tracking namespace `git-fetch` writes upstream branches to.
    upstream_remote: str = "upstream"
    #: The upstream branch a pull request opened by `git-pr-create` targets.
    pr_base: str = "main"

    def push_url(self, repo: str) -> str:
        if self.transport == "https":
            return f"https://{self.host}/{repo}.git"
        return f"git@{self.host}:{repo}.git"


def _absolute_real_dir(raw: object, key: str) -> Path:
    if not isinstance(raw, str) or not raw or not _expand_home(raw).is_absolute():
        raise ConfigError(f"[git] {key} entries must be absolute paths (or start with ~/), got {raw!r}")
    path = Path(os.path.abspath(_expand_home(raw)))
    if str(path) != os.path.realpath(path):
        raise ConfigError(
            f"[git] {key} entry {raw!r} must be an absolute path with no symlink on it "
            f"(its real location is {os.path.realpath(path)!r})"
        )
    return path


def _str_list(table: dict[str, object], key: str) -> list[str]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise ConfigError(f"[git] {key} must be a list of non-empty strings")
    return list(value)


#: Each operator's own ``[git]`` values live in `OPERATOR_GIT_FILE`, one table
#: per upstream repository (``["apache/airflow"]``), in the approved-policy
#: directory: outside every repository and every sandbox-writable root, so only
#: the operator puts them there, and a shared, committed policy never has to
#: name one person's paths.
#:
#: What an operator's table may set: where their clones, worktrees and fork are,
#: and how they reach the forge. The project-wide keys (``upstream_push``,
#: ``pr_base``, ``host``) stay in the shared policy, and ``protected`` only adds
#: branches to the policy's list.
OPERATOR_KEYS = frozenset(
    {"checkouts", "fork", "worktree_roots", "upstream_remote", "transport", "protected"}
)


def operator_git_path() -> Path:
    return approved_dir() / OPERATOR_GIT_FILE


def operator_git_table(upstream_repo: str) -> dict[str, object] | None:
    """The operator's table for ``upstream_repo``, or None when they declare none."""
    path = operator_git_path()
    try:
        data = read_regular_file(path)
    except TamperedPath as exc:
        raise ConfigError(str(exc)) from None
    if data is None:
        return None
    try:
        raw = tomllib.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from None
    table = raw.get(upstream_repo)
    if table is None:
        return None
    if not isinstance(table, dict):
        raise ConfigError(f'{path}: ["{upstream_repo}"] must be a table')
    unknown = sorted(set(table) - OPERATOR_KEYS)
    if unknown:
        raise ConfigError(
            f'{path}: ["{upstream_repo}"] may not set {", ".join(unknown)}; '
            "those are the project's, in the shared policy's [git] table"
        )
    return table


def operator_git_draft(upstream_repo: str, base: Path | None = None) -> str:
    """A ready-to-save ``["<upstream>"]`` table for the operator file, for a refusal to show.

    Filled from what is known without running anything: the main checkout of
    the working directory and the upstream's repository name. The fork stays a
    placeholder, since it is the operator's, not the repository's. Only keys in
    `OPERATOR_KEYS` appear, so the draft is always one the file accepts.
    """
    here = (base or Path.cwd()).resolve()
    checkout = main_worktree(here) or here
    name = upstream_repo.split("/", 1)[-1] if "/" in upstream_repo else checkout.name
    roots = Path(os.path.realpath(checkout.parent)) / f"{checkout.name}-worktrees"
    path = operator_git_path()
    return "\n".join(
        [
            "",
            f"Add your own values: append this table to {path}",
            "(create the worktree_roots directory first; no symlink may be on its path),",
            "with your fork filled in. Only you can write that file:",
            "",
            f'["{upstream_repo}"]',
            f'checkouts = ["{checkout}"]',
            f'fork = "<your-github-login>/{name}"',
            f'worktree_roots = ["{roots}"]',
            'upstream_remote = "upstream"',
        ]
    )


def _git_table(config: Config) -> dict[str, object]:
    """The shared policy's ``[git]`` table with the operator's own values over it."""
    project = config.git
    if project is not None and not isinstance(project, dict):
        raise ConfigError("[git] must be a table")
    operator = operator_git_table(config.upstream_repo)
    if project is None and operator is None:
        raise ConfigError(
            f"no [git] values for {config.upstream_repo}: the policy has no [git] table and "
            f'{operator_git_path()} has no ["{config.upstream_repo}"] table, so no git operation may run'
            + operator_git_draft(config.upstream_repo)
        )
    merged = dict(project or {})
    if operator is not None:
        protected = _str_list(merged, "protected") + _str_list(operator, "protected")
        merged.update(operator)
        merged["protected"] = protected
    return merged


def describe_git(config: Config, policy: GitPolicy) -> str:
    """The effective ``[git]`` values, each with the file it came from."""
    operator = operator_git_table(config.upstream_repo) or {}
    project = config.git if isinstance(config.git, dict) else {}

    def source(key: str) -> str:
        if key in operator:
            return str(operator_git_path())
        return "policy" if key in project else "default"

    values: list[tuple[str, object]] = [
        ("checkouts", [str(p) for p in policy.checkouts]),
        ("fork", policy.fork_repo),
        ("worktree_roots", [str(p) for p in policy.worktree_roots]),
        ("upstream_remote", policy.upstream_remote),
        ("transport", policy.transport),
        ("host", policy.host),
        ("upstream_push", list(policy.upstream_push)),
        ("pr_base", policy.pr_base),
    ]
    lines = ["[git] (effective)"]
    lines += [f"  {key} = {value!r}  # {source(key)}" for key, value in values]
    extra = [p for p in policy.protected if p not in DEFAULT_PROTECTED]
    origins = [
        s for s, table in ((str(operator_git_path()), operator), ("policy", project)) if "protected" in table
    ]
    lines.append(f"  protected += {extra!r}  # {', '.join(origins) or 'default'}")
    return "\n".join(lines)


def _owned_private_dir(path: Path, key: str) -> Path:
    """Refuse a directory another account owns or may write: worktrees there hold
    unpublished work and are where git later runs outside the sandbox."""
    try:
        st = os.stat(path)
    except FileNotFoundError:
        raise ConfigError(f"[git] {key} entry {str(path)!r} does not exist") from None
    if not stat.S_ISDIR(st.st_mode):
        raise ConfigError(f"[git] {key} entry {str(path)!r} is not a directory")
    if st.st_uid != os.getuid():
        raise ConfigError(f"[git] {key} entry {str(path)!r} is not owned by you")
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ConfigError(f"[git] {key} entry {str(path)!r} is writable by others (chmod go-w it)")
    return path


def git_policy(config: Config) -> GitPolicy:
    """Validate the ``[git]`` values; without any, every operation refuses."""
    table = _git_table(config)
    checkouts = tuple(_absolute_real_dir(raw, "checkouts") for raw in _str_list(table, "checkouts"))
    if not checkouts:
        raise ConfigError(
            "[git] checkouts must name at least one main checkout" + operator_git_draft(config.upstream_repo)
        )
    fork = table.get("fork")
    if fork is not None and (not isinstance(fork, str) or not _REPO.match(fork)):
        raise ConfigError(f"[git] fork must be an 'owner/name' string, got {fork!r}")
    host = table.get("host", "github.com")
    if not isinstance(host, str) or not _HOST.match(host):
        raise ConfigError(f"[git] host must be a host name, got {host!r}")
    transport = table.get("transport", "ssh")
    if transport not in ("ssh", "https"):
        raise ConfigError(f"[git] transport must be 'ssh' or 'https', got {transport!r}")
    upstream_remote = table.get("upstream_remote", "upstream")
    if not isinstance(upstream_remote, str) or not _REMOTE_NAME.match(upstream_remote):
        raise ConfigError(f"[git] upstream_remote must be a plain remote name, got {upstream_remote!r}")
    pr_base = table.get("pr_base", "main")
    if not isinstance(pr_base, str) or not _BRANCH.match(pr_base):
        raise ConfigError(f"[git] pr_base must be a branch name, got {pr_base!r}")
    return GitPolicy(
        checkouts=checkouts,
        upstream_repo=config.upstream_repo,
        fork_repo=fork,
        upstream_push=tuple(_str_list(table, "upstream_push")),
        protected=DEFAULT_PROTECTED + tuple(_str_list(table, "protected")),
        worktree_roots=tuple(
            _owned_private_dir(_absolute_real_dir(raw, "worktree_roots"), "worktree_roots")
            for raw in _str_list(table, "worktree_roots")
        ),
        host=host,
        transport=transport,
        workspace=config.workspace,
        upstream_remote=upstream_remote,
        pr_base=pr_base,
    )


# --- running git -----------------------------------------------------------


def clean_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    """The caller's environment, minus everything that would let it reconfigure git.

    Every ``GIT_*`` variable is dropped (``GIT_DIR``, ``GIT_SSH_COMMAND``,
    ``GIT_CONFIG_GLOBAL``, ``GIT_CONFIG_PARAMETERS``, …), and the global
    configuration is pinned to the account's own: ``HOME`` comes from the
    password database, never from the caller, and ``XDG_CONFIG_HOME`` is
    dropped, so a configuration written somewhere the agent can write is never
    read as the user's global one. What remains (``PATH``, ``SSH_AUTH_SOCK``,
    ``GNUPGHOME``, …) is what the user's own git and ssh setup needs.
    """
    source = os.environ if environ is None else environ
    env = {k: v for k, v in source.items() if not k.startswith("GIT_") and k != "XDG_CONFIG_HOME"}
    env["HOME"] = str(account_home())
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


#: Runs ``argv`` with ``env``, in the directory open as ``cwd_fd`` when one is given.
Runner = Callable[[list[str], dict[str, str], "int | None"], "subprocess.CompletedProcess[str]"]
#: Runs ``gh`` (``argv``) with ``env``, feeding ``stdin``.
GhRunner = Callable[[list[str], dict[str, str], str], "subprocess.CompletedProcess[str]"]


def _default_gh_runner(argv: list[str], env: dict[str, str], stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, check=False, capture_output=True, text=True, env=env, input=stdin)


def _default_runner(
    argv: list[str], env: dict[str, str], cwd_fd: int | None
) -> subprocess.CompletedProcess[str]:
    if cwd_fd is None:
        return subprocess.run(argv, check=False, capture_output=True, text=True, env=env)
    return subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        env=env,
        pass_fds=(cwd_fd,),
        preexec_fn=lambda: os.fchdir(cwd_fd),
    )


def open_dir(path: Path) -> int:
    """Open ``path`` as a directory, refusing a symlink at any component.

    Walked one component at a time from ``/`` with ``O_NOFOLLOW``, so the
    descriptor is the directory the name led to when it was checked. Git then
    runs *in* that descriptor rather than at the name, and swapping a directory
    on the path for a symlink afterwards (the agent can write inside a
    checkout) cannot send git somewhere else.
    """
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
    except OSError as exc:
        os.close(fd)
        raise GitRefused(
            f"{str(path)!r} is not a directory reachable without a symlink: {exc.strerror}"
        ) from None
    return fd


#: Pinned on every call, so a key the repository's configuration gains between
#: `check_repository_config` and the command cannot take effect: no file-system
#: monitor program, no automatic gc or maintenance (their hooks are commands),
#: and only network transports (a local path would run that repository's
#: receive-pack and hooks here). The same pins as the local tracker's git.
PINNED_CONFIG = ("core.fsmonitor=false", "gc.auto=0", "maintenance.auto=false", "protocol.allow=never")

#: The first git that honours ``GIT_ATTR_SOURCE``.
MIN_GIT_VERSION = (2, 42)

#: The empty tree, per object format: attributes are read from it, so no
#: `.gitattributes` in the working tree can switch on a filter or driver.
EMPTY_TREE = {
    "sha1": "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
    "sha256": "6ef19b41225c5369f1c104d45d8d85efa9b057b53b14b4b9b939dd74decc5321",
}


@dataclass
class Git:
    """Runs git with the pins above; injectable for tests."""

    runner: Runner = field(default=_default_runner)
    #: Runs ``gh`` for `git-pr-create`; injectable for tests.
    gh_runner: GhRunner = field(default=_default_gh_runner)
    #: Transports a push may use. Tests add ``file``; production cannot.
    protocols: tuple[str, ...] = ("https", "ssh")
    #: The user's global ``core.sshCommand`` (or plain ``ssh``), pinned on every
    #: call so the repository's configuration cannot replace it.
    _ssh_command: str | None = field(default=None, repr=False)
    #: Set once the object format is known (see `check_repository_config`).
    attr_source: str | None = None
    #: Validated directories, open (see `open_dir`); git runs in these, never at the name.
    anchors: dict[Path, int] = field(default_factory=dict)
    #: Validated working tree -> its git directory. Git gets these explicitly
    #: (``--git-dir``, ``--work-tree=.``) and never reads the ``.git`` file of a
    #: linked worktree again: that file is in the tree the agent can write.
    git_dirs: dict[Path, Path] = field(default_factory=dict)

    def anchor(self, path: Path, fd: int | None = None) -> int:
        """Return the open descriptor for ``path``, opening it on first use.

        Takes ownership of a passed ``fd``: it is kept until `close`, or closed
        at once when ``path`` already has a descriptor.
        """
        if path in self.anchors:
            if fd is not None and fd != self.anchors[path]:
                os.close(fd)
        else:
            self.anchors[path] = open_dir(path) if fd is None else fd
        return self.anchors[path]

    def close(self) -> None:
        for fd in self.anchors.values():
            os.close(fd)
        self.anchors.clear()

    def check_version(self) -> None:
        """Refuse a git older than `MIN_GIT_VERSION`, which ignores ``GIT_ATTR_SOURCE``."""
        found = self.runner(["git", "version"], clean_env(), None)
        match = re.search(r"(\d+)\.(\d+)", found.stdout or "")
        version = (int(match.group(1)), int(match.group(2))) if match else (0, 0)
        if found.returncode != 0 or version < MIN_GIT_VERSION:
            raise GitRefused(
                f"git {'.'.join(map(str, MIN_GIT_VERSION))} or later is required (found "
                f"{(found.stdout or '').strip() or 'none'}): an older git ignores GIT_ATTR_SOURCE, so a "
                ".gitattributes could switch on a filter outside the sandbox"
            )

    def ssh_command(self) -> str:
        if self._ssh_command is None:
            argv = ["git", "config", "--global", "--get", "core.sshCommand"]
            found = self.runner(argv, clean_env(), None)
            value = found.stdout.strip() if found.returncode == 0 else ""
            self._ssh_command = value if value and "\n" not in value else "ssh"
        return self._ssh_command

    def argv(self, directory: Path, *args: str, hooks: bool = False) -> list[str]:
        """A git command in ``directory``, with hooks switched off unless ``hooks``.

        An anchored directory is entered by descriptor (see `open_dir`), so the
        argv names it only when it is not anchored (dry runs print the name).
        """
        pins = [*PINNED_CONFIG, *(f"protocol.{p}.allow=always" for p in self.protocols)]
        pins.append(f"core.sshCommand={self.ssh_command()}")
        if not hooks:
            pins.append("core.hooksPath=/dev/null")
        where = [] if directory in self.anchors else ["-C", str(directory)]
        if directory in self.git_dirs:
            where += [f"--git-dir={self.git_dirs[directory]}", "--work-tree=."]
        return ["git", *(arg for pin in pins for arg in ("-c", pin)), *where, *args]

    def _env(self) -> dict[str, str]:
        env = clean_env()
        # Overrides every protocol.* setting, the repository's included.
        env["GIT_ALLOW_PROTOCOL"] = ":".join(self.protocols)
        if self.attr_source is not None:
            env["GIT_ATTR_SOURCE"] = self.attr_source
        return env

    def _call(
        self, directory: Path, *args: str, hooks: bool = False
    ) -> tuple[list[str], subprocess.CompletedProcess[str]]:
        argv = self.argv(directory, *args, hooks=hooks)
        return argv, self.runner(argv, self._env(), self.anchors.get(directory))

    def run(self, directory: Path, *args: str, hooks: bool = False) -> str:
        argv, completed = self._call(directory, *args, hooks=hooks)
        if completed.returncode != 0:
            raise GitFailed(argv, completed.returncode, completed.stderr or "", completed.stdout or "")
        return completed.stdout

    def ok(self, directory: Path, *args: str) -> bool:
        return self._call(directory, *args)[1].returncode == 0


# --- validation ------------------------------------------------------------


def _param(raw: str, name: str) -> str:
    if not raw or raw.startswith("-") or "\x00" in raw or "\n" in raw:
        raise GitRefused(f"parameter {name!r} may not be empty, start with '-' or span lines: {raw!r}")
    return raw


def sha(raw: str, name: str) -> str:
    if not _SHA.match(_param(raw, name)):
        raise GitRefused(f"{name} must be a full lowercase commit SHA, got {raw!r}")
    return raw


def branch_name(git: Git, directory: Path, raw: str, name: str) -> str:
    _param(raw, name)
    if not _BRANCH.match(raw) or ".." in raw or raw.endswith((".lock", "/", ".")):
        raise GitRefused(f"{name} is not an acceptable branch name: {raw!r}")
    if not git.ok(directory, "check-ref-format", "--branch", raw):
        raise GitRefused(f"{name} is not a valid branch name: {raw!r}")
    return raw


def is_protected(branch: str, policy: GitPolicy) -> bool:
    return any(fnmatch.fnmatchcase(branch, glob) for glob in policy.protected)


def _absolute(raw: str, name: str) -> Path:
    expanded = _expand_home(_param(raw, name))
    if not expanded.is_absolute():
        raise GitRefused(f"{name} must be an absolute path (or start with ~/), got {raw!r}")
    return Path(os.path.abspath(expanded))


def _real_dir(raw: str, name: str) -> Path:
    path = _absolute(raw, name)
    if str(path) != os.path.realpath(path):
        raise GitRefused(f"{name} {raw!r} has a symlink on its path; name its real location")
    return path


@dataclass(frozen=True)
class Worktree:
    """A working tree of one of the policy's checkouts."""

    path: Path
    checkout: Path
    #: (device, inode) of the checkout's `.git` directory when it was validated.
    git_dir_id: tuple[int, int] = (0, 0)
    #: The worktree's own git directory: `.git` for the main checkout, the
    #: registered `.git/worktrees/<name>` for a linked one.
    git_dir: Path = Path("/nonexistent")

    @property
    def linked(self) -> bool:
        return self.path != self.checkout


def resolve_worktree(git: Git, raw: str, policy: GitPolicy, name: str = "worktree") -> Worktree:
    """The working tree at ``raw``, if it is a policy checkout or one of its linked worktrees."""
    path = _real_dir(raw, name)
    if not path.is_dir():
        raise GitRefused(f"{name} {str(path)!r} is not a directory")
    git.anchor(path)
    lines = git.run(path, "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-common-dir")
    top, common = (Path(os.path.realpath(line)) for line in lines.splitlines()[:2])
    if top != path:
        raise GitRefused(f"{name} {str(path)!r} is not the top of a working tree (that is {str(top)!r})")
    for checkout in policy.checkouts:
        if common == checkout / ".git" and (checkout / ".git").is_dir():
            git.anchor(checkout)
            worktree = Worktree(path=path, checkout=checkout, git_dir_id=git_dir_identity(checkout))
            worktree = _check_registered(git, worktree, name)
            git.git_dirs[path] = worktree.git_dir
            git.git_dirs.setdefault(checkout, checkout / ".git")
            return worktree
    allowed = ", ".join(str(c) for c in policy.checkouts)
    raise GitRefused(f"{name} {str(path)!r} does not belong to a checkout the policy names ({allowed})")


def git_dir_identity(checkout: Path) -> tuple[int, int]:
    """The checkout's `.git`, looked up by name now, with no symlink anywhere on the way.

    Looked up afresh each time rather than through an anchor, so a directory
    swapped anywhere on the path since the last look shows as a different one.
    """
    fd = open_dir(checkout)
    try:
        found = os.stat(".git", dir_fd=fd, follow_symlinks=False)
    except OSError as exc:
        raise GitRefused(f"cannot read {str(checkout / '.git')!r}: {exc.strerror}") from None
    finally:
        os.close(fd)
    if not stat.S_ISDIR(found.st_mode):
        raise GitRefused(f"{str(checkout / '.git')!r} is not a directory")
    return (found.st_dev, found.st_ino)


def _check_registered(git: Git, worktree: Worktree, name: str) -> Worktree:
    """A linked worktree must be one git registered for this path, not a copy pointing at `.git`."""
    git_dir = Path(os.path.realpath(git.run(worktree.path, "rev-parse", "--absolute-git-dir").strip()))
    main = worktree.checkout / ".git"
    if not worktree.linked:
        if git_dir != main:
            raise GitRefused(f"{name} {str(worktree.path)!r} does not use {str(main)!r} as its git directory")
        return dataclasses.replace(worktree, git_dir=main)
    if git_dir.parent != main / "worktrees":
        raise GitRefused(
            f"{name} {str(worktree.path)!r} is not a linked worktree registered with {str(main)!r}"
        )
    try:
        registered = (git_dir / "gitdir").read_text().strip()
    except OSError:
        registered = ""
    if Path(os.path.realpath(registered)) != worktree.path / ".git":
        raise GitRefused(f"{name} {str(worktree.path)!r} is not where git registered {git_dir.name!r}")
    return dataclasses.replace(worktree, git_dir=git_dir)


def parse_config_scopes(output: str) -> list[tuple[str, str]]:
    """``git config --list --show-scope --name-only -z`` output as (scope, key) pairs."""
    items = [item for item in output.split("\x00") if item]
    pairs: list[tuple[str, str]] = []
    pending: str | None = None
    for item in items:
        if "\t" in item:
            scope, key = item.split("\t", 1)
            pairs.append((scope, key))
        elif pending is None:
            pending = item
        else:
            pairs.append((pending, item))
            pending = None
    return pairs


def check_repository_config(git: Git, worktree: Worktree) -> None:
    """Refuse a repository whose own configuration holds a key outside `SAFE_LOCAL_KEY`.

    Checked in every working tree an operation runs git in (a linked worktree
    has its own ``config.worktree``), and again right before the command that
    acts, so a key added after the first check is still caught; what cannot
    be re-checked in between is pinned by `PINNED_CONFIG`.
    """
    git.check_version()
    if git_dir_identity(worktree.checkout) != worktree.git_dir_id:
        raise GitRefused(f"{str(worktree.checkout / '.git')!r} changed since it was validated")
    # A linked worktree's common directory comes from its `commondir` file, which
    # can be rewritten after `resolve_worktree` looked: ask git again, through the
    # same pinned git directory the command will use, and require the same answer.
    lines = git.run(
        worktree.path, "rev-parse", "--path-format=absolute", "--git-common-dir", "--absolute-git-dir"
    )
    common, git_dir = (Path(os.path.realpath(line)) for line in lines.splitlines()[:2])
    if common != worktree.checkout / ".git":
        raise GitRefused(
            f"the common git directory of {str(worktree.path)!r} is now {str(common)!r}, "
            f"not {str(worktree.checkout / '.git')!r}"
        )
    if git_dir != worktree.git_dir:
        raise GitRefused(f"the git directory of {str(worktree.path)!r} changed since it was validated")
    for directory in dict.fromkeys((worktree.path, worktree.checkout)):
        _check_config_in(git, directory)
    object_format = git.run(worktree.path, "rev-parse", "--show-object-format").strip()
    if object_format not in EMPTY_TREE:
        raise GitRefused(f"unsupported object format {object_format!r}")
    git.attr_source = EMPTY_TREE[object_format]


def _check_config_in(git: Git, directory: Path) -> None:
    output = git.run(directory, "config", "--list", "--show-scope", "--name-only", "--includes", "-z")
    unsafe = sorted(
        {
            key
            for scope, key in parse_config_scopes(output)
            # `command` scope is this module's own `-c` pins; `GIT_CONFIG_*` is dropped.
            if scope in ("local", "worktree") and not SAFE_LOCAL_KEY.match(key.lower())
        }
    )
    if unsafe:
        raise GitRefused(
            f"the repository configuration of {str(directory)!r} sets {', '.join(unsafe)}; "
            "git runs outside the sandbox here, so only inert repository settings are accepted. "
            "Move those settings to your global git configuration, or remove them, and retry"
        )


def resolve_commit(git: Git, directory: Path, commit: str, name: str) -> str:
    if not git.ok(directory, "cat-file", "-e", f"{commit}^{{commit}}"):
        raise GitRefused(f"{name} {commit} is not a commit in this repository")
    return commit


# --- operations ------------------------------------------------------------


@dataclass(frozen=True)
class GitOp:
    name: str
    params: tuple[str, ...]
    summary: str
    run: Callable[[Git, GitPolicy, dict[str, str], bool], str]


def _refuse_empty_branch(git: Git, worktree: Worktree, commit: str, local: str) -> None:
    """The agent-guard `empty-rebase` rule, for the push this dispatcher runs.

    Moving an existing branch to a commit with nothing over a default branch
    (a rebase that dropped every commit) closes the pull request it heads and
    revokes maintainers' push access to it. The bases are the remotes' default
    branches (`refs/remotes/*/HEAD`); with none known, nothing is refused, as
    in the guard. There is no override: closing a pull request is not a push.
    """
    heads = git.run(worktree.path, "for-each-ref", "--format=%(symref)", "refs/remotes/*/HEAD")
    for base in sorted({line for line in heads.splitlines() if line}):
        if git.run(worktree.path, "rev-list", "--count", f"{base}..{commit}").strip() == "0":
            raise GitRefused(
                f"{local!r} has no commits over {base.removeprefix('refs/remotes/')}; force-pushing it "
                "would empty the branch, which closes a pull request it heads. Check the rebase result"
            )


def push_branch(git: Git, policy: GitPolicy, p: dict[str, str], dry_run: bool) -> str:
    """Push a local branch's commit to the fork or upstream, with a lease on the expected SHA."""
    worktree = resolve_worktree(git, p["checkout"], policy, "checkout")
    check_repository_config(git, worktree)
    local = branch_name(git, worktree.path, p["branch"], "branch")
    remote_branch = branch_name(git, worktree.path, p["remote_branch"], "remote_branch")
    if is_protected(remote_branch, policy):
        raise GitRefused(f"{remote_branch!r} is a protected branch; no operation pushes to it")
    target = _param(p["target"], "target")
    if target == "fork":
        if policy.fork_repo is None:
            raise GitRefused("the policy names no [git] fork, so nothing may be pushed to one")
        repo = policy.fork_repo
    elif target == "upstream":
        if not any(fnmatch.fnmatchcase(remote_branch, glob) for glob in policy.upstream_push):
            raise GitRefused(
                f"{remote_branch!r} matches no [git] upstream_push glob "
                f"({', '.join(policy.upstream_push) or 'none declared'}), so it may not be pushed upstream"
            )
        repo = policy.upstream_repo
    else:
        raise GitRefused(f"target must be 'fork' or 'upstream', got {target!r}")
    expected = p["expected"]
    lease = "" if expected == "new" else sha(expected, "expected")
    if not git.ok(worktree.path, "show-ref", "--verify", "--quiet", f"refs/heads/{local}"):
        raise GitRefused(f"there is no local branch {local!r}")
    commit = git.run(worktree.path, "rev-parse", "--verify", f"refs/heads/{local}^{{commit}}").strip()
    if lease:
        _refuse_empty_branch(git, worktree, commit, local)
    args = [
        "push",
        # The pre-push checks run in the sandbox before this call (see the module
        # docstring): a hook here would run working-tree code outside it.
        "--no-verify",
        # Only the one ref: `push.followTags` would also publish reachable tags.
        "--no-follow-tags",
        "--porcelain",
        f"--force-with-lease=refs/heads/{remote_branch}:{lease}",
        policy.push_url(repo),
        f"{commit}:refs/heads/{remote_branch}",
    ]
    if dry_run:
        return " ".join(git.argv(worktree.path, *args))
    check_repository_config(git, worktree)
    git.run(worktree.path, *args)
    was = "created" if not lease else f"was {lease}"
    return f"pushed {commit} to {repo} {remote_branch} ({was})"


def worktree_sync(git: Git, policy: GitPolicy, p: dict[str, str], dry_run: bool) -> str:
    """Move a clean linked worktree's branch to a commit (``reset --keep``)."""
    worktree = resolve_worktree(git, p["worktree"], policy)
    if not worktree.linked:
        raise GitRefused("worktree-sync moves linked worktrees only; this is the main checkout")
    check_repository_config(git, worktree)
    commit = resolve_commit(git, worktree.path, sha(p["commit"], "commit"), "commit")
    if not git.ok(worktree.path, "symbolic-ref", "--quiet", "HEAD"):
        raise GitRefused(f"{str(worktree.path)!r} has a detached HEAD; check out its branch first")
    branch = git.run(worktree.path, "symbolic-ref", "--short", "HEAD").strip()
    if git.run(worktree.path, "status", "--porcelain", "--untracked-files=no").strip():
        raise GitRefused(f"{str(worktree.path)!r} has uncommitted changes; commit or set them aside first")
    previous = git.run(worktree.path, "rev-parse", "HEAD").strip()
    args = ["reset", "--keep", commit]
    if dry_run:
        return " ".join(git.argv(worktree.path, *args))
    check_repository_config(git, worktree)
    git.run(worktree.path, *args)
    return f"moved {branch} in {worktree.path} from {previous} to {commit}"


def worktree_add(git: Git, policy: GitPolicy, p: dict[str, str], dry_run: bool) -> str:
    """Create a linked worktree on a new branch, inside a policy worktree root."""
    checkout = resolve_worktree(git, p["checkout"], policy, "checkout")
    if checkout.linked:
        raise GitRefused("checkout must be the main checkout, not a linked worktree")
    check_repository_config(git, checkout)
    path = _absolute(p["path"], "path")
    if not _WORKTREE_NAME.match(path.name):
        raise GitRefused(f"the new worktree's directory name is not acceptable: {path.name!r}")
    if not any(
        path.parent == root and str(root) == os.path.realpath(path.parent) for root in policy.worktree_roots
    ):
        roots = ", ".join(str(r) for r in policy.worktree_roots) or "none declared"
        raise GitRefused(f"{str(path)!r} is not directly inside a [git] worktree_roots directory ({roots})")
    if os.path.lexists(path):
        raise GitRefused(f"{str(path)!r} already exists")
    branch = branch_name(git, checkout.path, p["branch"], "branch")
    if git.ok(checkout.path, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"):
        raise GitRefused(f"branch {branch!r} already exists; worktree-add creates a new one")
    start = resolve_commit(git, checkout.path, sha(p["start"], "start"), "start")
    if dry_run:
        return " ".join(git.argv(checkout.path, "worktree", "add", "-b", branch, str(path), start))
    check_repository_config(git, checkout)
    # Created through the root's descriptor and entered by descriptor, then
    # added as `.`: a root swapped for a symlink after the checks above still
    # cannot make git write anywhere but this new, empty directory. (Git names
    # its administrative directory after the path given, so it is `-` here.)
    root_fd = open_dir(path.parent)
    try:
        os.mkdir(path.name, 0o777, dir_fd=root_fd)
        new_fd = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        git.anchor(path, new_fd)
        try:
            git.run(
                path, f"--git-dir={checkout.checkout / '.git'}", "worktree", "add", "-b", branch, ".", start
            )
        except GitFailed:
            os.rmdir(path.name, dir_fd=root_fd)
            raise
    finally:
        os.close(root_fd)
    return f"created {path} on new branch {branch} at {start}"


def worktree_remove(git: Git, policy: GitPolicy, p: dict[str, str], dry_run: bool) -> str:
    """Remove a linked worktree that has no changes (never ``--force``)."""
    worktree = resolve_worktree(git, p["worktree"], policy)
    if not worktree.linked:
        raise GitRefused("worktree-remove removes linked worktrees only; this is the main checkout")
    check_repository_config(git, worktree)
    args = ["worktree", "remove", str(worktree.path)]
    if dry_run:
        return " ".join(git.argv(worktree.checkout, *args))
    # Without --force git itself refuses a worktree with modified or untracked files.
    check_repository_config(git, worktree)
    git.run(worktree.checkout, *args)
    return f"removed {worktree.path}"


def _workspace_text(policy: GitPolicy, value: str, what: str) -> str:
    """A UTF-8 text file read from the policy's workspace (see `ops.read_body`)."""
    from .ops import ParamError, read_body

    if policy.workspace is None:
        raise GitRefused(f"the policy names no workspace, so no {what} file can be read")
    try:
        data = read_body(_param(value, what), workspace=policy.workspace)
    except ParamError as exc:
        raise GitRefused(str(exc)) from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise GitRefused(f"the {what} file is not UTF-8 text") from None
    if "\x00" in text:
        raise GitRefused(f"the {what} file holds a NUL character")
    return text


def _stage_paths(worktree: Worktree, text: str) -> list[str]:
    """The paths of a `git-stage` list: relative, inside the worktree, one per line."""
    paths = [line for line in (raw.strip() for raw in text.splitlines()) if line]
    if not paths:
        raise GitRefused("the path list is empty")
    if len(paths) > MAX_STAGE_PATHS:
        raise GitRefused(f"the path list names {len(paths)} paths; at most {MAX_STAGE_PATHS} per call")
    for path in paths:
        parts = Path(path).parts
        if path.startswith(("-", "/", ":")) or ".." in parts or ".git" in parts:
            raise GitRefused(
                f"{path!r} is not a plain relative path inside the worktree "
                "(no leading '-', '/' or ':', no '..', nothing under .git)"
            )
        resolved = os.path.abspath(worktree.path / path)
        if os.path.commonpath([str(worktree.path), resolved]) != str(worktree.path):
            raise GitRefused(f"{path!r} resolves outside {str(worktree.path)!r}")
    return paths


def stage_paths(git: Git, policy: GitPolicy, p: dict[str, str], dry_run: bool) -> str:
    """Stage exactly the paths listed in a workspace file (``git add`` with literal pathspecs)."""
    worktree = resolve_worktree(git, p["worktree"], policy)
    check_repository_config(git, worktree)
    paths = _stage_paths(worktree, _workspace_text(policy, p["paths_file"], "paths_file"))
    # Literal pathspecs: no glob or `:(magic)` in a listed path widens what is staged.
    # Attributes come from the empty tree (`check_repository_config`), so no
    # `.gitattributes` in the working tree can switch on a clean filter.
    args = ["--literal-pathspecs", "add", "--", *paths]
    if dry_run:
        return " ".join(git.argv(worktree.path, *args))
    check_repository_config(git, worktree)
    git.run(worktree.path, *args)
    return f"staged {len(paths)} path(s) in {worktree.path}"


def _require_checked(git: Git, policy: GitPolicy, worktree: Worktree) -> None:
    """Refuse a staged change whose content the sandboxed checks did not pass.

    `vetted-op-checks` records, per path, the content it checked; every staged
    path must be in that record with the same content. The record sits in the
    workspace, which sandboxed commands can write, so this keeps an agent
    honest the way CI does; it is not a proof against one forging it.
    """
    from .checks import DELETED, stamp_path
    from .checks import PROG as CHECKS

    assert policy.workspace is not None  # the message file was read from it
    hint = f"run `{CHECKS} {worktree.path} <workspace>/<paths_file>` in the sandbox, then stage again"
    path = stamp_path(policy.workspace, worktree.path)
    try:
        data = read_regular_file(path)
    except (OSError, TamperedPath) as exc:
        raise GitRefused(f"the checks record {str(path)!r} cannot be read ({exc}): {hint}") from None
    if data is None:
        raise GitRefused(f"no checks were recorded for {str(worktree.path)!r}: {hint}")
    try:
        record = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise GitRefused(f"the checks record {str(path)!r} is not valid JSON: {hint}") from None
    files = record.get("files") if isinstance(record, dict) else None
    if not isinstance(files, dict):
        raise GitRefused(f"the checks record {str(path)!r} lists no files: {hint}")
    staged = [
        p
        for p in git.run(worktree.path, "diff", "--cached", "--name-only", "--no-renames", "-z").split("\0")
        if p
    ]
    unchecked = []
    for staged_path in staged:
        entry = git.run(worktree.path, "--literal-pathspecs", "ls-files", "--stage", "-z", "--", staged_path)
        blob = entry.split()[1] if entry.strip("\0").strip() else DELETED
        if files.get(staged_path) != blob:
            unchecked.append(staged_path)
    if unchecked:
        shown = ", ".join(unchecked[:10]) + (" …" if len(unchecked) > 10 else "")
        raise GitRefused(f"the checks did not pass these staged paths as they are now: {shown}; {hint}")


def commit_staged(git: Git, policy: GitPolicy, p: dict[str, str], dry_run: bool) -> str:
    """Commit what is staged, with a message from a workspace file, signed per the user's own config."""
    worktree = resolve_worktree(git, p["worktree"], policy)
    check_repository_config(git, worktree)
    message = _workspace_text(policy, p["message_file"], "message_file").strip()
    if not message:
        raise GitRefused("the commit message is empty")
    if len(message) > MAX_COMMIT_MESSAGE:
        raise GitRefused(f"the commit message is longer than {MAX_COMMIT_MESSAGE} characters")
    if not git.ok(worktree.path, "symbolic-ref", "--quiet", "HEAD"):
        raise GitRefused(f"{str(worktree.path)!r} has a detached HEAD; check out a branch first")
    branch = git.run(worktree.path, "symbolic-ref", "--short", "HEAD").strip()
    if is_protected(branch, policy):
        raise GitRefused(f"{branch!r} is a protected branch; commit on a topic branch")
    if git.ok(worktree.path, "diff", "--cached", "--quiet"):
        raise GitRefused("nothing is staged; stage the change first (git-stage)")
    _require_checked(git, policy, worktree)
    # No hook runs (`core.hooksPath=/dev/null`, `--no-verify`): the pre-commit
    # checks are working-tree code, so `vetted-op-checks` runs them in the
    # sandbox before this call, and `_require_checked` refuses a staged change
    # they did not pass. Signing follows the user's global git configuration,
    # which is theirs; the repository's cannot change it.
    args = ["commit", "--no-verify", "--cleanup=strip", "-m", message]
    if dry_run:
        return " ".join(git.argv(worktree.path, *args[:-1], "<message from message_file>"))
    check_repository_config(git, worktree)
    git.run(worktree.path, *args)
    commit = git.run(worktree.path, "rev-parse", "HEAD").strip()
    return f"committed {commit} on {branch} in {worktree.path}"


def fetch_upstream(git: Git, policy: GitPolicy, p: dict[str, str], dry_run: bool) -> str:
    """Fetch one upstream branch into ``refs/remotes/<upstream_remote>/<branch>``."""
    worktree = resolve_worktree(git, p["checkout"], policy, "checkout")
    check_repository_config(git, worktree)
    branch = branch_name(git, worktree.path, p["branch"], "branch")
    # The URL comes from the policy, never from a remote the repository configures.
    ref = f"refs/remotes/{policy.upstream_remote}/{branch}"
    args = [
        "fetch",
        "--no-tags",
        "--no-recurse-submodules",
        "--no-write-fetch-head",
        policy.push_url(policy.upstream_repo),
        f"+refs/heads/{branch}:{ref}",
    ]
    if dry_run:
        return " ".join(git.argv(worktree.path, *args))
    check_repository_config(git, worktree)
    git.run(worktree.path, *args)
    head = git.run(worktree.path, "rev-parse", ref).strip()
    return f"fetched {policy.upstream_repo} {branch} into {ref} at {head}"


def _forbidden_hits(text: str) -> list[str]:
    from .forbidden_terms import DEFAULT_TERMS

    return [label for label, pattern in DEFAULT_TERMS if re.search(pattern, text, re.IGNORECASE)]


def pr_create(git: Git, policy: GitPolicy, p: dict[str, str], dry_run: bool) -> str:
    """Open a pull request from ``<fork>:<branch>`` against the policy's ``pr_base`` upstream."""
    if policy.fork_repo is None:
        raise GitRefused("the policy names no [git] fork, so no pull request can be opened from one")
    worktree = resolve_worktree(git, p["checkout"], policy, "checkout")
    check_repository_config(git, worktree)
    branch = branch_name(git, worktree.path, p["branch"], "branch")
    if is_protected(branch, policy):
        raise GitRefused(f"{branch!r} is a protected branch; open pull requests from a topic branch")
    # The title travels on the command line, not in a file, so the confirmation
    # the user approves shows exactly the title that will be published.
    title = _param(p["title"], "title").strip()
    if not title or len(title) > 256 or any(unicodedata.category(c).startswith("C") for c in title):
        raise GitRefused("the title must be one line of 1 to 256 printable characters")
    body = _workspace_text(policy, p["body_file"], "body_file")
    # A pull request is public. The same terms the publication guard refuses in
    # any public text are refused here, so a security detail cannot reach the
    # upstream repository through a file the guard does not read.
    hits = sorted(set(_forbidden_hits(title) + _forbidden_hits(body)))
    if hits:
        raise GitRefused(
            "the pull request text contains terms that are never published before disclosure: "
            f"{', '.join(hits)}; describe the change in neutral functional terms"
        )
    head = f"{policy.fork_repo.split('/', 1)[0]}:{branch}"
    argv = [
        "gh",
        "api",
        "--hostname",
        policy.host,
        "--method",
        "POST",
        f"repos/{policy.upstream_repo}/pulls",
        "-f",
        f"head={head}",
        "-f",
        f"base={policy.pr_base}",
        "-f",
        f"title={title}",
        "-F",
        "body=@-",
        "--jq",
        ".html_url",
    ]
    if dry_run:
        return " ".join([*argv[:-4], "-F", "body=@<body_file>", *argv[-2:]])
    completed = git.gh_runner(argv, clean_env(), body)
    if completed.returncode != 0:
        raise GitFailed(argv[:7], completed.returncode, completed.stderr or "", completed.stdout or "")
    return f"opened {completed.stdout.strip()} ({head} -> {policy.upstream_repo} {policy.pr_base})"


OPS: dict[str, GitOp] = {
    op.name: op
    for op in (
        GitOp(
            "git-push-branch",
            ("checkout", "branch", "target", "remote_branch", "expected"),
            "push local <branch> to <remote_branch> of the fork or upstream; <expected> is the "
            "remote branch's current full SHA, or 'new'. No hook runs: run the pre-push checks "
            "in the sandbox first",
            push_branch,
        ),
        GitOp(
            "git-worktree-sync",
            ("worktree", "commit"),
            "move a clean linked worktree's branch to <commit> (reset --keep)",
            worktree_sync,
        ),
        GitOp(
            "git-worktree-add",
            ("checkout", "path", "branch", "start"),
            "create a linked worktree at <path> on a new <branch> starting at <start>",
            worktree_add,
        ),
        GitOp(
            "git-worktree-remove",
            ("worktree",),
            "remove a linked worktree that has no changes",
            worktree_remove,
        ),
        GitOp(
            "git-stage",
            ("worktree", "paths_file"),
            "stage exactly the relative paths listed, one per line, in <paths_file> (a workspace "
            "file); literal pathspecs, nothing outside the worktree",
            stage_paths,
        ),
        GitOp(
            "git-commit",
            ("worktree", "message_file"),
            "commit what is staged on the current (non-protected) branch, message from <message_file> "
            "(a workspace file), signed per the user's global git config. No hook runs out here: "
            "refused unless `vetted-op-checks` passed every staged path, as it is now, in the sandbox",
            commit_staged,
        ),
        GitOp(
            "git-fetch",
            ("checkout", "branch"),
            "fetch upstream <branch> into refs/remotes/<upstream_remote>/<branch>, from the policy's "
            "upstream URL",
            fetch_upstream,
        ),
        GitOp(
            "git-pr-create",
            ("checkout", "branch", "title", "body_file"),
            "open a pull request from <fork>:<branch> against the upstream's pr_base; <title> on the "
            "command line (so the confirmation shows it), body from a workspace file; refused if "
            "either holds a never-publish term",
            pr_create,
        ),
    )
}


def main(argv: list[str] | None = None, *, git: Git | None = None) -> int:
    """The ``vetted-op-git`` console script."""
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Run one fixed, policy-scoped git operation outside the sandbox. No pass-through arguments.",
    )
    parser.add_argument("--caller", help="the skill or plugin invoking this operation")
    parser.add_argument("--dry-run", action="store_true", help="validate, print the git command, run nothing")
    parser.add_argument("operation", nargs="?", help="operation name, or 'list-ops' / 'policy'")
    parser.add_argument("params", nargs="*", help="operation parameters, positionally")
    args = parser.parse_args(raw)

    if args.operation in (None, "list-ops"):
        for name, entry in sorted(OPS.items()):
            print(f"write  {name:<22} {' '.join(entry.params)}\n        {entry.summary}")
        return EXIT_OK

    if sum(1 for a in raw if a == "--caller" or a.startswith("--caller=")) > 1:
        print(f"{PROG}: refused: --caller given more than once", file=sys.stderr)
        return EXIT_POLICY

    # Like every entry point that runs outside the sandbox: only a policy the user
    # placed in the approved directory themselves drives git. A dry run against
    # one that is not approved yet still checks its parameters, but runs no git
    # command at all: even read-only git, out here, is steered by that policy.
    approved = True
    try:
        try:
            config = load(approved_only=args.operation != "policy")
        except ConfigError:
            if not args.dry_run:
                raise
            config = load(approved_only=False)
            approved = False
        policy = git_policy(config)
    except ConfigError as exc:
        print(f"{PROG}: config error: {exc}", file=sys.stderr)
        return EXIT_POLICY

    if args.operation == "policy":
        print(describe(config))
        print(describe_git(config, policy))
        return EXIT_OK

    if not args.caller:
        print(f"{PROG}: --caller is required for any operation", file=sys.stderr)
        return EXIT_USAGE

    op = OPS.get(args.operation)
    try:
        if op is None:
            raise GitRefused(f"unknown operation {args.operation!r}; see '{PROG} list-ops'")
        permitted = config.ops_for(args.caller)
        if op.name not in permitted:
            raise GitRefused(
                f"caller {args.caller!r} is not permitted to run {op.name!r}; "
                f"permitted: {', '.join(sorted(permitted)) or '(none)'}"
            )
        if len(args.params) != len(op.params):
            raise GitRefused(
                f"operation {op.name!r} takes {len(op.params)} parameter(s) ({', '.join(op.params)}), "
                f"got {len(args.params)}"
            )
        params = dict(zip(op.params, args.params, strict=True))
        for name, value in params.items():
            _param(value, name)
        if not approved:
            print(
                f"{PROG}: dry run against a policy that is not approved: the parameters are well formed; "
                "no git command was run. Approve the policy to see the command it would run."
            )
            return EXIT_OK
        runner = git or Git()
        try:
            print(op.run(runner, policy, params, args.dry_run))
        finally:
            runner.close()
    except (GitRefused, ConfigError) as exc:
        print(f"{PROG}: refused: {exc}", file=sys.stderr)
        return EXIT_POLICY
    except GitFailed as exc:
        sys.stderr.write(exc.stdout)
        sys.stderr.write(exc.stderr)
        print(f"{PROG}: {op.name if op else args.operation} failed: {exc}", file=sys.stderr)
        return EXIT_COMMAND
    return EXIT_OK
