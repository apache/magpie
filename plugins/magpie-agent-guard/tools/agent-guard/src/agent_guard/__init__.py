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

"""Deterministic pre-execution guard dispatcher for apache-magpie.

Inspects a shell command before it runs and **denies** the ones that would
violate a hard framework rule that should never depend on the model remembering
a SKILL.md instruction. The guard decisions live in one harness-agnostic core
(:func:`dispatch`); a thin per-harness adapter translates that harness's
pre-tool hook to/from the core, so every wired harness enforces one rule set:

* :func:`main` — Claude Code ``PreToolUse`` hook (reads the event on stdin,
  emits a deny decision as JSON). The default, no-argument invocation.
* :func:`codex_main` — Codex native ``PreToolUse`` hook (``--codex``):
  consumes canonical ``Bash`` events and emits a native JSON denial.
* :func:`opencode_main` — OpenCode ``tool.execute.before`` plugin adapter
  (``--opencode``): reads ``{"command", "cwd"}`` on stdin, signals deny via a
  non-zero exit so the plugin can throw and abort the tool call. The Pi
  extension uses the same transport (``--pi``).
* :func:`antigravity_main` — Antigravity ``PreToolUse`` hook
  (``--antigravity``): matches ``run_command`` and prints a JSON
  ``{"decision": "deny", "reason": ...}`` on stdout.
* :func:`grok_main` — Grok Build ``PreToolUse`` adapter (``--grok`` or
  automatic no-argument payload-shape detection): reads the documented
  camelCase event and emits Grok's JSON allow/deny decision.
* :func:`junie_main` — Junie CLI ``PreToolUse`` hook (``--junie``): reads the
  snake_case event and blocks with a ``decision`` JSON and exit 2.
* :func:`check_main` — Harness-neutral check-only entry point (``--check``):
  takes the command as remaining CLI args, exits ``DENY_EXIT`` with the reason
  on stdout on a deny, ``ALLOW_EXIT`` silently on allow, ``USAGE_EXIT`` when no
  command is supplied. Suitable for shell scripts and wrappers that inspect the
  guard decision before acting.
* :func:`exec_main` — Harness-neutral check-then-exec entry point (``--exec``):
  same guard check, but on allow it exec-replaces this process with the command
  so the exit code and output are indistinguishable from a direct invocation.
  On deny it prints the reason to stderr and exits ``DENY_EXIT``. Any harness
  that can be configured to wrap commands through an executable can use this to
  enforce guard rules without a harness-specific hook adapter.

The engine ships two **bundled** guards — the universal ``git`` hygiene rules
that apply to every project:

1. **commit-trailer** — never let a ``git commit`` carry a ``Co-Authored-By:``
   trailer unless the repository's commit-attribution convention is
   ``co-authored-by`` (see :func:`resolve_commit_attribution` and
   ``docs/setup/commit-attribution.md``; the default is ``generated-by``).
2. **empty-rebase** — never force-push a branch that has no commits over its
   base (an empty push to a PR head auto-closes the PR and revokes write).

Domain-specific guards are **owned and contributed by the skills that need
them** via the discovery mechanism below — e.g. the ``mention`` and
``mark-ready`` guards live in ``skills/pr-management-triage/guards/`` and the
``security-language`` guard in ``skills/security-issue-fix/guards/``.

The hook fires on *every* ``Bash`` call, so this module is **stdlib-only** and
meant to be invoked directly as ``python3 .../agent_guard/__init__.py`` — never
through ``uv run`` — and returns in a few milliseconds for any command that is
not a guarded ``gh`` / ``git commit`` / ``git push`` (the fast path).

Every guard is overridable, per command, by a visible inline env assignment so a
maintainer can consciously proceed (``MAGPIE_ALLOW_MENTIONS=1 gh pr comment …``)
or disable the whole dispatcher (``MAGPIE_GUARD_OFF=1``). Overrides are read
from the command string itself (and from the hook's own environment).

**Contributing guards.** Beyond the two bundled guards, any skill adds its own
deterministic guard **without re-wiring the hook**: drop an import-free ``*.py``
file that defines a module-level ``guard(ctx)`` returning a deny string or
``None`` into any discovered guard directory — see ``GuardContext`` and
``guards.d/no_verify_commit.py`` for the template. Three sources are discovered,
in this order: every dir in ``$MAGPIE_GUARD_DIRS``; every
``plugins/<plugin>/skills/<skill>/guards`` and ``skills/<skill>/guards`` in the
framework tree this file is running from, or, from a marketplace install, the
skill guards of the sibling family plugins; and the ``guards.d`` sibling of this
file. A skill therefore owns its guards in its
own directory and they take effect as soon as the framework is installed —
nothing collects, copies, or syncs them.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #

GLOBAL_OFF_ENV = "MAGPIE_GUARD_OFF"
READY_LABEL_ENV = "MAGPIE_READY_LABEL"
DEFAULT_READY_LABEL = "ready for maintainer review"

# Shell control operators that separate one simple command from the next.
SHELL_OPERATORS = frozenset({"&&", "||", "|", ";", "&", "|&"})

# A GitHub @mention: an `@` that is NOT part of an email address (so it is not
# preceded by a word char or a dot), followed by a login (or `org/team`).
# Logins are 1-39 chars, alphanumeric or single hyphens.
MENTION_RE = re.compile(r"(?<![\w.@])@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:/[A-Za-z0-9._-]+)?)")

# Fenced code blocks and inline code spans — GitHub does not turn @mentions
# inside them into notifications, so we strip them before scanning.
_FENCED_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

GUARD_TIMEOUT = 10  # seconds for any subprocess (gh / git) a guard shells out to.

# Commit attribution (docs/setup/commit-attribution.md): one small TOML file
# per layer, the project's committed and the contributor's gitignored.
ATTRIBUTION_FILE = "commit-attribution.toml"
ATTRIBUTION_CONVENTIONS = frozenset({"generated-by", "assisted-by", "co-authored-by", "none", "custom"})
ATTRIBUTION_CONTRIBUTOR_CHOICE = "contributor-choice"  # project file only
DEFAULT_ATTRIBUTION = "generated-by"


_ASSIGNMENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*", re.DOTALL)

# `env` options (GNU coreutils and BSD): flags without a value, long options
# whose value is optional (`--default-signal[=SIG]`), and — handled in
# `_env_inner` — `-u`/`--unset` and `-C`/`--chdir`, which take one. Any other
# option leaves the command unparsed, and refused. That includes
# `-S`/`--split-string`: env splits its string with its own escapes (`\_`,
# `\c`, `${VAR}`), which shlex does not reproduce, so the guards would see a
# different command from the one env runs.
_ENV_SHORT_FLAGS = frozenset("i0v")
_ENV_LONG_FLAGS = frozenset({"ignore-environment", "null", "debug", "list-signal-handling"})
_ENV_LONG_OPTIONAL = frozenset({"block-signal", "default-signal", "ignore-signal"})
# Wrappers unwrapped per segment before the command counts as unparsed. Each
# step consumes input, so only a crafted line ever reaches this.
_UNWRAP_LIMIT = 64


class Segment:
    """One simple command from a (possibly compound) shell line.

    ``argv`` has leading ``NAME=value`` env assignments stripped into ``env``;
    ``raw`` is a reconstruction of this segment's own tokens only (used for
    substring scans that survive heredocs, e.g. the Co-Authored-By trailer).
    """

    def __init__(self, tokens: list[str], raw: str, command: str = "") -> None:
        self.env: dict[str, str] = {}
        #: True when an `env` / `command` wrapper was looked through. Sandbox
        #: exclusions match a command line by its start, so a wrapped excluded
        #: command runs sandboxed even when the command itself is spelled right.
        self.wrapped = False
        #: True when a wrapper could not be parsed; `dispatch` refuses the line.
        self.unparsed = False
        argv = self._unwrap(self._take_assignments(tokens))
        #: The command head as written (`~/.claude/scripts/x.sh`, `/usr/bin/git`),
        #: for the rules that care how a command is spelled, not just its name.
        self.head = argv[0] if argv else ""
        # Normalise the command head to its basename so a path-qualified
        # invocation (`/usr/bin/git`, `./git`) is guarded identically to the
        # bare name. Guard rules only inspect argv[0] as a command *name*; the
        # real execution path is untouched (exec_main hands the original argv
        # to os.execvp).
        if argv:
            argv[0] = os.path.basename(argv[0])
        self.argv: list[str] = argv
        self.raw = raw
        #: The whole command line as written, before tokenising: the one place
        #: quoting is still visible (a quoted `~` is not expanded by the shell).
        self.command = command

    def _take_assignments(self, tokens: list[str]) -> list[str]:
        """Strip leading ``NAME=value`` assignments into ``env``."""
        i = 0
        while i < len(tokens) and _ASSIGNMENT_RE.fullmatch(tokens[i]):
            name, _, value = tokens[i].partition("=")
            self.env[name] = value
            i += 1
        return tokens[i:]

    def _unwrap(self, argv: list[str]) -> list[str]:
        """Look through prefix wrappers that run their argument as the command:
        ``env [options] [NAME=value…] cmd …`` (its assignments join ``env``, so
        an inline override still counts) and ``command [-p] cmd …``.

        Unwrapping runs until no wrapper is left — every step consumes input, so
        it ends — and anything it cannot parse sets ``unparsed``, which
        ``dispatch`` refuses: a wrapper is never a way past the guards.
        """
        steps = 0
        while argv:
            steps += 1
            if steps > _UNWRAP_LIMIT:
                self.unparsed = True
                return argv
            head = os.path.basename(argv[0])
            if head == "env":
                inner = self._env_inner(argv[1:])
                if inner is None:
                    self.unparsed = True
                    return argv
                self.wrapped = True
                argv = inner
            elif head == "command":
                rest = argv[1:]
                while rest and rest[0].startswith("-") and rest[0] != "-":
                    flag = rest.pop(0)
                    if flag == "--":
                        break
                    letters = flag[1:]
                    if any(ch in "vV" for ch in letters):
                        return argv  # `command -v x`: a lookup, not an execution
                    if any(ch != "p" for ch in letters):
                        self.unparsed = True
                        return argv
                self.wrapped = True
                argv = rest
            else:
                return argv
        return argv

    def _env_inner(self, args: list[str]) -> list[str] | None:
        """The command ``env`` runs, after its options and assignments; None
        when an option is not one GNU / BSD ``env`` documents, or is ``-S``."""
        args = list(args)
        while args:
            tok = args[0]
            if tok == "--":
                args.pop(0)
                break
            if tok.startswith("--"):
                name, eq, _ = tok[2:].partition("=")
                if name in _ENV_LONG_FLAGS or name in _ENV_LONG_OPTIONAL:
                    args.pop(0)
                    continue
                if name in ("unset", "chdir"):
                    args.pop(0)
                    if not eq:
                        if not args:
                            return None
                        args.pop(0)
                    continue
                return None
            if tok.startswith("-") and tok != "-":
                args.pop(0)
                letters = tok[1:]
                for pos, ch in enumerate(letters):
                    if ch in _ENV_SHORT_FLAGS:
                        continue
                    if ch in "uC":
                        if not letters[pos + 1 :]:
                            if not args:
                                return None
                            args.pop(0)
                        break
                    return None
                continue
            break
        return self._take_assignments(args)

    def override(self, *names: str) -> bool:
        """True if any of ``names`` (or the global off switch) is set truthy,
        either as an inline env assignment on this segment or in the hook's own
        environment."""
        for name in (GLOBAL_OFF_ENV, *names):
            val = self.env.get(name, os.environ.get(name))
            if val not in (None, "", "0", "false", "False"):
                return True
        return False


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #


def split_segments(command: str) -> list[Segment]:
    """Tokenise ``command`` and split it into simple-command segments on shell
    operators. Returns an empty list if the command cannot be tokenised."""
    try:
        tokens = shlex.split(command, comments=False)
    except ValueError:
        return []
    segments: list[Segment] = []
    current: list[str] = []
    for tok in tokens:
        if tok in SHELL_OPERATORS:
            if current:
                segments.append(Segment(current, shlex.join(current), command))
                current = []
        else:
            current.append(tok)
    if current:
        segments.append(Segment(current, shlex.join(current), command))
    return segments


def strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code spans — mentions inside them do
    not notify on GitHub."""
    return _INLINE_CODE_RE.sub(" ", _FENCED_RE.sub(" ", text))


