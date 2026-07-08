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
* :func:`opencode_main` — OpenCode ``tool.execute.before`` plugin adapter
  (``--opencode``): reads ``{"command", "cwd"}`` on stdin, signals deny via a
  non-zero exit so the plugin can throw and abort the tool call.
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
   trailer (AGENTS.md: agents use ``Generated-by:``, never co-author).
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
deterministic guard **without re-wiring the hook**: drop an import-free
``*.py`` file into a discovered ``guards.d`` directory (the ``guards.d`` sibling
of this script, plus any dir in ``$MAGPIE_GUARD_DIRS``) that defines a
module-level ``guard(ctx)`` returning a deny string or ``None`` — see
``GuardContext`` and ``guards.d/no_verify_commit.py`` for the template. The hook
is wired once at setup; thereafter guards are added/removed by managing files in
``guards.d`` (which ``/magpie-setup`` keeps in sync from the snapshot).
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


class Segment:
    """One simple command from a (possibly compound) shell line.

    ``argv`` has leading ``NAME=value`` env assignments stripped into ``env``;
    ``raw`` is the original text of the segment (used for substring scans that
    survive heredocs, e.g. the Co-Authored-By trailer).
    """

    def __init__(self, tokens: list[str], raw: str) -> None:
        self.env: dict[str, str] = {}
        i = 0
        while i < len(tokens) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[i]):
            name, _, value = tokens[i].partition("=")
            self.env[name] = value
            i += 1
        argv = tokens[i:]
        # Normalise the command head to its basename so a path-qualified
        # invocation (`/usr/bin/git`, `./git`) is guarded identically to the
        # bare name. Guard rules only inspect argv[0] as a command *name*; the
        # real execution path is untouched (exec_main hands the original argv
        # to os.execvp). Prefix wrappers like `env git` / `command git` keep
        # argv[0] == "env" and remain a separate, pre-existing gap.
        if argv:
            argv[0] = os.path.basename(argv[0])
        self.argv: list[str] = argv
        self.raw = raw

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
                segments.append(Segment(current, command))
                current = []
        else:
            current.append(tok)
    if current:
        segments.append(Segment(current, command))
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
    """Return the value of ``-x``/``--xxx`` (space- or ``=``-separated) or None."""
    for i, tok in enumerate(argv):
        if tok in (short, long):
            return argv[i + 1] if i + 1 < len(argv) else None
        for prefix in (f"{long}=", f"{short}="):
            if tok.startswith(prefix):
                return tok[len(prefix) :]
    return None


def gh_subcommand(argv: list[str]) -> tuple[str, str] | None:
    """For an argv whose first token is ``gh``, return ``(group, sub)`` skipping
    global flags, e.g. ``(\"pr\", \"comment\")``. None if not a ``gh`` call."""
    if not argv or argv[0] != "gh":
        return None
    rest = [t for t in argv[1:] if not t.startswith("-")]
    if len(rest) >= 2:
        return rest[0], rest[1]
    return None


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


def guard_commit_trailer(seg: Segment, cwd: str | None) -> str | None:
    if seg.argv[:2] != ["git", "commit"]:
        return None
    if not re.search(r"co-authored-by:", seg.raw, re.IGNORECASE):
        return None
    if seg.override("MAGPIE_ALLOW_COAUTHOR"):
        return None
    return (
        "agent-guard[commit-trailer]: this commit message carries a 'Co-Authored-By:' "
        "trailer. Per AGENTS.md, agents are assistants, not authors — use a "
        "'Generated-by: <agent name and version>' trailer instead and remove the "
        "Co-Authored-By line. Override (not for AI co-authorship): MAGPIE_ALLOW_COAUTHOR=1."
    )


def guard_empty_rebase(seg: Segment, cwd: str | None) -> str | None:
    if seg.argv[:2] != ["git", "push"]:
        return None
    forced = any(
        t in ("-f", "--force") or t == "--force-with-lease" or t.startswith("--force-with-lease=")
        for t in seg.argv
    )
    if not forced:
        return None
    if seg.override("MAGPIE_ALLOW_EMPTY_PUSH"):
        return None

    # Resolve the source ref being pushed: last `src[:dst]` positional, else HEAD.
    positionals = [t for t in seg.argv[2:] if not t.startswith("-")]
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