def find_mentions(text: str) -> list[str]:
    """Lower-cased GitHub mentions (logins and ``org/team``) in ``text``, with
    code spans stripped first."""
    return [m.group(1).lower() for m in MENTION_RE.finditer(strip_code(text))]


def _opt_value(argv: list[str], short: str, long: str) -> str | None:
    """Return the first value of ``-x``/``--xxx`` (space- or ``=``-separated) or None."""
    return next(iter(_opt_values(argv, short, long)), None)


def _opt_values(argv: list[str], short: str, long: str) -> list[str]:
    """Every value of a repeatable ``-x``/``--xxx`` flag (space- or
    ``=``-separated), in order.

    The token taken as a value is still scanned as a possible flag: without
    knowing every flag's arity, ``--body --add-label --add-label X`` cannot be
    told apart from ``--add-label --add-label``, so both readings are kept."""
    values: list[str] = []
    for i, tok in enumerate(argv):
        if tok in (short, long):
            if i + 1 < len(argv):
                values.append(argv[i + 1])
            continue
        for prefix in (f"{long}=", f"{short}="):
            if tok.startswith(prefix):
                values.append(tok[len(prefix) :])
                break
    return values


# ``gh`` command groups, used to anchor subcommand detection. Matching against
# this set means a flag VALUE can never be mistaken for the command group.
GH_COMMAND_GROUPS = frozenset(
    {
        "alias",
        "api",
        "attestation",
        "auth",
        "browse",
        "cache",
        "codespace",
        "completion",
        "config",
        "extension",
        "gist",
        "gpg-key",
        "issue",
        "label",
        "org",
        "pr",
        "project",
        "release",
        "repo",
        "ruleset",
        "run",
        "search",
        "secret",
        "ssh-key",
        "status",
        "variable",
        "workflow",
    }
)

# Flags taking a separate value that may appear BEFORE the command group.
# ``gh`` parses flags interspersed, so ``gh --repo OWNER/REPO pr create`` is
# accepted and runs normally; the value must be consumed or it is mistaken for
# the group.
GH_VALUE_FLAGS = frozenset({"-R", "--repo", "-H", "--hostname"})

# Global `git` options that take a separate value and may appear before the
# subcommand, e.g. `git -C /path commit ...`. `git` parses these interspersed
# the same way `gh` does, and the value must be consumed here for the same
# reason GH_VALUE_FLAGS is: leaving it behind shifts the subcommand one token
# to the right.
GIT_VALUE_FLAGS = frozenset(
    {
        "-C",
        "-c",
        "--exec-path",
        "--html-path",
        "--man-path",
        "--info-path",
        "--namespace",
        "--work-tree",
        "--git-dir",
        "--super-prefix",
        "--config-env",
    }
)


def git_subcommand_index(argv: list[str]) -> int | None:
    """Index into ``argv`` of the ``git`` subcommand (``\"commit\"``,
    ``\"push\"``, ...), skipping global flags and their values so
    ``git -C /tmp commit`` resolves the same as ``git commit``. None if
    ``argv`` is not a ``git`` call, or if no subcommand can be identified.

    Without this, a guard anchored on a fixed ``argv[:2]`` slice is fail-open
    for any ordinary global flag before the subcommand (``git -C <dir>
    commit``, ``git -c core.editor=true commit``, ``git --no-pager commit``),
    the same bypass ``gh_subcommand`` above already guards against for ``gh``.
    """
    if not argv or argv[0] != "git":
        return None
    i = 1
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("-") and tok != "-":
            if "=" not in tok and tok in GIT_VALUE_FLAGS:
                i += 2
                continue
            i += 1
            continue
        return i
    return None


def gh_subcommand(argv: list[str]) -> tuple[str, str] | None:
    """For an argv whose first token is ``gh``, return ``(group, sub)`` skipping
    global flags and their values, e.g. ``(\"pr\", \"comment\")``. None if not a
    ``gh`` call, or if no command group can be identified.

    Flag values are *consumed*, not merely filtered out. Dropping only the
    tokens that start with ``-`` leaves their values behind, so
    ``gh --repo apache/airflow pr create`` reads as
    ``("apache/airflow", "pr")`` and every guard keyed on ``("pr", "create")``
    silently stops running — a fail-open bypass reachable by ordinary flag
    ordering rather than by anything adversarial.
    """
    if not argv or argv[0] != "gh":
        return None

    positional: list[str] = []
    i = 1
    while i < len(argv):
        tok = argv[i]
        if tok == "--":
            positional.extend(argv[i + 1 :])
            break
        if tok.startswith("-") and tok != "-":
            # ``--flag=value`` carries its value in the same token.
            if "=" not in tok and tok in GH_VALUE_FLAGS:
                i += 2
                continue
            i += 1
            continue
        positional.append(tok)
        i += 1

    # Anchor on the first known command group so an unrecognised value-taking
    # flag before the group cannot shift the result.
    for n, tok in enumerate(positional):
        if tok in GH_COMMAND_GROUPS:
            return (tok, positional[n + 1]) if n + 1 < len(positional) else None

    if len(positional) >= 2:
        return positional[0], positional[1]
    return None


def _json_strings(value: object) -> list[str]:
    """Every string in a JSON value, depth first."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _json_strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _json_strings(v)]
    return []


def gh_body_text(argv: list[str], *, include_title: bool, read_files: bool) -> str:
    """Concatenate the inline ``--body`` (and optionally ``--title``) plus, when
    ``read_files`` is set, the contents of any ``--body-file``."""
    parts: list[str] = []
    body = _opt_value(argv, "-b", "--body")
    if body:
        parts.append(body)
    if include_title:
        title = _opt_value(argv, "-t", "--title")
        if title:
            parts.append(title)
    if read_files:
        path = _opt_value(argv, "-F", "--body-file")
        if path and path != "-":
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    parts.append(fh.read())
            except OSError:
                parts.append("\x00UNREADABLE_BODY_FILE\x00")
    return "\n".join(parts)


def _run(args: list[str], cwd: str | None = None) -> str | None:
    """Run a subprocess, returning stripped stdout, or None on any failure."""
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GUARD_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _positional_target(argv: list[str], sub_index: int) -> str | None:
    """First non-flag token after the subcommand — the PR/issue number or URL.
    ``sub_index`` is the index of the subcommand token in ``argv``."""
    i = sub_index + 1
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("-"):
            # Skip a flag and, heuristically, its value when not ``=``-joined.
            if "=" not in tok and tok not in ("--web",):
                i += 2
            else:
                i += 1
            continue
        return tok
    return None


def _repo_flag(argv: list[str]) -> list[str]:
    repo = _opt_value(argv, "-R", "--repo")
    return ["--repo", repo] if repo else []


# --------------------------------------------------------------------------- #
# Guards — each returns a deny reason string, or None to allow.
# --------------------------------------------------------------------------- #


def _find_repo_root(start: Path) -> Path | None:
    """The nearest ancestor of ``start`` (inclusive) holding a ``.git`` entry.

    A plain filesystem walk rather than ``git rev-parse``: this runs on every
    ``git commit`` the agent makes, and ``.git`` is a directory in a main
    checkout and a file in a linked worktree, so ``exists()`` covers both.
    """
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


# --------------------------------------------------------------------------- #
# Where a project's Magpie configuration lives
#
# A copy of `setup_preflight/layers.py`, inlined because this file runs as a
# plain script (``python3 .../agent_guard/__init__.py``) and cannot import a
# sibling.  Keep ``git_common_dir`` identical to that copy;
# ``tools/setup-preflight/tests/test_layers.py`` checks every copy.  Adopted
# repository (a committed ``.apache-magpie.lock``): the personal layer is
# ``<repo>/.apache-magpie-local/``.  Not adopted: ``<git-common-dir>/apache-magpie/``,
# with a legacy in-tree ``.apache-magpie-local/`` still read after it.  The
# committed layer is ``<repo>/.apache-magpie-overrides/``.  Nothing here
# creates a directory.
# --------------------------------------------------------------------------- #

LOCK_NAME = ".apache-magpie.lock"
LOCAL_DIR = ".apache-magpie-local"
OVERRIDES_DIR = ".apache-magpie-overrides"

_REPO_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*")

#: ``gh api`` flags that take a separate value, so the endpoint is the first other token.
_GH_API_VALUE_FLAGS = frozenset(
    {
        "-X",
        "--method",
        "-f",
        "--raw-field",
        "-F",
        "--field",
        "-H",
        "--header",
        "--input",
        "-q",
        "--jq",
        "-t",
        "--template",
        "--hostname",
        "--cache",
        "-p",
        "--preview",
    }
)


#: ``gh api`` flags that take no value.
_GH_API_BOOL_FLAGS = frozenset({"--paginate", "--slurp", "-i", "--include", "--silent", "--verbose"})


def _gh_api_endpoint(args: list[str]) -> str | None:
    """The endpoint positional of a ``gh api`` argument list (everything after ``api``).

    None unless the line parses unambiguously: an unknown flag (whose arity
    the guard cannot know) or a second positional means the endpoint cannot
    be told for certain.
    """
    endpoint: str | None = None
    i = 0
    while i < len(args):
        tok = args[i]
        if tok == "--":
            rest = args[i + 1 :]
            if endpoint is not None or len(rest) != 1:
                return None
            return rest[0]
        if tok.startswith("--"):
            name = tok.split("=", 1)[0]
            if name in _GH_API_VALUE_FLAGS:
                i += 1 if "=" in tok else 2
                continue
            if name in _GH_API_BOOL_FLAGS and "=" not in tok:
                i += 1
                continue
            return None
        if tok.startswith("-") and len(tok) > 1:
            flag = tok[:2]
            if flag in _GH_API_VALUE_FLAGS:
                i += 1 if len(tok) > 2 else 2
                continue
            if tok in _GH_API_BOOL_FLAGS:
                i += 1
                continue
            return None
        if endpoint is not None:
            return None
        endpoint = tok
        i += 1
    return endpoint


#: Value-taking flags of the ``gh pr`` / ``gh issue`` commands the mention
#: guards widen (comment, edit, review), besides ``-R`` / ``--repo``.
_GH_TARGET_VALUE_LONG = frozenset(
    {
        "--body",
        "--body-file",
        "--title",
        "--base",
        "--milestone",
        "--add-label",
        "--remove-label",
        "--add-reviewer",
        "--remove-reviewer",
        "--add-assignee",
        "--remove-assignee",
        "--add-project",
        "--remove-project",
    }
)
_GH_TARGET_BOOL_LONG = frozenset(
    {
        "--approve",
        "--comment",
        "--request-changes",
        "--edit-last",
        "--delete-last",
        "--yes",
        "--create-if-none",
        "--editor",
        "--web",
        "--remove-milestone",
    }
)
_GH_TARGET_VALUE_SHORT = frozenset("bFtBm")
_GH_TARGET_BOOL_SHORT = frozenset("acrew")


def _gh_target_args(args: list[str]) -> tuple[list[str], list[str]] | None:
    """Every ``--repo`` value and the positionals of a ``gh pr|issue`` argument list.

    Parsed with each flag's arity, the way ``gh`` reads the line, so a flag's
    value is never mistaken for a repository or a selector — ``--body
    -Racme/x`` is body text, not ``-R``. None when the line cannot be read
    for certain: an unknown flag, or combined short flags.
    """
    repos: list[str] = []
    positionals: list[str] = []
    i = 0
    while i < len(args):
        tok = args[i]
        if tok == "--":
            positionals.extend(args[i + 1 :])
            break
        if tok.startswith("--"):
            name, eq, value = tok.partition("=")
            if name == "--repo":
                if not eq:
                    if i + 1 >= len(args):
                        return None
                    value = args[i + 1]
                    i += 1
                repos.append(value)
            elif name in _GH_TARGET_VALUE_LONG:
                i += 0 if eq else 1
            elif name not in _GH_TARGET_BOOL_LONG or eq:
                return None
            i += 1
            continue
        if tok.startswith("-") and len(tok) > 1:
            letter, rest = tok[1], tok[2:]
            if letter == "R":
                value = rest[1:] if rest.startswith("=") else rest
                if not value:
                    if i + 1 >= len(args):
                        return None
                    value = args[i + 1]
                    i += 1
                repos.append(value)
            elif letter in _GH_TARGET_VALUE_SHORT:
                i += 0 if rest else 1
            elif letter not in _GH_TARGET_BOOL_SHORT or rest:
                return None
            i += 1
            continue
        positionals.append(tok)
        i += 1
    if len(positionals) > 1:
        return None
    return repos, positionals


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


def svn_admin_dir(root: Path) -> Path | None:
    """`<root>/.svn` when `root` is the root of a Subversion working copy, else `None`.

    Subversion keeps one `.svn`, holding a `wc.db`, at the root of a working
    copy.  Only `root`'s own is accepted, as with `.git`: following one in an
    ancestor would let any directory above the project redirect where its
    configuration is read and written.  Reads files only, never spawns `svn`.
    """
    admin = _absolute(root) / ".svn"
    return admin if (admin / "wc.db").is_file() else None


def unadopted_home(root: Path) -> Path:
    """Where an unadopted project keeps personal configuration; never created here.

    `<git-common-dir>/apache-magpie` in a git repository, else
    `<.svn>/apache-magpie` in a Subversion working copy: both inside the
    VCS's own directory, so never committed.  With no VCS at all there is
    nothing to commit it to, so it is the in-tree `<root>/.apache-magpie-local`.
    """
    common = git_common_dir(root)
    if common is not None:
        return common / GIT_HOME_NAME
    svn = svn_admin_dir(root)
    if svn is not None:
        return svn / GIT_HOME_NAME
    return root / LOCAL_DIR


def personal_dir(root: Path) -> Path:
    """Where this user's configuration for `root` is written; never created here.

    Adopted → `<root>/.apache-magpie-local`, except in a linked worktree
    that has none while its main checkout has one: then the main
    checkout's, so a worktree writes where it already reads.  Not adopted →
    `unadopted_home`.  May not exist yet.
    """
    if adopted(root):
        own = root / LOCAL_DIR
        main = main_worktree(root)
        if own.is_dir() or main is None or not (main / LOCAL_DIR).is_dir():
            return own
        return main / LOCAL_DIR
    return unadopted_home(root)


def personal_layers(root: Path) -> list[Path]:
    """Every personal directory a config file is looked up in, first match wins.

    Adopted → `<root>/.apache-magpie-local`, then, in a linked worktree,
    the main checkout's when it exists: `.apache-magpie-local/` is
    gitignored, so a new worktree has none, and a file missing from its own
    is found in the main checkout's.  Not adopted → `unadopted_home`
    (in git, already shared by every worktree), then a legacy in-tree
    `.apache-magpie-local/`.
    """
    if adopted(root):
        found = [root / LOCAL_DIR]
        main = main_worktree(root)
        if main is not None and (main / LOCAL_DIR).is_dir():
            found.append(main / LOCAL_DIR)
        return found
    found = [unadopted_home(root)]
    legacy = root / LOCAL_DIR
    if legacy.is_dir() and legacy not in found:
        found.append(legacy)
    return found


def config_layers(root: Path) -> list[Path]:
    """Every directory a config file is looked up in, first match wins."""
    return [*personal_layers(root), root / OVERRIDES_DIR]


ATTRIBUTION_PROJECT_DIR = OVERRIDES_DIR


def _read_attribution(path: Path) -> str | None:
    """The ``convention`` value of one ``commit-attribution.toml``.

    ``None`` when the file does not exist. Raises ``ValueError`` when it
    exists but cannot be read or parsed, so the caller can fail closed.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"{path}: {exc}") from exc
    # Imported here, not at the top: the module must import on a pre-3.11
    # ``python3`` so ``_reexec_under_supported_python`` can run.
    import tomllib

    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    value = data.get("convention")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{path}: convention must be a string")
    return value.strip().lower()


def resolve_commit_attribution(repo_root: Path | None) -> str:
    """The commit-attribution convention in force for ``repo_root``.

    See ``docs/setup/commit-attribution.md``. The project's committed choice
    wins when it makes one; the contributor's personal choice (the first
    personal layer holding the file, see ``personal_layers``) applies only
    when the project's file is absent, sets no ``convention``, or sets
    ``contributor-choice``. Anything unreadable, unparsable or unknown
    resolves to the default, which is the conservative answer for every guard
    that consults this: the default never permits ``Co-Authored-By:``.
    """
    if repo_root is None:
        return DEFAULT_ATTRIBUTION
    try:
        project = _read_attribution(repo_root / ATTRIBUTION_PROJECT_DIR / ATTRIBUTION_FILE)
        if project is not None and project != ATTRIBUTION_CONTRIBUTOR_CHOICE:
            return project if project in ATTRIBUTION_CONVENTIONS else DEFAULT_ATTRIBUTION
        local = None
        for layer in personal_layers(repo_root):
            local = _read_attribution(layer / ATTRIBUTION_FILE)
            if local is not None:
                break
    except ValueError:
        return DEFAULT_ATTRIBUTION
    if local in ATTRIBUTION_CONVENTIONS:
        return local
    return DEFAULT_ATTRIBUTION


def _git_start_dir(argv: list[str], sub_index: int, cwd: str | None) -> Path:
    """The directory ``git [-C <dir>]… <subcommand>`` runs as if started in."""
    base = Path(cwd) if cwd else Path.cwd()
    i = 1
    while i < sub_index:
        if argv[i] == "-C" and i + 1 < sub_index:
            base = base / argv[i + 1]
            i += 2
            continue
        i += 1
    return base


def _commit_repo_root(argv: list[str], sub_index: int, cwd: str | None) -> Path | None:
    """The repository a ``git [-C <dir>]… commit`` would commit to."""
    return _find_repo_root(_git_start_dir(argv, sub_index, cwd))


COMMIT_MESSAGE_FILE_MAX = 1024 * 1024  # bytes read from a `git commit -F` file


def _commit_message_file_text(argv: list[str], sub_index: int, cwd: str | None) -> str:
    """The message a ``git commit -F/--file <path>`` would read, or ``""``.

    AGENTS.md sends commit bodies through a file, so the command line alone
    no longer shows what the commit will say. A relative path is resolved the
    way git resolves it, against the ``-C``-adjusted start directory. A file
    that is missing or unreadable now yields nothing: git itself would fail on
    it, and one written earlier in the same command line does not exist yet
    when the hook runs — a known limit of any pre-execution check.
    """
    path = _opt_value(argv[sub_index + 1 :], "-F", "--file")
    if not path or path == "-":
        return ""
    target = Path(path)
    if not target.is_absolute():
        target = _git_start_dir(argv, sub_index, cwd) / target
    try:
        with open(target, encoding="utf-8", errors="replace") as fh:
            return fh.read(COMMIT_MESSAGE_FILE_MAX)
    except OSError:
        return ""