# The framework's bundled guards — the universal `git` hygiene rules that apply
# to every project regardless of which skills are installed. Domain-specific
# guards are owned and contributed by the skills that need them (e.g. the
# mention + mark-ready guards live in `skills/pr-management-triage/guards/`, the
# security-language guard in `skills/security-issue-fix/guards/`); they are
# discovered at runtime from `guards.d` without editing this file or re-wiring
# the hook — see "Contributing guards" below.
BUILTIN_GUARDS: tuple[Callable[[Segment, str | None], str | None], ...] = (
    guard_commit_trailer,
    guard_empty_rebase,
)

# Only commands in these families are inspected; everything else takes the
# instant fast path. Bundled and contributed guards alike operate on the
# `gh` / `git` outbound/destructive surface.
GUARDED_HEADS = frozenset({"gh", "git"})

# Colon-separated extra guard directories (in addition to the default
# ``guards.d`` sibling of this script). Lets a checkout point the hook at
# skill-owned guard dirs without moving files.
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

    def opt(self, short: str, long: str) -> str | None:
        return _opt_value(self.argv, short, long)

    def gh_body(self, *, include_title: bool = False, read_files: bool = True) -> str:
        return gh_body_text(self.argv, include_title=include_title, read_files=read_files)

    def mentions(self, text: str) -> list[str]:
        return find_mentions(text)

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
    if len(seg.argv) > 1 and head in ("git", "gh"):
        kinds.add(f"{head}:{seg.argv[1]}")
    return kinds


def guard_dirs() -> list[Path]:
    """Directories scanned for contributed guards: ``$MAGPIE_GUARD_DIRS`` entries
    plus the ``guards.d`` sibling of this script."""
    dirs: list[Path] = []
    env = os.environ.get(GUARD_DIRS_ENV)
    if env:
        dirs.extend(Path(p) for p in env.split(os.pathsep) if p)
    dirs.append(Path(__file__).resolve().parent / "guards.d")
    seen: set[Path] = set()
    out: list[Path] = []
    for d in dirs:
        if d not in seen and d.is_dir():
            seen.add(d)
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


def dispatch(command: str, cwd: str | None = None) -> str | None:
    """Return a deny reason for ``command``, or None to allow it."""
    if not command:
        return None
    contributed: list[tuple[Callable[[GuardContext], str | None], set[str] | None]] | None = None
    for seg in split_segments(command):
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


def main() -> int:
    """Claude Code ``PreToolUse`` entry point (the default invocation)."""
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # Malformed event — never break the user's shell; allow.
    if not isinstance(event, dict) or event.get("tool_name") != "Bash":
        return 0
    command = str(event.get("tool_input", {}).get("command", ""))
    cwd = event.get("cwd")
    reason = dispatch(command, cwd if isinstance(cwd, str) else None)
    if reason:
        _emit_deny(reason)
    return 0


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

    No argument → the Claude Code ``PreToolUse`` hook (:func:`main`).
    ``--opencode`` → the OpenCode adapter (:func:`opencode_main`).
    ``--kiro`` → the Kiro CLI adapter (:func:`kiro_main`).
    ``--check <cmd…>`` → harness-neutral check-only (:func:`check_main`).
    ``--exec <cmd…>`` → harness-neutral check-then-exec (:func:`exec_main`).

    A single self-contained file thus serves every wired harness, so
    ``/magpie-setup`` ships one script and each harness (or wrapper) points its
    own hook at it.
    """
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "--opencode":
        return opencode_main()
    if args and args[0] == "--kiro":
        return kiro_main()
    if args and args[0] == "--check":
        return check_main(args[1:])
    if args and args[0] == "--exec":
        return exec_main(args[1:])
    return main()


if __name__ == "__main__":
    raise SystemExit(cli())