def guard_commit_trailer(seg: Segment, cwd: str | None) -> str | None:
    idx = git_subcommand_index(seg.argv)
    if idx is None or seg.argv[idx] != "commit":
        return None
    message = seg.raw + "\n" + _commit_message_file_text(seg.argv, idx, cwd)
    if not re.search(r"co-authored-by:", message, re.IGNORECASE):
        return None
    if seg.override("MAGPIE_ALLOW_COAUTHOR"):
        return None
    convention = resolve_commit_attribution(_commit_repo_root(seg.argv, idx, cwd))
    if convention == "co-authored-by":
        return None
    return (
        "agent-guard[commit-trailer]: this commit message carries a 'Co-Authored-By:' "
        f"trailer, but this repository's commit-attribution convention is '{convention}'. "
        "Agents are assistants, not authors: remove the Co-Authored-By line and add the "
        "trailer the convention names with `git commit --trailer` (see "
        "docs/setup/commit-attribution.md). Override (not for AI co-authorship): "
        "MAGPIE_ALLOW_COAUTHOR=1."
    )


def guard_empty_rebase(seg: Segment, cwd: str | None) -> str | None:
    idx = git_subcommand_index(seg.argv)
    if idx is None or seg.argv[idx] != "push":
        return None
    # `+refspec` is git's other force spelling: git-push(1) documents it as
    # equivalent to `--force` for that refspec, so it must be recognized here
    # and stripped from the refs the resolution below reads.
    refspecs = [t for t in seg.argv[idx + 1 :] if not t.startswith("-")]
    forced = any(
        t in ("-f", "--force") or t == "--force-with-lease" or t.startswith("--force-with-lease=")
        for t in seg.argv
    ) or any(r.startswith("+") for r in refspecs)
    if not forced:
        return None
    if seg.override("MAGPIE_ALLOW_EMPTY_PUSH"):
        return None

    # Resolve the source ref being pushed: last `src[:dst]` positional, else HEAD.
    positionals = [t.removeprefix("+") for t in refspecs]
    src = "HEAD"
    if len(positionals) >= 2:
        src = positionals[1].split(":", 1)[0] or "HEAD"
    elif len(positionals) == 1 and _run(
        ["git", "rev-parse", "--verify", "--quiet", f"{positionals[0]}^{{commit}}"], cwd=cwd
    ):
        # A lone positional that resolves to a commit is the ref; else it is the remote.
        src = positionals[0]

    default_ref = _run(["git", "rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=cwd)
    if not default_ref:
        return None  # fail-open: no base to compare against.
    base = _run(["git", "merge-base", default_ref, src], cwd=cwd)
    if not base:
        return None  # fail-open.
    count = _run(["git", "rev-list", "--count", f"{base}..{src}"], cwd=cwd)
    if count is not None and count.isdigit() and int(count) == 0:
        return (
            f"agent-guard[empty-rebase]: refusing to force-push '{src}' — it has 0 commits "
            f"over its merge-base with {default_ref}. Pushing an empty branch to a PR head "
            "auto-closes the PR and revokes maintainer write access. Verify the rebase "
            "result is non-empty first. Override: MAGPIE_ALLOW_EMPTY_PUSH=1."
        )
    return None


# The dispatchers' entry points and the stable directory each must be launched
# from. `sandbox.excludedCommands` and the `permissions.allow` rules name the
# literal `~/.claude/magpie/<tool>` spelling, so only that spelling runs outside
# the sandbox without a prompt (docs/setup/secure-agent-setup.md).
VETTED_ENTRY_POINTS = {
    "vetted-op": "vetted-ops",
    "vetted-op-read": "vetted-ops",
    "vetted-op-tracker": "vetted-ops",
    "adversarial-review": "adversarial-review",
}
VETTED_STABLE_BASE = "~/.claude/magpie/"
# `uv run` / `uvx` options that take a value, so the value is not mistaken for
# the command they launch.
_UV_VALUE_OPTIONS = frozenset(
    {
        "--project",
        "--from",
        "--directory",
        "--with",
        "--with-editable",
        "--with-requirements",
        "--group",
        "--extra",
        "--package",
        "--python",
        "-p",
        "--env-file",
        "--index",
        "--default-index",
        "--cache-dir",
        "--config-file",
    }
)


def _vetted_launch(argv: list[str]) -> tuple[str, str, str] | None:
    """``(option, base, entry_point)`` for a ``uv run --project`` / ``uvx --from``
    launch of a vetted dispatcher, or None for any other command."""
    if not argv or argv[0] not in ("uv", "uvx"):
        return None
    # `uv` takes its options on either side of `run` (`uv --project X run …`
    # is the same launch as `uv run --project X …`); `uvx` has no subcommand.
    option, rest = ("--project", argv[1:]) if argv[0] == "uv" else ("--from", argv[1:])
    needs_run = argv[0] == "uv"
    base: str | None = None
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == option:
            base = rest[i + 1] if i + 1 < len(rest) else None
            i += 2
            continue
        if tok.startswith(option + "="):
            base = tok[len(option) + 1 :]
            i += 1
            continue
        if tok in _UV_VALUE_OPTIONS:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        if needs_run:
            if tok != "run":
                return None  # another uv subcommand
            needs_run = False
            i += 1
            continue
        break
    if needs_run or base is None or i >= len(rest) or rest[i] not in VETTED_ENTRY_POINTS:
        return None
    return option, base, rest[i]


def _account_home() -> str | None:
    """The account's home from the password database, never from ``HOME``,
    which an earlier command can reassign. None where there is none (Windows).
    Spelled as the database spells it, unresolved: Codex's rewrite hook writes
    that spelling, and ``_within`` resolves the roots it compares itself."""
    try:
        import pwd  # POSIX only; the engine also runs on Windows.

        return pwd.getpwuid(os.getuid()).pw_dir
    except (ImportError, KeyError, OSError):
        return None


def _within(path: str, root: str) -> bool:
    root = os.path.realpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _inside_checkout(base: str, cwd: str | None) -> bool:
    """True when the absolute ``base`` lies in a git working tree: the one the
    command runs from, or the one ``base`` itself sits in, whatever the cwd.
    A dispatcher there is code the agent can edit. The account's own plugin
    cache is exempt, even when the home directory is version-controlled; a
    directory merely named like one elsewhere is not."""
    target = os.path.realpath(base)
    home = _account_home()
    if home and _within(target, os.path.join(home, ".claude", "plugins", "cache")):
        return False
    top = _run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if top and _within(target, top):
        return True
    probe = target
    while probe and not os.path.isdir(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            return False
        probe = parent
    top = _run(["git", "rev-parse", "--show-toplevel"], cwd=probe)
    return top is not None and _within(target, top)


_CODEX_HOOK_SCRIPT = "codex-expand-stable-path.py"


def _codex_stable_roots() -> set[str]:
    """The absolute vetted-ops roots Codex's rewrite hook may substitute for `~`.

    The hook rewrites to the root it was registered with: `--stable-path` in
    the Codex configuration (`vetted-ops-codex-rules --hook --tool-root …`),
    else the account's home. Only those exact roots are let through; a path
    the agent could build itself is not.
    """
    home = _account_home()
    if home is None:
        return set()
    roots = {f"{home.rstrip('/')}/{VETTED_STABLE_BASE[2:]}vetted-ops"}
    config = Path(os.environ.get("CODEX_HOME") or f"{home}/.codex") / "config.toml"
    try:
        import tomllib  # 3.11+, the engine's floor.

        data = tomllib.loads(config.read_text(encoding="utf-8"))
    except (ImportError, OSError, ValueError):
        return roots
    for command in _toml_commands(data):
        if _CODEX_HOOK_SCRIPT not in command:
            continue
        try:
            argv = shlex.split(command)
        except ValueError:
            continue
        if "--stable-path" in argv[:-1]:
            root = argv[argv.index("--stable-path") + 1].rstrip("/")
            if os.path.isabs(root):
                roots.add(root)
    return roots


def _toml_commands(node: object) -> list[str]:
    """Every string ``command`` value anywhere in parsed TOML."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "command" and isinstance(value, str):
                found.append(value)
            else:
                found += _toml_commands(value)
    elif isinstance(node, list):
        for item in node:
            found += _toml_commands(item)
    return found


#: User-scope scripts the sandbox exclusion names by their literal `~` path
#: (docs/setup/secure-agent-setup.md): basename -> the one spelling that matches.
EXCLUDED_SCRIPTS = {
    "magpie-run-evals.sh": "~/.claude/scripts/magpie-run-evals.sh",
}


def guard_excluded_script_spelling(seg: Segment) -> str | None:
    """Refuse a sandbox-excluded user-scope script launched by any other spelling.

    The exclusion matches only ``~/.claude/scripts/<name>``: an expanded home
    path (``/Users/<you>/…``), ``$HOME/…``, a quoted ``~`` or a repository copy
    runs *inside* the sandbox, where the script cannot reach what it was
    excluded for (the eval wrapper: the model API), so every case errors
    without being graded.
    """
    stable = EXCLUDED_SCRIPTS.get(seg.argv[0])
    if stable is None:
        return None
    # Accept only the bare spelling as written: tokenising drops quotes, and a
    # quote anywhere in a `~` prefix (`"~/…"`, `~"/…"`, `\\~/…`) stops the shell
    # from expanding it, so the line itself must carry `~/.claude/scripts/<name>`.
    bare = re.search(rf"(?:^|[\s;&|(]){re.escape(stable)}(?=\s|$)", seg.command)
    if seg.head == stable and bare and not seg.wrapped:
        return None
    if seg.override("MAGPIE_ALLOW_SCRIPT_PATH"):
        return None
    shown = f"{'env/command … ' if seg.wrapped else ''}{seg.head}"
    return (
        f"agent-guard[vetted-ops-spelling]: run `{stable} …` exactly so, as the whole command "
        f"with a bare `~`, not `{shown}`. The sandbox exclusion names only that spelling; any "
        "other runs the script inside the sandbox, where it fails. Override: MAGPIE_ALLOW_SCRIPT_PATH=1."
    )


def _bare_base(command: str, option: str, base: str) -> bool:
    """True when ``command`` carries ``<option> <base>`` exactly as written, unquoted.

    Tokenising drops quotes, but a quote or backslash anywhere in a `~` prefix
    (`"~/…"`, `~"/…"`, `\\~/…`) stops the shell from expanding it, so the raw
    line must show the bare spelling.
    """
    # Space-separated only: `--project=~/…` is not an assignment, so the shell
    # leaves that `~` alone too (and the exclusion is written with a space).
    pattern = rf"{re.escape(option)}\s+{re.escape(base)}/?(?=[\s;&|)]|$)"
    return re.search(pattern, command) is not None


def guard_vetted_ops_spelling(seg: Segment, cwd: str | None = None, harness: str | None = None) -> str | None:
    launch = _vetted_launch(seg.argv)
    if launch is None:
        return None
    option, base, entry = launch
    tool = VETTED_ENTRY_POINTS[entry]
    stable = VETTED_STABLE_BASE + tool
    base = base.rstrip("/")
    if base.startswith("~") and not _bare_base(seg.command, option, base):
        # Tokenising drops the quotes, but the shell does not expand a quoted
        # or escaped `~`: uv would get a directory literally named `~`, and the
        # exclusion (which names the bare spelling) would not match either.
        if seg.override("MAGPIE_ALLOW_VETTED_PATH"):
            return None
        return (
            f"agent-guard[vetted-ops-spelling]: the `~` in `{option} {base}` is quoted or escaped, "
            "so the shell will not expand it and the sandbox exclusion will not match. "
            f"Write it bare: `{seg.argv[0]} {'run ' if seg.argv[0] == 'uv' else ''}{option} {stable} {entry} …`."
        )
    if base == stable and seg.wrapped:
        # Right spelling, but behind `env` / `command`: the exclusion matches a
        # command line by its start, so this would run inside the sandbox.
        if seg.override("MAGPIE_ALLOW_VETTED_PATH"):
            return None
        return (
            f"agent-guard[vetted-ops-spelling]: run `{seg.argv[0]} {'run ' if seg.argv[0] == 'uv' else ''}"
            f"{option} {stable} {entry} …` as the whole command, not behind `env` / `command`: "
            "the sandbox exclusion matches only a command line that starts with it."
        )
    if base == stable:
        return None
    if harness == "codex" and entry == "vetted-op-read" and base in _codex_stable_roots():
        # Codex's execpolicy cannot match `~`, so its own hook rewrites a lone
        # read to the absolute root it was registered with
        # (tools/vetted-ops/hooks/codex-expand-stable-path.py). Only reads are
        # rewritten, and only to that exact root.
        return None
    # What is refused: the stable path spelled any other way (expanded home,
    # `$HOME`, the wrong dispatcher's link), a relative path, and an absolute
    # path inside the working tree: both are a checkout the agent can edit.
    # Another absolute or `~` path is a harness's own installed plugin
    # directory (docs: tools/adversarial-review/README.md) and is left to that
    # harness's rules.
    stable_elsewhere = "/.claude/magpie/" in base or base.startswith(VETTED_STABLE_BASE)
    relative = not base.startswith(("/", "~"))
    checkout = base.startswith("/") and not stable_elsewhere and _inside_checkout(base, cwd)
    if not (stable_elsewhere or relative or checkout or base.startswith("$")):
        return None
    if seg.override("MAGPIE_ALLOW_VETTED_PATH"):
        return None
    return (
        f"agent-guard[vetted-ops-spelling]: `{entry}` must be launched as "
        f"`{seg.argv[0]} {'run ' if seg.argv[0] == 'uv' else ''}{option} {stable} {entry} …`, "
        f"spelled with the literal `~`, not `{base}`. The sandbox exclusion and the "
        "permission rules name only that spelling: an expanded home path runs inside the "
        "sandbox, where gh cannot verify TLS, and a checkout path runs code the agent can "
        "edit, which must never be excluded from the sandbox. Re-run it with the `~` form. "
        "Override (developing the dispatcher itself): MAGPIE_ALLOW_VETTED_PATH=1."
    )


# The framework's bundled guards — the universal `git` hygiene rules that apply
# to every project regardless of which skills are installed. Domain-specific
# guards are owned and contributed by the skills that need them (e.g. the
# mention + mark-ready guards live in `skills/pr-management-triage/guards/`, the
# security-language guard in `skills/security-issue-fix/guards/`); they are
# discovered at runtime, in place, without editing this file or re-wiring the
# hook — see "Contributing guards" above.
BUILTIN_GUARDS: tuple[Callable[[Segment, str | None], str | None], ...] = (
    guard_commit_trailer,
    guard_empty_rebase,
)

# Only commands in these families are inspected; everything else takes the
# instant fast path. Bundled and contributed guards alike operate on the
# `gh` / `git` outbound/destructive surface.
GUARDED_HEADS = frozenset({"gh", "git"})

# Colon-separated extra guard directories, searched before the discovered ones.
# Skill-owned guards no longer need it (``framework_root`` finds them in place);
# it remains the escape hatch for guards kept outside the framework tree.
GUARD_DIRS_ENV = "MAGPIE_GUARD_DIRS"


# --------------------------------------------------------------------------- #
# Contributed-guard extension API
# --------------------------------------------------------------------------- #


class GuardContext:
    """The API passed to every **contributed** guard — ``guard(ctx) -> str | None``.

    A skill adds a guard by dropping an import-free ``*.py`` file in a discovered
    ``guards.d`` directory that defines a module-level ``guard(ctx)`` (and an
    optional ``TRIGGERS`` list of command families, e.g. ``["gh"]`` /
    ``["git:commit"]``). Returning a string denies the command with that reason;
    returning ``None`` allows it. Everything the guard needs is on ``ctx`` — it
    never imports ``agent_guard`` — so guards stay decoupled from the engine.
    """

    def __init__(self, seg: Segment, cwd: str | None) -> None:
        self.seg = seg
        self.cwd = cwd

    @property
    def argv(self) -> list[str]:
        return self.seg.argv

    @property
    def raw(self) -> str:
        return self.seg.raw

    @property
    def ready_label(self) -> str:
        return os.environ.get(READY_LABEL_ENV, DEFAULT_READY_LABEL)

    def override(self, *names: str) -> bool:
        return self.seg.override(*names)

    def gh_subcommand(self) -> tuple[str, str] | None:
        return gh_subcommand(self.argv)

    def git_subcommand(self) -> str | None:
        """The ``git`` subcommand (``\"commit\"``, ``\"push\"``, ...), skipping
        global flags and their values the same way :func:`gh_subcommand` does
        for ``gh``. None if this segment is not a ``git`` call."""
        idx = git_subcommand_index(self.argv)
        return self.argv[idx] if idx is not None else None

    def opt(self, short: str, long: str) -> str | None:
        return _opt_value(self.argv, short, long)

    def opts(self, short: str, long: str) -> list[str]:
        """Every value of a repeatable flag; :meth:`opt` returns only the first."""
        return _opt_values(self.argv, short, long)

    def gh_body(self, *, include_title: bool = False, read_files: bool = True) -> str:
        return gh_body_text(self.argv, include_title=include_title, read_files=read_files)

    def mentions(self, text: str) -> list[str]:
        return find_mentions(text)

    def _committed_config_text(self, filename: str) -> str | None:
        """``.apache-magpie-overrides/<filename>`` on the target repository's default branch, on GitHub.

        A value that widens what a guard allows must come from somewhere the
        agent cannot write. Anything local fails that test — the agent can
        edit a file, commit it, or ``cd`` into a scratch repository it made —
        so the guard reads the copy GitHub serves from the default branch of
        the repository the command posts to, which only a reviewed, merged
        change can alter. A fork or scratch repository only ever governs
        itself. Unreadable → None, and the guard falls back to the strict rule.
        """
        repo = self.target_repo()
        if repo is None:
            return None
        return self.run(
            [
                "gh",
                "api",
                f"repos/{repo}/contents/{OVERRIDES_DIR}/{filename}",
                "-H",
                "Accept: application/vnd.github.raw",
            ]
        )

    def _committed_row(self, filename: str, key: str) -> str | None:
        text = self._committed_config_text(filename)
        for line in (text or "").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[0] == f"`{key}`":
                return cells[1]
        return None

    def committed_config_value(self, filename: str, key: str) -> str | None:
        """The first backticked value of a `` | `key` | value | `` row of the config on the target repository's default branch."""
        cell = self._committed_row(filename, key)
        match = re.match(r"`([^`]+)`", cell or "")
        return match.group(1).strip() if match else None

    def committed_config_values(self, filename: str, key: str) -> list[str]:
        """Every backticked value of a `` | `key` | value | `` row of the config on the target repository's default branch."""
        return [t.strip() for t in re.findall(r"`([^`]+)`", self._committed_row(filename, key) or "")]

    def gh_input_json(self) -> object | None:
        """The JSON payload of ``gh api --input <file>``, or None."""
        path = self.opt("--input", "--input")
        if not path or path == "-":
            return None
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def target_repo(self) -> str | None:
        """``OWNER/REPO`` a ``gh`` command explicitly acts on, or None when that is not certain.

        Only guards that *widen* a rule ask, so anything ambiguous answers
        None and the strict rule stands. ``gh api`` acts on the repository in
        a plain ``repos/OWNER/REPO/…`` endpoint; ``graphql`` and any other
        endpoint can reach any repository, and an endpoint with ``.`` / ``..``
        segments, percent-encoding or ``{owner}`` placeholders is refused
        rather than resolved. Every other command must name its repository —
        through ``--repo`` and/or a PR / issue URL as the selector
        positional — and all of them must agree. There is no fallback to the
        checkout: a ``cd`` or ``GH_REPO`` earlier on the line would change
        what ``gh`` posts to without the guard seeing it.
        """
        sub = self.gh_subcommand()
        if sub is not None and sub[0] == "api" and "api" in self.argv:
            endpoint = _gh_api_endpoint(self.argv[self.argv.index("api") + 1 :]) or ""
            path = endpoint.split("?", 1)[0].split("#", 1)[0]
            if any(c in path for c in "%{}\\") or any(seg in (".", "..") for seg in path.split("/")):
                return None
            m = re.fullmatch(r"/?repos/([^/]+/[^/]+)(?:/.*)?", path)
            found = {m.group(1).lower()} if m else set()
        else:
            parsed = _gh_target_args(self.argv[self.argv.index(sub[1]) + 1 :]) if sub is not None else None
            if parsed is None:
                return None
            repos, positionals = parsed
            found = {r.lower() for r in repos}
            # Only the selector positional (`gh pr comment <URL>`) names a
            # repository; a URL inside --body or any other value is text.
            m = re.fullmatch(
                r"https?://(?:www\.)?github\.com/([^/]+/[^/#?]+)/(?:pull|issues)/\d+(?:[/#?].*)?",
                positionals[0] if positionals else "",
                re.IGNORECASE,
            )
            if m:
                found.add(m.group(1).lower())
        if len(found) != 1:
            return None
        repo = found.pop()
        return repo if _REPO_SLUG.fullmatch(repo) else None

    def target_repo_owner(self) -> str | None:
        """The owner of the repository a ``gh`` command acts on (see :meth:`target_repo`)."""
        repo = self.target_repo()
        return repo.split("/", 1)[0] if repo else None

    def gh_api_posted_text(self) -> tuple[list[str], bool] | None:
        """Every value a non-``GET`` ``gh api`` call would send, and whether all of it was readable.

        ``None`` for anything that is not ``gh api``, and for an explicit
        ``GET``. No endpoint or mutation list: a write to any endpoint is
        scanned, so a newly added endpoint cannot slip past. The flags are
        parsed the way ``gh`` accepts them — ``-X POST``, ``-XPOST``,
        ``--method=POST``, ``-f k=v``, ``-fk=v``, ``--raw-field=k=v``, the
        same for ``-F`` / ``--field`` (whose ``@file`` is read) and
        ``--input`` (every string in its JSON). Text on stdin cannot be
        inspected, so it comes back as not readable.
        """
        sub = self.gh_subcommand()
        if sub is None or sub[0] != "api" or "api" not in self.argv:
            return None
        idx = self.argv.index("api")
        method: str | None = None
        raw_fields: list[str] = []
        typed_fields: list[str] = []
        inputs: list[str] = []
        tokens = self.argv[idx + 1 :]
        k = 0
        while k < len(tokens):
            tok = tokens[k]
            value: str | None = None
            for flags, sink in (
                (("-X", "--method"), "method"),
                (("-f", "--raw-field"), "raw"),
                (("-F", "--field"), "typed"),
                (("--input",), "input"),
            ):
                for flag in flags:
                    if tok == flag:
                        value = tokens[k + 1] if k + 1 < len(tokens) else ""
                        k += 1
                    elif flag.startswith("--") and tok.startswith(flag + "="):
                        value = tok[len(flag) + 1 :]
                    elif not flag.startswith("--") and tok.startswith(flag) and len(tok) > len(flag):
                        value = tok[len(flag) :]
                    if value is not None:
                        break
                if value is not None:
                    if sink == "method":
                        method = value.upper()
                    elif sink == "raw":
                        raw_fields.append(value)
                    elif sink == "typed":
                        typed_fields.append(value)
                    else:
                        inputs.append(value)
                    break
            k += 1
        if method is None:
            method = "POST" if (raw_fields or typed_fields or inputs) else "GET"
        if method == "GET":
            return None
        texts: list[str] = [v.partition("=")[2] for v in raw_fields]
        readable = True
        for field in typed_fields:
            value = field.partition("=")[2]
            if value.startswith("@"):
                if value == "@-":
                    readable = False
                    continue
                try:
                    texts.append(Path(value[1:]).read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    readable = False
            else:
                texts.append(value)
        for path in inputs:
            if path == "-":
                readable = False
                continue
            try:
                texts.extend(_json_strings(json.loads(Path(path).read_text(encoding="utf-8"))))
            except (OSError, ValueError):
                readable = False
        return texts, readable

    def positional_after(self, sub_token: str) -> str | None:
        try:
            idx = self.argv.index(sub_token)
        except ValueError:
            return None
        return _positional_target(self.argv, idx)

    def repo_flag(self) -> list[str]:
        return _repo_flag(self.argv)

    def run(self, args: list[str]) -> str | None:
        return _run(args, cwd=self.cwd)


def command_kinds(seg: Segment) -> set[str]:
    """The command-family tags a segment matches, e.g. ``{"git", "git:commit"}``."""
    kinds: set[str] = set()
    if not seg.argv:
        return kinds
    head = seg.argv[0]
    kinds.add(head)
    if head == "git":
        # A TRIGGERS = ["git:commit"] contributed guard must still fire behind
        # an ordinary global flag (`git -C <dir> commit`); a plain seg.argv[1]
        # read is the same fail-open shape guard_commit_trailer had.
        idx = git_subcommand_index(seg.argv)
        if idx is not None:
            kinds.add(f"git:{seg.argv[idx]}")
    elif len(seg.argv) > 1 and head == "gh":
        # Same for TRIGGERS = ["gh:pr"] behind `gh -R <repo> pr ...`.
        sub = gh_subcommand(seg.argv)
        kinds.add(f"{head}:{sub[0] if sub else seg.argv[1]}")
    return kinds


def framework_root() -> Path | None:
    """The framework tree this engine is running out of, or ``None``.

    Recognised by the two directories the engine always sits beside: a
    ``skills/`` or ``plugins/`` tree and the ``tools/agent-guard`` package holding this file.
    That holds whether the hook runs from an installed plugin, a framework
    checkout, or an adopter's snapshot — and does not hold for a standalone copy
    of this one file, which is why the result is optional rather than a path
    computed by counting ``parents``.
    """
    for parent in Path(__file__).resolve().parents:
        if ((parent / "skills").is_dir() or (parent / "plugins").is_dir()) and (
            parent / "tools" / "agent-guard"
        ).is_dir():
            return parent
    return None


#: The plugin that ships this engine, as named in a marketplace's plugin cache.
ENGINE_PLUGIN = "magpie-agent-guard"


def installed_plugin_guard_dirs() -> list[Path]:
    """Skill guards of the family plugins installed beside this engine's plugin.

    A marketplace install caches every plugin on its own, as
    ``<marketplace>/<plugin>/<version>/``, so the plugins whose skills own guards
    are siblings of this one rather than a framework tree above it. Each sibling's
    copy at this engine's version is used, since the families are released
    together; failing that, its most recently installed version. Empty when the
    engine is not running from such a cache.
    """
    for plugin_root in Path(__file__).resolve().parents:
        if (plugin_root / ".claude-plugin").is_dir():
            break
    else:
        return []
    if plugin_root.parent.name != ENGINE_PLUGIN:
        return []
    dirs: list[Path] = []
    for plugin in sorted(plugin_root.parent.parent.iterdir()):
        if plugin.name == ENGINE_PLUGIN or not plugin.is_dir():
            continue
        installed = [v for v in plugin.iterdir() if (v / ".claude-plugin").is_dir()]
        same = plugin / plugin_root.name
        if same in installed:
            chosen = same
        elif installed:
            chosen = max(installed, key=lambda v: v.stat().st_mtime)
        else:
            continue
        dirs.extend(sorted(chosen.glob("skills/*/guards")))
    return dirs


def guard_dirs() -> list[Path]:
    """Directories scanned for contributed guards: ``$MAGPIE_GUARD_DIRS`` entries,
    then every ``plugins/*/skills/*/guards`` and ``skills/*/guards`` in the framework
    tree this file runs from, or, from a marketplace install, the skill guards of
    the sibling family plugins; then the ``guards.d`` sibling of this file."""
    dirs: list[Path] = []
    env = os.environ.get(GUARD_DIRS_ENV)
    if env:
        dirs.extend(Path(p) for p in env.split(os.pathsep) if p)
    if (root := framework_root()) is not None:
        dirs.extend(sorted((root / "plugins").glob("*/skills/*/guards")))
        dirs.extend(sorted((root / "skills").glob("*/guards")))
    else:
        dirs.extend(installed_plugin_guard_dirs())
    dirs.append(Path(__file__).resolve().parent / "guards.d")
    seen: set[Path] = set()
    out: list[Path] = []
    for d in dirs:
        if d.is_dir():
            real = d.resolve()
            if real not in seen:
                seen.add(real)
                out.append(d)
    return out


def discover_guards() -> list[tuple[Callable[[GuardContext], str | None], set[str] | None]]:
    """Load contributed guards from the guard dirs. Each is returned with its
    declared ``TRIGGERS`` set (or None to mean "any guarded command"). A guard
    file that fails to import is skipped — a broken contribution must never break
    the user's shell."""
    found: list[tuple[Callable[[GuardContext], str | None], set[str] | None]] = []
    for directory in guard_dirs():
        for path in sorted(directory.glob("*.py")):
            if path.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"_agentguard_{path.stem}", path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception:
                continue
            fn = getattr(module, "guard", None)
            if not callable(fn):
                continue
            triggers = getattr(module, "TRIGGERS", None)
            found.append((fn, set(triggers) if triggers else None))
    return found


# --------------------------------------------------------------------------- #
# Dispatch / entry point
# --------------------------------------------------------------------------- #


def dispatch(command: str, cwd: str | None = None, harness: str | None = None) -> str | None:
    """Return a deny reason for ``command``, or None to allow it.

    ``harness`` names the calling adapter only where a rule must differ by
    harness (the Codex stable-path rewrite, see guard_vetted_ops_spelling).
    """
    if not command:
        return None
    contributed: list[tuple[Callable[[GuardContext], str | None], set[str] | None]] | None = None
    for seg in split_segments(command):
        if seg.unparsed and not seg.override():
            return (
                "agent-guard[wrapper]: this command runs behind an `env` / `command` wrapper the "
                "guards cannot parse, so they cannot see what it runs. Run the command without "
                "the wrapper (inline `NAME=value` assignments work on their own)."
            )
        if seg.argv and seg.argv[0] in ("uv", "uvx"):
            # Checked here rather than as a guarded head: a vetted launch is the
            # only `uv` rule, and contributed guards stay on `gh` / `git`.
            reason = guard_vetted_ops_spelling(seg, cwd, harness)
            if reason:
                return reason
            continue
        if seg.argv and seg.argv[0] in EXCLUDED_SCRIPTS:
            reason = guard_excluded_script_spelling(seg)
            if reason:
                return reason
            continue
        if not seg.argv or seg.argv[0] not in GUARDED_HEADS:
            continue  # fast path — non-guarded command family
        # Bundled guards (trusted, in-process; each self-filters its command).
        for builtin in BUILTIN_GUARDS:
            try:
                reason = builtin(seg, cwd)
            except Exception:
                continue
            if reason:
                return reason
        # Contributed guards, discovered lazily once per command.
        if contributed is None:
            contributed = discover_guards()
        kinds = command_kinds(seg)
        ctx = GuardContext(seg, cwd)
        for fn, triggers in contributed:
            if triggers is not None and not (triggers & kinds):
                continue
            try:
                reason = fn(ctx)
            except Exception:
                continue
            if reason:
                return reason
    return None


def _emit_deny(reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")


def _claude_event(event: object, harness: str | None = None) -> int:
    """Handle one parsed Claude Code ``PreToolUse`` event."""
    if not isinstance(event, dict) or event.get("tool_name") != "Bash":
        return ALLOW_EXIT
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return ALLOW_EXIT
    command = str(tool_input.get("command", ""))
    cwd = event.get("cwd")
    reason = dispatch(command, cwd if isinstance(cwd, str) else None, harness)
    if reason:
        _emit_deny(reason)
    return ALLOW_EXIT


def main() -> int:
    """Claude Code ``PreToolUse`` entry point."""
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ALLOW_EXIT
    return _claude_event(event)


def codex_main() -> int:
    """Codex's native Bash hook shares Claude's event and denial schema.

    Unified exec is reported as Bash with tool_input.command by Codex.
    Never emit an allow decision: ordinary commands still need the native
    sandbox and exec-policy approval checks. Malformed input follows the
    shared fail-open contract; this hook is not a sandbox replacement.
    """
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ALLOW_EXIT
    if not isinstance(event, dict) or event.get("hook_event_name") != "PreToolUse":
        return ALLOW_EXIT
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
        return ALLOW_EXIT
    return _claude_event(event, "codex")


# Exit codes for the harness-neutral entry point (``--opencode`` and any future
# harness whose hook blocks on a non-zero child exit): 0 = allow, DENY = block.
ALLOW_EXIT = 0
DENY_EXIT = 2
# Usage error (no command supplied to ``--check`` / ``--exec``). Deliberately
# distinct from DENY_EXIT so a wrapper testing ``$? -eq 2`` for a *policy* deny
# never mistakes a misinvocation for a block. Matches sysexits ``EX_USAGE``.
USAGE_EXIT = 64
# Cap on ``--exec`` self-re-entry. A wrapper named e.g. ``git`` placed earlier on
# ``$PATH`` that calls ``--exec git`` will have ``os.execvp`` re-resolve the bare
# name back to itself and loop; this bound turns that runaway into a clear error.
_EXEC_DEPTH_VAR = "_AGENT_GUARD_EXEC_DEPTH"
_EXEC_DEPTH_MAX = 20


def opencode_main() -> int:
    """Harness-neutral entry point used by the OpenCode plugin.

    Reads a minimal ``{"command": "...", "cwd": "..."}`` JSON object on stdin —
    the shape the OpenCode ``tool.execute.before`` plugin forwards for the
    ``bash`` tool — and runs the **same** :func:`dispatch` core that backs the
    Claude Code hook. On a deny it writes the reason to stdout and exits
    ``DENY_EXIT``; the plugin turns that non-zero exit into a thrown error that
    aborts the tool call. On allow (or any malformed input) it exits
    ``ALLOW_EXIT`` — fail-open, exactly like the Claude path, so a guard glitch
    never wedges the user's session.

    The guard *decisions* are therefore identical across harnesses; only this
    thin I/O shell differs from :func:`main`.
    """
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ALLOW_EXIT
    if not isinstance(event, dict):
        return ALLOW_EXIT
    command = str(event.get("command", ""))
    cwd = event.get("cwd")
    reason = dispatch(command, cwd if isinstance(cwd, str) else None)
    if reason:
        sys.stdout.write(reason + "\n")
        return DENY_EXIT
    return ALLOW_EXIT


def kiro_main() -> int:
    """Harness-neutral entry point for Kiro CLI's ``preToolUse`` hook.

    Reads Kiro's hook event on stdin — ``{"tool_name": "...", "tool_input":
    {"command": "..."}, "cwd": "..."}`` — matches the shell tool
    (``execute_bash`` / its ``shell`` alias / ``execute_cmd``), and runs the
    **same** :func:`dispatch` core as every other harness. On a deny it writes
    the reason to **stderr** (which Kiro returns to the model) and exits
    ``DENY_EXIT`` (2 = block for ``PreToolUse``); on allow, a non-shell tool, or
    any malformed input it exits ``ALLOW_EXIT`` — fail-open, exactly like the
    Claude and OpenCode paths. Only this thin I/O shell differs; the guard
    decisions are identical across harnesses.
    """
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ALLOW_EXIT
    if not isinstance(event, dict):
        return ALLOW_EXIT
    if event.get("tool_name") not in ("execute_bash", "shell", "execute_cmd"):
        return ALLOW_EXIT
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return ALLOW_EXIT
    command = str(tool_input.get("command", ""))
    cwd = event.get("cwd")
    reason = dispatch(command, cwd if isinstance(cwd, str) else None)
    if reason:
        sys.stderr.write(reason + "\n")
        return DENY_EXIT
    return ALLOW_EXIT


def antigravity_main() -> int:
    """Translate Antigravity's ``PreToolUse`` hook event to the shared guard core.

    Antigravity pipes ``{"toolCall": {"name": "run_command", "args":
    {"CommandLine": "...", "Cwd": "..."}}, "workspacePaths": [...], ...}`` on
    stdin and reads a JSON decision from stdout. A deny is
    ``{"decision": "deny", "reason": ...}``, which blocks the call and returns
    the reason to the model. Everything else prints ``{"decision": "allow"}``,
    which defers to the user's permission rules rather than approving the call.
    Malformed and non-shell events allow, matching the other adapters'
    fail-open contract.

    The hook runs with its ``hooks.json`` directory as the working directory,
    so Git checks use the command's ``Cwd`` when present, else the first
    workspace root.
    """
    allow = json.dumps({"decision": "allow"})
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.stdout.write(allow + "\n")
        return ALLOW_EXIT
    tool_call = event.get("toolCall") if isinstance(event, dict) else None
    if not isinstance(tool_call, dict) or tool_call.get("name") != "run_command":
        sys.stdout.write(allow + "\n")
        return ALLOW_EXIT
    args = tool_call.get("args")
    command = args.get("CommandLine") if isinstance(args, dict) else None
    if not isinstance(args, dict) or not isinstance(command, str):
        sys.stdout.write(allow + "\n")
        return ALLOW_EXIT
    cwd = args.get("Cwd")
    if not isinstance(cwd, str) or not cwd:
        roots = event.get("workspacePaths")
        cwd = roots[0] if isinstance(roots, list) and roots and isinstance(roots[0], str) else None
    reason = dispatch(command, cwd)
    if reason:
        sys.stdout.write(json.dumps({"decision": "deny", "reason": reason}) + "\n")
        return ALLOW_EXIT
    sys.stdout.write(allow + "\n")
    return ALLOW_EXIT


# Read-only commands the Copilot adapter answers ``allow`` for, so they never
# prompt (PRINCIPLES.md §1, "Avoiding prompt fatigue"). Matching is on parsed
# argv of a single simple command only: any shell metacharacter, redirection,
# substitution or chaining falls back to Copilot's normal prompt.
_COPILOT_SHELL_META = re.compile(r"[;&|<>`$()\n\r\\{}]")
_COPILOT_GH_READ = {
    ("pr", "view"), ("pr", "list"), ("pr", "diff"), ("pr", "checks"),
    ("issue", "view"), ("issue", "list"),
    ("repo", "view"), ("repo", "list"),
    ("run", "view"), ("run", "list"),
    ("workflow", "view"), ("workflow", "list"),
    ("release", "view"), ("release", "list"),
    ("label", "list"), ("cache", "list"),
}  # fmt: skip
_COPILOT_GH_API_WRITE = re.compile(r"^(-X|--method|-f|-F|--field|--raw-field|--input)(=.*)?$|^-[XfF].+")
_COPILOT_GIT_READ = {
    "status", "diff", "log", "show", "rev-parse", "ls-files", "blame", "describe",
    "merge-base", "cat-file", "rev-list", "shortlog", "ls-remote",
}  # fmt: skip
_COPILOT_GIT_FLAG_DENY = {"--output", "--ext-diff", "--textconv", "--exec-path"}


def copilot_read_only(command: str) -> bool:
    """True when *command* is one simple, side-effect-free read.

    Deliberately narrow: the answer ``allow`` skips Copilot's own prompt, so
    anything uncertain returns False and keeps the default behaviour.
    """
    if _COPILOT_SHELL_META.search(command):
        return False
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    if len(argv) < 2:
        return False
    head = os.path.basename(argv[0])
    if head == "gh":
        rest = [a for a in argv[1:] if not a.startswith("-")]
        if len(rest) >= 2 and (rest[0], rest[1]) in _COPILOT_GH_READ:
            return True
        if rest[:1] == ["search"] or rest[:2] == ["auth", "status"]:
            return True
        if rest[:1] == ["api"] and rest[1:2] != ["graphql"]:
            return not any(_COPILOT_GH_API_WRITE.match(a) for a in argv[2:])
        return False
    if head == "git":
        if any(a.split("=")[0] in _COPILOT_GIT_FLAG_DENY for a in argv):
            return False
        return argv[1] in _COPILOT_GIT_READ
    return "vetted-op-read" in argv[:6] and argv[0] in {"uv", "uvx"}


def _copilot_command(event: dict[str, object]) -> tuple[str, str | None] | None:
    """Extract ``(command, cwd)`` from either Copilot payload shape."""
    name = event.get("tool_name", event.get("toolName"))
    if not isinstance(name, str) or name.lower() not in {"bash", "shell"}:
        return None
    args = event.get("tool_input", event.get("toolArgs"))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, ValueError):
            return None
    if not isinstance(args, dict) or not isinstance(args.get("command"), str):
        return None
    cwd = event.get("cwd")
    return args["command"], cwd if isinstance(cwd, str) else None


def _copilot_emit(decision: str, reason: str) -> None:
    json.dump(
        {
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            },
        },
        sys.stdout,
    )
    sys.stdout.write("\n")


def copilot_main() -> int:
    """Copilot CLI ``PreToolUse`` adapter.

    Accepts both the PascalCase (Claude/VS Code-compatible) and camelCase
    payloads. A guard hit emits one ``deny`` decision; a provably read-only
    command emits ``allow`` so it does not prompt; everything else prints
    nothing and Copilot's normal permission flow decides. Malformed events are
    silent, like every other adapter.
    """
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ALLOW_EXIT
    if not isinstance(event, dict):
        return ALLOW_EXIT
    parsed = _copilot_command(event)
    if parsed is None:
        return ALLOW_EXIT
    command, cwd = parsed
    reason = dispatch(command, cwd)
    if reason:
        _copilot_emit("deny", reason)
    elif copilot_read_only(command):
        _copilot_emit("allow", "magpie: read-only command")
    return ALLOW_EXIT


def _grok_event(event: object) -> int:
    """Handle one parsed Grok Build ``PreToolUse`` event."""
    if not isinstance(event, dict):
        return ALLOW_EXIT
    if event.get("toolName") != "run_terminal_command":
        return ALLOW_EXIT
    tool_input = event.get("toolInput")
    if not isinstance(tool_input, dict):
        return ALLOW_EXIT
    command = tool_input.get("command")
    if not isinstance(command, str):
        return ALLOW_EXIT

    cwd = event.get("cwd")
    reason = dispatch(command, cwd if isinstance(cwd, str) else None)
    if reason:
        json.dump({"decision": "deny", "reason": reason}, sys.stdout)
        sys.stdout.write("\n")
        return DENY_EXIT

    return ALLOW_EXIT


def grok_main() -> int:
    """Translate Grok Build ``PreToolUse`` input to the shared guard core.

    Verified with Grok Build 1.0.46 (2765805b9442). ``PreToolUse`` supplies
    camelCase ``toolName`` / ``toolInput`` fields; the captured shell event uses
    ``run_terminal_command`` and carries the command in ``toolInput.command``.
    Relevant calls emit Grok's explicit JSON decision. Malformed or unrelated
    events stay silent and fail open inside the adapter.
    """
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ALLOW_EXIT
    return _grok_event(event)


def _junie_event(event: object) -> int:
    """Handle one parsed Junie CLI ``PreToolUse`` event."""
    if not isinstance(event, dict) or event.get("tool_name") != "Bash":
        return ALLOW_EXIT
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return ALLOW_EXIT
    command = tool_input.get("command")
    if not isinstance(command, str):
        return ALLOW_EXIT

    cwd = event.get("cwd")
    reason = dispatch(command, cwd if isinstance(cwd, str) else None)
    if reason:
        json.dump({"decision": "deny", "reason": reason}, sys.stdout)
        sys.stdout.write("\n")
        sys.stderr.write(reason + "\n")
        return DENY_EXIT

    return ALLOW_EXIT


def junie_main() -> int:
    """Translate Junie CLI ``PreToolUse`` input to the shared guard core.

    Junie sends snake_case ``tool_name`` / ``tool_input`` like Claude Code but
    does not honour Claude's ``hookSpecificOutput`` deny: it reads a top-level
    ``decision`` and blocks unconditionally on exit code 2. The adapter emits
    both, so the block holds whichever the runtime checks first. It is selected
    explicitly with ``--junie`` because the no-argument shape sniff would route
    this payload to the Claude adapter and fail open.
    """
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ALLOW_EXIT
    return _junie_event(event)


def check_main(argv: list[str]) -> int:
    """Harness-neutral check-only entry point (``--check``).

    Takes the command to inspect as ``argv`` (the remaining arguments after the
    ``--check`` flag), joins them into a command string, and runs
    :func:`dispatch`. On a deny it writes the reason to *stdout* and exits
    ``DENY_EXIT``; on allow it exits ``ALLOW_EXIT`` silently.

    Stdout is used (matching the ``--opencode`` convention) so callers can
    capture the reason::

        reason=$(python3 agent-guard.py --check git push origin main)
        if [ $? -eq 2 ]; then echo "blocked: $reason"; exit 1; fi
        git push origin main

    **Fail-open on decision, like every other entry point:** a *present*
    command that matches no guard rule — or one the engine cannot evaluate
    (a :func:`dispatch` error) — returns ``ALLOW_EXIT`` so a misconfigured
    wrapper never hard-blocks the user. Invoking with **no command at all** is
    a usage error and returns ``USAGE_EXIT`` (not ``DENY_EXIT``), so a caller
    testing ``$? -eq 2`` for a policy deny never mistakes a misinvocation for a
    block.
    """
    if not argv:
        sys.stderr.write("agent-guard --check: no command specified\n")
        return USAGE_EXIT
    command = shlex.join(argv)
    cwd = os.getcwd()
    try:
        reason = dispatch(command, cwd)
    except Exception as exc:  # fail-open: a guard glitch never blocks the user
        sys.stderr.write(f"agent-guard --check: guard engine error, allowing: {exc}\n")
        return ALLOW_EXIT
    if reason:
        sys.stdout.write(reason + "\n")
        return DENY_EXIT
    return ALLOW_EXIT


def exec_main(argv: list[str]) -> int:
    """Harness-neutral check-then-exec entry point (``--exec``).

    Takes the command to execute as ``argv`` (remaining arguments after
    ``--exec``), runs :func:`dispatch`, and either exec-replaces this process
    with the command (allow) or prints the deny reason to *stderr* and exits
    ``DENY_EXIT`` (deny). On allow the process image is replaced via
    :func:`os.execvp`, so the command's own exit code and output are
    indistinguishable from a direct invocation.

    Any harness or shell integration that can substitute this as the executor
    for ``git`` and ``gh`` commands enforces guard rules without a
    harness-specific hook adapter::

        # As a shell alias (project .bashrc / .zshrc). Safe: aliases are
        # invisible to os.execvp, so the bare name resolves to the real binary.
        alias git='python3 /path/to/agent-guard.py --exec git'
        alias gh='python3 /path/to/agent-guard.py --exec gh'

        # As a wrapper script named 'git' earlier on $PATH than the real one.
        # It MUST exec the real git by absolute path — otherwise --exec would
        # re-resolve the bare name 'git' through $PATH, find this wrapper again,
        # and loop. Adjust the path to your real git.
        #!/usr/bin/env bash
        exec python3 /path/to/agent-guard.py --exec /usr/bin/git "$@"

    On allow, ``argv[0]`` is passed to :func:`os.execvp`, which resolves a bare
    name through ``$PATH``; pass an absolute path when a same-named wrapper
    shadows the real binary (see above). As a backstop, runaway self-re-entry is
    bounded by ``_EXEC_DEPTH_MAX`` and turned into a clear error rather than an
    unbounded loop.

    **Fail-open on decision, like every other entry point:** if the guard
    engine itself errors (a :func:`dispatch` exception) the command is still
    executed. Invoking with no command is a usage error (``USAGE_EXIT``).
    """
    if not argv:
        sys.stderr.write("agent-guard --exec: no command specified\n")
        return USAGE_EXIT
    command = shlex.join(argv)
    cwd = os.getcwd()
    try:
        reason = dispatch(command, cwd)
    except Exception as exc:  # fail-open: a guard glitch never blocks the user
        sys.stderr.write(f"agent-guard --exec: guard engine error, allowing: {exc}\n")
        reason = None
    if reason:
        sys.stderr.write(f"agent-guard: {reason}\n")
        return DENY_EXIT
    # Backstop against a same-named PATH wrapper re-resolving into agent-guard.
    depth = 0
    try:
        depth = int(os.environ.get(_EXEC_DEPTH_VAR, "0"))
    except ValueError:
        depth = 0
    if depth >= _EXEC_DEPTH_MAX:
        sys.stderr.write(
            "agent-guard --exec: refusing to exec — self-re-entry depth "
            f"({depth}) exceeded. A PATH wrapper is re-resolving the bare "
            "command name back to agent-guard; point it at the real binary by "
            "absolute path.\n"
        )
        return 1
    os.environ[_EXEC_DEPTH_VAR] = str(depth + 1)
    # execvp replaces the process image on success; on failure it raises OSError
    # and control falls through to the explicit return below.
    try:
        os.execvp(argv[0], argv)
    except OSError as exc:
        sys.stderr.write(f"agent-guard --exec: {exc}\n")
    return 1


def cli(argv: list[str] | None = None) -> int:
    """Route to the harness adapter named on the command line.

    No argument → inspect the parsed ``PreToolUse`` payload shape: Grok's
    camelCase ``toolName`` / ``toolInput`` routes to :func:`_grok_event`;
    Claude Code's snake_case ``tool_name`` / ``tool_input`` routes to
    :func:`_claude_event`.
    ``--opencode`` → the OpenCode adapter (:func:`opencode_main`).
    ``--pi`` → the Pi extension, which uses the same ``{"command", "cwd"}``
    transport (:func:`opencode_main`).
    ``--kiro`` → the Kiro CLI adapter (:func:`kiro_main`).
    ``--antigravity`` → the Antigravity adapter (:func:`antigravity_main`).
    ``--copilot`` → the Copilot CLI adapter (:func:`copilot_main`).
    ``--codex`` → the Codex native hook adapter (:func:`codex_main`).
    ``--grok`` → the Grok Build adapter (:func:`grok_main`).
    ``--junie`` → the Junie CLI adapter (:func:`junie_main`).
    ``--check <cmd…>`` → harness-neutral check-only (:func:`check_main`).
    ``--exec <cmd…>`` → harness-neutral check-then-exec (:func:`exec_main`).

    A single self-contained file thus serves every wired harness, so
    ``/magpie-setup`` ships one script and each harness (or wrapper) points its
    own hook at it.
    """
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "--codex":
        return codex_main()
    if args and args[0] in ("--opencode", "--pi"):
        return opencode_main()
    if args and args[0] == "--kiro":
        return kiro_main()
    if args and args[0] == "--antigravity":
        return antigravity_main()
    if args and args[0] == "--copilot":
        return copilot_main()
    if args and args[0] == "--grok":
        return grok_main()
    if args and args[0] == "--junie":
        return junie_main()
    if not args:
        try:
            event = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            return ALLOW_EXIT
        if isinstance(event, dict) and event.get("toolName") == "run_terminal_command":
            return _grok_event(event)
        return _claude_event(event)
    if args and args[0] == "--check":
        return check_main(args[1:])
    if args and args[0] == "--exec":
        return exec_main(args[1:])
    return main()


_MIN_PYTHON = (3, 11)
_REEXEC_VAR = "_AGENT_GUARD_REEXEC"


def _reexec_under_supported_python() -> None:
    """Re-run this script under a 3.11+ interpreter when ``python3`` is older.

    Hooks invoke the engine as a bare ``python3``, which resolves through the
    user's ``PATH`` — often an activated project virtualenv pinned to an older
    Python. Look for a versioned ``python3.N`` instead of failing; when there is
    none, exit 1 with an actionable message rather than an ImportError
    traceback on every shell call.
    """
    if sys.version_info[:2] >= _MIN_PYTHON:
        # Drop the marker so commands the guard runs (``--exec``) do not
        # inherit it and skip the search in a nested guard run.
        os.environ.pop(_REEXEC_VAR, None)
        return
    import shutil

    found = ".".join(map(str, sys.version_info[:3]))
    if os.environ.get(_REEXEC_VAR):
        sys.stderr.write(
            f"agent-guard: needs Python 3.11+, but the interpreter it re-ran under is "
            f"{found} ({sys.executable}). The guard is NOT running. "
            "Check which python3.N is first on PATH.\n"
        )
        raise SystemExit(1)
    # Probes python3.20 down to python3.11; raise the upper bound when 3.21 ships.
    for minor in range(20, _MIN_PYTHON[1] - 1, -1):
        interpreter = shutil.which(f"python3.{minor}")
        if interpreter:
            os.environ[_REEXEC_VAR] = "1"
            os.execv(interpreter, [interpreter, os.path.abspath(__file__), *sys.argv[1:]])
    sys.stderr.write(
        f"agent-guard: needs Python 3.11+, but python3 is {found} ({sys.executable}) "
        "and no python3.11+ is on PATH. The guard is NOT running. "
        "Install Python 3.11+ or put a newer python3 first on PATH.\n"
    )
    raise SystemExit(1)


if __name__ == "__main__":
    _reexec_under_supported_python()
    raise SystemExit(cli())
