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

"""Lint the agent-host sandbox configuration.

Implements mitigation M.29 from
docs/security/threat-model.md: every change to .claude/settings.json
must be acknowledged by an equivalent change to
tools/sandbox-lint/expected.json (the shipped baseline), and the
resulting configuration must satisfy the security invariants encoded
below.

The lint runs in CI on every PR that touches either file. Local edits
made by a maintainer outside a PR cannot be prevented; that residual
is documented in the threat model (residual #4, X3 - Sandbox bypass
via developer override).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from sandbox_lint.layers import GIT_HOME_NAME, LOCAL_DIR, RUN_DIR_NAME, run_dir_candidates, valid_worktree_id

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = Path(".claude/settings.json")
DEFAULT_EXPECTED = Path("tools/sandbox-lint/expected.json")
# The framework checkout splits its agent settings: the committed
# `.claude/settings.json` is the floor every contributor shares, and this
# template carries the rest, reconciled into each contributor's
# `.claude/settings.local.json`. Claude Code merges the two, so the baseline is
# compared against the merge. Projects without the template lint the file alone.
DEFAULT_LOCAL_TEMPLATE = Path("tools/agent-isolation/claude-settings.local.template.json")
# Which MCP tools each family calls. In the framework checkout every family is
# in use, so the floor's MCP allows must be exactly what this derives.
FAMILY_MCP_REGISTRY = Path("plugins/magpie-setup/skills/setup/family-mcp-allows.json")
# A project's own additions to EXCLUDED_COMMAND_ALLOWLIST, one entry per line,
# under its project root.
PROJECT_EXCLUSION_ALLOWLIST = Path(".apache-magpie-overrides/sandbox-lint/excluded-commands.txt")
# The layer actually in force on this machine. It may add personal entries
# (and MCP allows for families not adopted), but layered over the floor it must
# still pass every invariant and may not override a value the floor sets.
LOCAL_LIVE_SETTINGS = Path(".claude/settings.local.json")


def registry_errors(floor: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    """The floor's MCP allows against the registry for every family."""
    derived = {
        f"mcp__{server}__{tool}"
        for server, entry in (registry.get("servers") or {}).items()
        for tool in entry.get("tools", [])
    }
    present = {
        a for a in (floor.get("permissions", {}) or {}).get("allow", []) or [] if str(a).startswith("mcp__")
    }
    return [
        f"floor permissions.allow: missing {a!r} (in {FAMILY_MCP_REGISTRY})"
        for a in sorted(derived - present)
    ] + [f"floor permissions.allow: {a!r} is not in {FAMILY_MCP_REGISTRY}" for a in sorted(present - derived)]


# ---------------------------------------------------------------------------
# Security invariants
# ---------------------------------------------------------------------------
#
# These are hard rules that must hold regardless of legitimate edits to
# either file. They guard against the case where a future PR weakens
# both the live settings AND the baseline simultaneously without a
# threat-model review.

# allowRead must not contain any path that resolves to a credential
# store. Each entry is matched with normalised trailing-slash so that
# "~/.aws" and "~/.aws/" both fail.
FORBIDDEN_ALLOW_READ = {
    "~/",
    "/",
    "~/.aws",
    "~/.ssh",
    "~/.netrc",
    "~/.docker",
    "~/.kube",
    "~/.azure",
    "~/.config/gcloud",
    # The Gmail OAuth refresh token. The oauth-draft MCP server reads it
    # outside the sandbox; a readable token plus the Google API hosts
    # would let any unprompted sandboxed command use the user's Gmail.
    "~/.config/apache-magpie",
}

# allowWrite must be even more restrictive than allowRead. A path
# escaping into any of these would let an agent overwrite credentials
# or shell config.
FORBIDDEN_ALLOW_WRITE = {
    "~/",
    "/",
    "~/.config",
    "~/.config/gh",
    "~/.config/apache-magpie",
    "~/.gnupg",
    "~/.ssh",
    "~/.aws",
    "~/.docker",
    "~/.kube",
}

# Read-only vetted ops must never prompt: bulk skills call the read
# dispatcher from background gatherer agents, which cannot surface a prompt,
# so a prompt there is a silent denial. These invariants apply whenever the
# settings carry any vetted-op rule. The `~` base is the only spelling the
# skills use, and the agent-guard `vetted-ops-spelling` guard refuses others.
VETTED_OPS_BASE = "~/.claude/magpie/vetted-ops"
VETTED_OP_READ_LAUNCHERS = ("uv run --project", "uvx --from")
REQUIRED_VETTED_OP_READ_ALLOW = tuple(
    f"Bash({launcher} {VETTED_OPS_BASE} vetted-op-read *)" for launcher in VETTED_OP_READ_LAUNCHERS
)
# Sample read commands an ask rule is matched against, for both launchers and
# both bases: the literal `~`, and a resolved absolute home, which an agent
# without the spelling guard may still produce.
VETTED_OP_READ_SAMPLE_COMMANDS = tuple(
    f"{launcher} {base} vetted-op-read --caller sandbox-lint pr-view"
    for launcher in VETTED_OP_READ_LAUNCHERS
    for base in (VETTED_OPS_BASE, "/home/sandbox-lint/.claude/magpie/vetted-ops")
)
# Spellings that name a dispatcher: `vetted-op ` carries its trailing space so
# the `vetted-ops` path segment alone does not count.
VETTED_OP_DISPATCHER_NAMES = ("vetted-op-read", "vetted-op-tracker", "vetted-op ")
# The tamper protection that makes the unprompted read safe to allow.
REQUIRED_VETTED_OPS_DENY = (
    "Edit(~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/**)",
    "Edit(~/.claude/magpie/**)",
    "Edit(.apache-magpie-overrides/tools/vetted-ops/**)",
    # The same policy in a maintainer's personal layer (a project that has not
    # adopted Magpie): inside the git directory (`.git/**` also covers a
    # submodule's `.git/modules/<name>/`) or the Subversion one, or the legacy
    # in-tree layer. Absolute globs, since a linked worktree's git directory
    # lives outside it. vetted-ops reads a personal policy only in these shapes.
    "Edit(//**/.git/**/apache-magpie/tools/vetted-ops/**)",
    "Edit(//**/.svn/apache-magpie/tools/vetted-ops/**)",
    "Edit(//**/.apache-magpie-local/tools/vetted-ops/**)",
)

# permissions.deny must contain at least these entries verbatim. Each
# corresponds to an exfiltration vector documented in the threat model.
REQUIRED_PERMISSIONS_DENY = {
    "Read(~/.aws/**)",
    "Read(~/.ssh/**)",
    "Read(~/.netrc)",
    "Read(~/.docker/**)",
    "Read(~/.kube/**)",
    "Read(~/.config/gh/**)",
    "Read(~/.config/apache-magpie/**)",
    # The user's confirmations of a tracker's custom body parser, which
    # vetted operations then run outside the sandbox: the agent's own file
    # tools must not be able to write one.
    "Edit(~/.config/apache-magpie/local-tracker-parsers.json)",
    "Read(~/.config/gcloud/**)",
    # The host-only uv config: it moves the cache uv uses outside the sandbox
    # (hooks, MCP servers, the excluded uvx / uv run commands) to a directory
    # the sandbox cannot write. Unreadable inside the sandbox, so sandboxed uv
    # keeps its own writable default cache; never editable by the agent.
    "Read(~/.config/uv/uv.toml)",
    "Edit(~/.config/uv/**)",
    "Read(~/.azure/**)",
    "Read(//**/.env)",
    "Read(//**/.env.local)",
    "Read(//**/.env.*.local)",
    "Bash(curl *)",
    "Bash(wget *)",
    "Bash(aws *)",
    "Bash(gcloud *)",
    "Bash(az *)",
    "Bash(kubectl *)",
}

# Hook managers (tools/hook-manager/registry.json): (tool, home env var,
# default home, sandbox home, config files, nested configs count, hook marker).
# The default home is where the hooks of commits made in a terminal run a
# manager's environments outside the sandbox. It is per-user, shared by every
# project, so sandboxed commands may never edit it, whatever the project uses.
# A project that uses the manager also gives sandboxed runs a home of their own
# through env.<var>; one that does not needs no env.<var>, since its sandboxed
# runs of the manager then fail on the denied default home.
# BEGIN generated by tools/dev/sync-hook-managers.py; do not edit
HOOK_MANAGER_HOMES = (
    (
        "prek",
        "PREK_HOME",
        "~/.cache/prek",
        "~/.cache/prek-sandbox",
        ("prek.toml", ".pre-commit-config.yaml", ".pre-commit-config.yml"),
        True,
        "prek",
    ),
)
# END generated by tools/dev/sync-hook-managers.py
REQUIRED_PERMISSIONS_DENY |= {f"Edit({h[2]}/**)" for h in HOOK_MANAGER_HOMES}

# denyRead must contain ~/ as a base deny. Without it, allowRead would
# operate over the full filesystem instead of being an inclusion list
# carved out of a denied home directory.
REQUIRED_DENY_READ = {"~/"}

# Host sockets that `sandbox.network.allowAllUnixSockets: true` puts in reach
# of every sandboxed command unless denyRead hides their paths: the container
# daemons (host root through the daemon), the per-user runtime directory (the
# systemd user manager over `bus` and `systemd/private` runs commands outside
# the sandbox; rootless Podman; editor askpass sockets), the system bus, X11,
# and WSL's interop and WSLg sockets. Claude Code skips a denyRead path the
# host lacks, so the full list is safe everywhere. `<uid>` is the current
# user's uid.
ALL_UNIX_SOCKETS_DENY_READ = (
    "/run/docker.sock",
    "/var/run/docker.sock",
    "/run/docker-cli.sock",
    "/run/podman",
    "/run/user/<uid>",
    "/run/dbus",
    "/tmp/.X11-unix",
    "/run/WSL",
    "/mnt/wslg",
)

# Settings that switch a control off wholesale, whichever layer sets them. A
# local file may add personal entries; it may not add one of these.
#
# Commands that run whatever follows them: excluding one from the sandbox (or
# excluding "*") runs arbitrary code outside it.
ANY_COMMAND_LAUNCHERS = frozenset(
    {
        "bash", "sh", "zsh", "dash", "ksh", "fish", "csh", "tcsh", "busybox",
        "env", "sudo", "doas", "xargs", "eval", "exec", "command", "source", ".",
        "nohup", "nice",
        "timeout", "time", "watch", "setsid", "stdbuf", "flock", "script",
        "npx", "bunx", "deno", "bun", "pwsh", "powershell", "osascript",
        "awk", "gawk", "nawk", "mawk", "tclsh", "lua", "Rscript",
    }
)  # fmt: skip
# The only commands that may run outside the sandbox. Recognising commands that
# run anything (below) cannot be complete: `find -exec`, `git -c`, `make` and
# many more run their arguments. An exclusion therefore has to be one of these,
# or a narrowing of one (`gh auth *` under `gh *`); a project adds its own in
# PROJECT_EXCLUSION_ALLOWLIST, where they still pass the runs-anything check.
EXCLUDED_COMMAND_ALLOWLIST = frozenset(
    {
        "gh *",
        "roborev *",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read *",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker *",
        "uvx --from ~/.claude/magpie/vetted-ops vetted-op-read *",
        "uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker *",
        "uvx --from ~/.claude/magpie/adversarial-review adversarial-review *",
        "~/.claude/scripts/magpie-run-evals.sh *",
    }
)
# Interpreters, matched with any version suffix (`python3.12`, `node22`).
_VERSIONED_INTERPRETER = re.compile(r"(python|pypy|node|ruby|perl|php)[0-9.]*")
_ENV_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
# Package managers whose subcommands fetch or run code (`npm exec`, `pnpm dlx`,
# install hooks, project scripts); only these read-only ones stay legal.
_PACKAGE_MANAGER_READS = {
    "npm": {"--version", "-v", "--help", "ls", "list", "view", "outdated", "audit"},
    "pnpm": {"--version", "-v", "--help", "ls", "list", "view", "outdated", "audit"},
    "yarn": {"--version", "-v", "--help", "list", "info", "outdated", "audit"},
    "pipx": {"--version", "--help", "-h", "list", "environment"},
}
# Where the sandbox lets every command write, whatever allowWrite says.
_IMPLICIT_WRITABLE = ("/tmp", "/private/tmp", "/var/folders", "/private/var/folders")


def uses_hook_manager(
    project_root: Path | None, config_files: tuple[str, ...], nested: bool, marker: str
) -> bool:
    """Whether the project uses a hook manager (tools/hook-manager/README.md#detection).

    It does when one of the manager's config files sits at its root, is
    tracked anywhere below it (for a manager with nested workspace configs),
    or one of its installed git hooks runs the manager (an install with a
    custom config path). With no project to look at, every manager counts:
    the settings may serve a project that uses it.
    """
    if project_root is None:
        return True
    if any((project_root / name).is_file() for name in config_files):
        return True
    git = ["git", "-C", str(project_root)]
    if nested:
        tracked = _git_output([*git, "ls-files", "-z", "--", *(f":(glob)**/{name}" for name in config_files)])
        if tracked:
            return True
    common = _git_output([*git, "rev-parse", "--path-format=absolute", "--git-common-dir"]).strip()
    hooks = Path(common) / "hooks" if common else project_root / ".git" / "hooks"
    try:
        candidates = [h for h in hooks.iterdir() if h.is_file() and not h.name.endswith(".sample")]
    except OSError:
        return False
    for hook in candidates:
        try:
            if marker in hook.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            continue
    return False


def _git_output(cmd: list[str]) -> str:
    """A git command's stdout, or "" when git is missing or the command fails."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _expand(path: str, project_root: Path | None) -> str | None:
    """``path`` as an absolute, normalised string, or None when it is relative
    and there is no project root to anchor it to."""
    expanded = os.path.expanduser(path)
    if not os.path.isabs(expanded):
        if project_root is None:
            return None
        expanded = os.path.join(str(project_root), expanded)
    return os.path.normpath(expanded)


def _is_writable(path: str, writable: tuple[str, ...]) -> bool:
    return any(path == root or path.startswith(root.rstrip("/") + "/") for root in writable)


def _writable_roots(allow_write: list[str], project_root: Path | None) -> tuple[str, ...]:
    """The directories the agent can write to: the sandbox's ``allowWrite``
    entries (and the working directories, which the sandbox also makes
    writable) and the project itself."""
    entries = [e for e in allow_write if isinstance(e, str)] + ["."]
    roots = tuple(r for r in (_expand(e, project_root) for e in entries) if r is not None)
    return roots + _IMPLICIT_WRITABLE


def _is_outside_pin(path: str, writable: tuple[str, ...] = ()) -> bool:
    """A path the agent cannot edit: `~/...` or absolute, and not under a
    directory the agent can write to.

    A relative path (`.`, `./x`) names something in the checkout, and uv builds
    a pinned project before running it, so its build backend and entry points
    are the agent's. So is a script or project under ``allowWrite``.
    """
    if not (path.startswith("~/") or path.startswith("/")) or ".." in path.split("/"):
        return False
    return not _is_writable(os.path.normpath(os.path.expanduser(path)), writable)


def _read_project_exclusions(project_root: Path | None) -> tuple[frozenset[str], str | None]:
    """The project's own allowed exclusions, and an error when its file exists
    but cannot be read."""
    if project_root is None:
        return frozenset(), None
    path = project_root / PROJECT_EXCLUSION_ALLOWLIST
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return frozenset(), None
    except (OSError, UnicodeDecodeError) as exc:
        return frozenset(), f"{PROJECT_EXCLUSION_ALLOWLIST}: cannot be read ({exc})"
    return frozenset(s for s in (line.strip() for line in lines) if s and not s.startswith("#")), None


def _is_allowed_exclusion(entry: str, allowed: frozenset[str]) -> bool:
    """``entry`` is an allowed exclusion or a narrowing of one: the same
    command with more of its arguments named (``gh auth *`` under ``gh *``)."""
    text = entry.strip()
    # Claude Code's legacy prefix form `cmd:*` means the same as `cmd *`.
    if text.endswith(":*"):
        text = text[:-2] + " *"
    for pattern in allowed:
        if text == pattern:
            return True
        if pattern.endswith(" *") and (text == pattern[:-2] or text.startswith(pattern[:-1])):
            return True
    return False


def _has_glob(word: str) -> bool:
    return any(c in word for c in "*?[")


def _runs_anything(command: str, writable: tuple[str, ...] = ()) -> bool:
    """Whether ``command`` (a rule pattern) can launch arbitrary code.

    A shell or interpreter by name or path, a bare ``*``, an option where a
    command should be, or a package runner not pinned to a path. A pinned
    runner (``uv run --project <path> ...``, ``uvx --from <path> ...`` with an
    absolute or ``~/`` path, the vetted-ops forms) is judged by the command it
    runs, so wrapping a shell in one does not help. Any other ``uv``
    subcommand counts, since sync, lock, pip and build run a project's build
    backend. A command word that is a path runs that file, so it counts unless
    the path is outside the checkout and every ``writable`` directory.
    """
    text = command.strip()
    # Claude Code's legacy prefix form `cmd:*` means the same as `cmd *`.
    if text.endswith(":*"):
        text = text[:-2] + " *"
    words = text.split()
    # `LC_ALL=C *` runs whatever follows the assignments.
    while words and _ENV_ASSIGNMENT.match(words[0]):
        words = words[1:]
    # A glob in the command word (`bash*`, `b*`) matches a launcher too.
    if not words or words[0].startswith("-") or _has_glob(words[0]):
        return True
    head = words[0].rstrip(":").rsplit("/", 1)[-1]
    if "/" in words[0] and not _is_outside_pin(words[0].rstrip(":"), writable):
        return True
    # Likewise in a runner's subcommand or pin position (`uv run*`, `uvx*`,
    # `uv run --proj*`); a glob in a plain subcommand's arguments is harmless.
    if head in ("uv", "uvx", "pipx") and len(words) > 1 and _has_glob(words[1]):
        return True
    if head == "uv" and len(words) > 2 and words[1] in ("run", "tool") and _has_glob(words[2]):
        return True
    # Global options can precede the subcommand (`uv --offline run *`), so an
    # option where the subcommand belongs counts as unpinned. Only the bare
    # informational forms (`uv --version`) stay legal.
    if head == "uv" and len(words) > 1 and words[1].startswith("-"):
        return not (len(words) == 2 and words[1] in ("--version", "-V", "--help", "-h"))
    if head == "uv" and len(words) > 2 and words[1] == "tool" and words[2].startswith("-"):
        return True
    if head in ANY_COMMAND_LAUNCHERS or _VERSIONED_INTERPRETER.fullmatch(head):
        return True
    if head == "uv":
        # Every uv subcommand but `run` with an outside pin can execute code
        # from a project the agent edits (sync, lock, pip, build run its build
        # backend), so only that form and the bare informational one are legal.
        if len(words) == 2 and words[1] in ("--version", "-V", "--help", "-h"):
            return False
        if len(words) < 5 or words[1:3] != ["run", "--project"] or not _is_outside_pin(words[3], writable):
            return True
        return _runs_anything(" ".join(words[4:]), writable)
    if head == "uvx":
        if len(words) < 4 or words[1] != "--from" or not _is_outside_pin(words[2], writable):
            return True
        return _runs_anything(" ".join(words[3:]), writable)
    if head in _PACKAGE_MANAGER_READS:
        return not (len(words) == 2 and words[1] in _PACKAGE_MANAGER_READS[head])
    return False


# ---------------------------------------------------------------------------
# Path normalisation
# ---------------------------------------------------------------------------


def _normalise(path: str) -> str:
    """Strip all trailing slashes so '~/.aws' and '~/.aws//' compare equal.

    The sandbox treats every trailing-slash count as the same directory;
    the validator must too, otherwise the forbidden-list could be bypassed
    by a multi-slash variant.
    """
    return path.rstrip("/") or "/"


def _normalised_set(paths: list[str]) -> set[str]:
    return {_normalise(p) for p in paths}


def _deny_covers(entry: str, target: str) -> bool:
    """Whether a denyRead ``entry`` hides ``target``: the entry is the target
    or an ancestor of it, segment by segment (globs allowed; a ``<uid>``
    target segment stands for the current user's uid, so ``/run/user/0``
    does not cover it for uid 1000)."""
    expanded = os.path.expanduser(entry)
    if not os.path.isabs(expanded):
        return False
    entry_parts = [p for p in os.path.normpath(expanded).split("/") if p]
    target_parts = [p for p in target.split("/") if p]
    return len(entry_parts) <= len(target_parts) and all(
        fnmatch.fnmatchcase(str(os.getuid()) if t == "<uid>" else t, e)
        for e, t in zip(entry_parts, target_parts, strict=False)
    )


# ---------------------------------------------------------------------------
# Deep diff — set semantics on known list-typed keys, equality elsewhere
# ---------------------------------------------------------------------------

# Keys whose values are lists treated as sets (order/duplicates do not
# matter for security semantics).
SET_LIST_KEYS = {
    "denyRead",
    "allowRead",
    "allowWrite",
    "allowedDomains",
    "excludedCommands",
    "allow",
    "deny",
    "ask",
}


def deep_diff(actual: Any, expected: Any, path: str = "$") -> list[str]:
    """Return human-readable diff lines; empty list means the two trees match."""
    diffs: list[str] = []
    if type(actual) is not type(expected):
        return [
            f"{path}: type mismatch "
            f"(settings has {type(actual).__name__}, expected has {type(expected).__name__})"
        ]
    if isinstance(actual, dict):
        assert isinstance(expected, dict)
        keys = sorted(set(actual) | set(expected))
        for k in keys:
            if k not in actual:
                diffs.append(f"{path}.{k}: missing in settings (present in expected)")
            elif k not in expected:
                diffs.append(f"{path}.{k}: extra in settings (not in expected)")
            else:
                diffs.extend(deep_diff(actual[k], expected[k], f"{path}.{k}"))
    elif isinstance(actual, list):
        assert isinstance(expected, list)
        leaf = path.rsplit(".", 1)[-1]
        if leaf in SET_LIST_KEYS:
            sa, se = set(actual), set(expected)
            for x in sorted(sa - se):
                diffs.append(f"{path}: extra entry in settings: {x!r}")
            for x in sorted(se - sa):
                diffs.append(f"{path}: missing entry in settings: {x!r}")
        elif actual != expected:
            diffs.append(f"{path}: list mismatch (settings={actual!r}, expected={expected!r})")
    elif actual != expected:
        diffs.append(f"{path}: settings={actual!r} expected={expected!r}")
    return diffs


# ---------------------------------------------------------------------------
# Floor + local template
# ---------------------------------------------------------------------------


def merge_layers(floor: dict[str, Any], local: dict[str, Any]) -> dict[str, Any]:
    """Merge settings the way Claude Code layers the local file over the project one.

    Lists concatenate (de-duplicated, floor first); objects merge recursively.
    A scalar both layers set is left to ``split_errors`` to report, so the
    floor's value is kept here.
    """
    merged: dict[str, Any] = dict(floor)
    for key, value in local.items():
        base = merged.get(key)
        if isinstance(base, dict) and isinstance(value, dict):
            merged[key] = merge_layers(base, value)
        elif isinstance(base, list) and isinstance(value, list):
            combined = list(base)
            combined.extend(item for item in value if item not in combined)
            merged[key] = combined
        elif key not in merged:
            merged[key] = value
    return merged


def split_errors(floor: dict[str, Any], local: dict[str, Any]) -> list[str]:
    """Rules that keep the floor/local split meaningful.

    - The floor holds every ``deny`` and ``ask``: a local rule can only add, and
      nobody's local file can weaken a protective rule.
    - The floor's only ``allow`` entries are MCP tools, derived from the
      families the project adopted (``setup`` writes them), and the
      ``vetted-op-read`` pair a vetted-ops project must never be prompted for;
      every other allow is a local convenience.
    - The local template carries no MCP allows (they come from the family
      registry for families installed on one machine) and no scalar the floor
      sets: a local scalar overrides the committed one, so a local
      ``sandbox.enabled: false`` would switch the sandbox off.
    """
    errors: list[str] = []
    perms_floor = floor.get("permissions", {}) or {}
    perms_local = local.get("permissions", {}) or {}
    for rule in perms_floor.get("allow", []) or []:
        if not (
            isinstance(rule, str) and (rule.startswith("mcp__") or rule in REQUIRED_VETTED_OP_READ_ALLOW)
        ):
            errors.append(
                f"floor permissions.allow: {rule!r} is neither a derived MCP tool nor the vetted-op-read "
                "pair; move it to the local template"
            )
    for key in ("deny", "ask"):
        for rule in perms_local.get(key, []) or []:
            errors.append(f"local template permissions.{key}: {rule!r} belongs in the floor")
    for rule in perms_local.get("allow", []) or []:
        if isinstance(rule, str) and rule.startswith("mcp__"):
            errors.append(
                f"local template permissions.allow: {rule!r} is an MCP tool; "
                "MCP allows are derived from the family registry"
            )
    errors.extend(override_errors(floor, local, label="local template"))
    return errors


def override_errors(
    floor: dict[str, Any], local: dict[str, Any], *, label: str, path: str = "$"
) -> list[str]:
    """Scalars the local layer sets differently from the floor.

    Claude Code lets a local scalar replace the committed one, so a different
    value is an override of a control (``sandbox.enabled: false`` switches the
    sandbox off); an equal one, as ``/sandbox`` may write, is harmless.
    """
    errors: list[str] = []
    for key, value in local.items():
        if key not in floor or key == "$schema":
            continue
        base = floor[key]
        if isinstance(base, dict) and isinstance(value, dict):
            errors.extend(override_errors(base, value, label=label, path=f"{path}.{key}"))
        elif not (isinstance(base, list) and isinstance(value, list)) and value != base:
            errors.append(f"{label} {path}.{key}: overrides a value the floor sets")
    return errors


# ---------------------------------------------------------------------------
# Invariant checks
# ---------------------------------------------------------------------------


def check_invariants(settings: dict[str, Any], project_root: Path | None = None) -> list[str]:
    """Return list of invariant violations; empty list means OK.

    ``project_root``, when given, anchors the gateway-run-directory
    exemption for daemon-socket entries in ``allowUnixSockets``: an entry is
    exempt only when it resolves to exactly
    ``<project_root>/.apache-magpie-local/run/<name>`` (adopted project) or
    ``<git-common-dir>/apache-magpie/run/<worktree-id>/<name>`` (not adopted;
    ``<worktree-id>`` is ``main`` or the linked worktree's gitdir name; the common
    directory is ``.git`` in a main checkout and the main checkout's
    ``.git`` in a linked worktree) -- the two places the container gateway
    serves from by default (``layers.run_dir_candidates``). Without a
    ``project_root`` (the default), the exemption falls back to an
    unanchored suffix match on the parent directory string, and a decoy
    path such as ``/tmp/evil/.apache-magpie-local/run/podman.sock`` is
    indistinguishable from a legitimate project-scoped socket -- both end
    in the same suffix -- so it is accepted. This residual is documented
    in ``tools/sandbox-lint/README.md`` under Residual risk. The CLI entry
    point always knows the project root and passes it; only a caller that
    invokes this function directly without one inherits the residual.

    The anchored comparison itself is lexical (``os.path.normpath`` on the
    two path strings), not a filesystem-resolved one: it never calls
    ``Path.resolve()`` or otherwise touches disk. A ``project_root`` (or an
    ``allowUnixSockets`` entry) reached through a symlink can therefore make
    a legitimate absolute entry compare as off-root and get flagged even
    though it is fine on disk. This fails closed -- a false positive here is
    a lint the maintainer has to explain, not a bypassed daemon-socket
    check -- so it is an accepted trade-off, not a bug to silence with
    ``resolve()``.
    """
    errors: list[str] = []

    sandbox = settings.get("sandbox")
    if not isinstance(sandbox, dict):
        return ["sandbox: missing or not an object"]

    if sandbox.get("enabled") is not True:
        errors.append("sandbox.enabled: must be true")

    fs_settings = sandbox.get("filesystem")
    perms_settings = settings.get("permissions")
    work_dirs = (
        (perms_settings.get("additionalDirectories", []) or []) if isinstance(perms_settings, dict) else []
    )
    writable = _writable_roots(
        ((fs_settings.get("allowWrite", []) or []) if isinstance(fs_settings, dict) else [])
        + list(work_dirs),
        project_root,
    )
    # The fixed path every vetted-ops and adversarial-review exclusion runs from.
    magpie_dir = os.path.normpath(os.path.expanduser("~/.claude/magpie"))
    for entry in work_dirs:
        expanded = _expand(entry, project_root) if isinstance(entry, str) else None
        if expanded is not None and (
            _is_writable(magpie_dir, (expanded,)) or _is_writable(expanded, (magpie_dir,))
        ):
            errors.append(
                f"permissions.additionalDirectories: {entry!r} makes the vetted-ops checkout writable, "
                "and its commands run outside the sandbox; remove it (sandbox-add-project-root.sh "
                "removes the ~/.claude/magpie entry it once added; remove any other by hand)"
            )

    # uv's interpreters, tool venvs and credentials, which uv runs outside the
    # sandbox for hooks, MCP servers and the excluded uvx / uv run commands: a
    # sandboxed command able to write there plants code that runs unsandboxed.
    uv_data_dir = os.path.normpath(os.path.expanduser("~/.local/share/uv"))
    for key, entries in (
        (
            "sandbox.filesystem.allowWrite",
            (fs_settings.get("allowWrite", []) or []) if isinstance(fs_settings, dict) else [],
        ),
        ("permissions.additionalDirectories", work_dirs),
    ):
        for entry in entries:
            expanded = _expand(entry, project_root) if isinstance(entry, str) else None
            if expanded is not None and (
                _is_writable(uv_data_dir, (expanded,)) or _is_writable(expanded, (uv_data_dir,))
            ):
                errors.append(
                    f"{key}: {entry!r} makes ~/.local/share/uv writable, and the interpreters and tools "
                    "under it run outside the sandbox; keep it in allowRead only "
                    "(sandbox-add-project-root.sh removes the write it once added)"
                )

    # A sandboxed hook manager must not share the home a terminal's git hooks
    # run from: env.<HOME> (which only Claude Code's own commands see) points
    # it at a directory of its own, outside the default home. Only for the
    # managers the project uses; the default-home deny is required for every
    # manager (REQUIRED_PERMISSIONS_DENY).
    env = settings.get("env")
    for tool, var, default, sandbox_home, files, nested, marker in HOOK_MANAGER_HOMES:
        if not uses_hook_manager(project_root, files, nested, marker):
            continue
        given = env.get(var) if isinstance(env, dict) else None
        default_home = os.path.normpath(os.path.expanduser(default))
        expanded_home = _expand(given, project_root) if isinstance(given, str) and given else None
        if expanded_home is None:
            errors.append(
                f"env.{var}: missing; set it to {sandbox_home} so sandboxed {tool} does not "
                "write the hook environments a terminal's commits run outside the sandbox"
            )
        elif _is_writable(expanded_home, (default_home,)) or _is_writable(default_home, (expanded_home,)):
            errors.append(
                f"env.{var}: {given!r} overlaps {default}, the home a terminal's git hooks "
                f"run from outside the sandbox; use {sandbox_home}"
            )

    # Same matching as a Bash allow rule (see `permissions.allow` below): a `*`
    # before the end also matches options spliced in at that position, and an
    # excluded command runs outside the sandbox once approved (the
    # adversarial-review exclusion once globbed the plugin version this way).
    project_exclusions, project_exclusions_error = _read_project_exclusions(project_root)
    if project_exclusions_error:
        errors.append(project_exclusions_error)
    allowed_exclusions = EXCLUDED_COMMAND_ALLOWLIST | project_exclusions
    for entry in sandbox.get("excludedCommands", []) or []:
        if isinstance(entry, str) and not _is_allowed_exclusion(entry, allowed_exclusions):
            errors.append(
                f"sandbox.excludedCommands: {entry!r} is not on the exclusion allowlist; an excluded "
                "command runs outside the sandbox, so only the framework's own exclusions are accepted. "
                f"Add it to {PROJECT_EXCLUSION_ALLOWLIST} once reviewed"
            )
        if isinstance(entry, str) and _runs_anything(entry, writable):
            errors.append(
                f"sandbox.excludedCommands: {entry!r} would run arbitrary commands outside the sandbox"
            )
        if isinstance(entry, str) and "*" in entry[:-1]:
            errors.append(
                f"sandbox.excludedCommands: {entry!r} has a '*' before the end of the command, "
                "so any options inserted at that position also run outside the sandbox; "
                "name the exact value there and use '*' only at the end"
            )

    fs = sandbox.get("filesystem")
    if not isinstance(fs, dict):
        errors.append("sandbox.filesystem: missing or not an object")
    else:
        deny_read = _normalised_set(fs.get("denyRead", []) or [])
        for required in REQUIRED_DENY_READ:
            if _normalise(required) not in deny_read:
                errors.append(
                    f"sandbox.filesystem.denyRead: must contain {required!r} "
                    "(otherwise allowRead expands across the full filesystem)"
                )

        allow_read = _normalised_set(fs.get("allowRead", []) or [])
        for forbidden in FORBIDDEN_ALLOW_READ:
            if _normalise(forbidden) in allow_read:
                errors.append(
                    f"sandbox.filesystem.allowRead: must not contain {forbidden!r} (credential/root path)"
                )

        allow_write = _normalised_set(fs.get("allowWrite", []) or [])
        for forbidden in FORBIDDEN_ALLOW_WRITE:
            if _normalise(forbidden) in allow_write:
                errors.append(
                    f"sandbox.filesystem.allowWrite: must not contain {forbidden!r} "
                    "(would permit credential overwrite)"
                )
        for entry in allow_write - allow_read:
            errors.append(
                f"sandbox.filesystem.allowWrite: contains {entry!r} which is not in allowRead "
                "(allowWrite must be a subset of allowRead)"
            )
        # bubblewrap mounts a read-only allowRead parent over its writable
        # child, so every Bash call then fails creating its deny-write
        # placeholders ("Can't create file … Read-only file system"). Seen
        # under denyRead ~/; checked everywhere, failing closed.
        for read_entry in fs.get("allowRead", []) or []:
            parent = _expand(read_entry, project_root) if isinstance(read_entry, str) else None
            if parent is None or _is_writable(parent, writable):
                continue
            for write_entry in fs.get("allowWrite", []) or []:
                child = _expand(write_entry, project_root) if isinstance(write_entry, str) else None
                if child is not None and child.startswith(parent.rstrip("/") + "/"):
                    errors.append(
                        f"sandbox.filesystem.allowRead: {read_entry!r} is a parent of the allowWrite "
                        f"entry {write_entry!r}, which the sandbox then mounts read-only (seen under "
                        "denyRead ~/); list the specific directories under it instead"
                    )

    perms = settings.get("permissions")
    if not isinstance(perms, dict):
        errors.append("permissions: missing or not an object")
    else:
        deny = set(perms.get("deny", []) or [])
        for required in REQUIRED_PERMISSIONS_DENY:
            if required not in deny:
                errors.append(f"permissions.deny: must contain {required!r}")
        # Claude Code evaluates deny, then ask, then allow, and a matching ask
        # rule prompts even when a more specific allow rule also matches. A
        # catch-all gh ask rule therefore prompts on every read-only gh call
        # and silently defeats the read-only allow list; writes are listed
        # subcommand by subcommand instead.
        # A `*` in a Bash allow rule matches any characters, spaces included.
        # Anywhere but the end it therefore also matches options spliced in at
        # that position, which the rule then approves without a prompt (the
        # vetted-ops rules once globbed the plugin version this way).
        if perms.get("defaultMode") == "bypassPermissions":
            errors.append(
                "permissions.defaultMode: must not be 'bypassPermissions' (it switches every prompt off)"
            )
        for rule in perms.get("allow", []) or []:
            bare = isinstance(rule, str) and rule.replace(" ", "") == "Bash"
            inner = (
                rule[len("Bash(") : -1]
                if isinstance(rule, str) and rule.startswith("Bash(") and rule.endswith(")")
                else None
            )
            if bare or (inner is not None and _runs_anything(inner, writable)):
                errors.append(f"permissions.allow: {rule!r} approves every shell command without a prompt")
            if isinstance(rule, str) and rule.startswith("Bash(") and "*" in rule[:-2]:
                errors.append(
                    f"permissions.allow: {rule!r} has a '*' before the end of the command, "
                    "so it also approves any options inserted at that position; "
                    "name the exact value there and use '*' only at the end"
                )
        ask = set(perms.get("ask", []) or [])
        excluded = [e for e in sandbox.get("excludedCommands", []) or [] if isinstance(e, str)]
        errors.extend(_vetted_op_read_never_prompts(perms, ask, deny, excluded))
        if "Bash(gh *)" in ask:
            errors.append(
                "permissions.ask: must not contain 'Bash(gh *)' (ask beats allow "
                "regardless of specificity, so it prompts on every read-only gh call; "
                "list the gh write subcommands one by one)"
            )

    # A daemon socket (docker.sock, podman.sock, or a podman API socket such
    # as podman-machine-default-api.sock) grants the sandboxed agent direct
    # control of the container runtime -- equivalent to host root on most
    # setups. The container gateway (tools/container-gateway) is the only
    # sanctioned path: it enforces its own policy in front of the real
    # socket, and its sockets live under .apache-magpie-local/run/ (adopted
    # project) or <git-common-dir>/apache-magpie/run/<worktree-id>/ (not adopted), never
    # the daemon's own well-known path.
    for domain in settings.get("sandbox", {}).get("network", {}).get("allowedDomains", []) or []:
        if isinstance(domain, str) and domain.strip() in ("*", "*.*"):
            errors.append(f"sandbox.network.allowedDomains: {domain!r} opens egress to every host")
    for entry in settings.get("sandbox", {}).get("network", {}).get("allowUnixSockets", []):
        stripped = entry.rstrip("/")
        name = stripped.rsplit("/", 1)[-1]
        parent = stripped.rsplit("/", 1)[0] if "/" in stripped else ""
        # macOS's filesystem is case-insensitive, so the sandbox treats
        # "Docker.sock" the same as "docker.sock"; match names the same way.
        name_cf = name.casefold()
        is_daemon = name_cf in ("docker.sock", "podman.sock") or name_cf.endswith("-api.sock")
        if not is_daemon:
            continue
        if project_root is not None:
            parent_path = Path(parent) if parent else Path()
            if not parent_path.is_absolute():
                parent_path = project_root / parent_path
            expected_parents = run_dir_candidates(project_root)
            is_exempt = any(
                os.path.normpath(str(parent_path)) == os.path.normpath(str(expected))
                for expected in expected_parents
            )
        else:
            head, _, wid = parent.rpartition("/")
            is_exempt = parent.endswith(f"{LOCAL_DIR}/{RUN_DIR_NAME}") or (
                head.endswith(f"/{GIT_HOME_NAME}/{RUN_DIR_NAME}") and valid_worktree_id(wid)
            )
        if not is_exempt:
            errors.append(
                f"sandbox.network.allowUnixSockets: {entry} names a container daemon socket; "
                "route through the container gateway (<project>/.apache-magpie-local/run/*.sock, "
                "or <git-common-dir>/apache-magpie/run/<worktree-id>/*.sock when the project has not adopted Magpie) instead"
            )

    if settings.get("sandbox", {}).get("network", {}).get("allowAllUnixSockets") is True:
        deny_entries = [
            e for e in ((fs.get("denyRead", []) or []) if isinstance(fs, dict) else []) if isinstance(e, str)
        ]
        for target in ALL_UNIX_SOCKETS_DENY_READ:
            if not any(_deny_covers(e, target) for e in deny_entries):
                errors.append(
                    f"sandbox.network.allowAllUnixSockets: true lets every sandboxed command connect to "
                    f"{target}; add it (or its directory) to sandbox.filesystem.denyRead, see "
                    "docs/setup/secure-agent-setup.md#linux-needs-allowallunixsockets"
                )

    return errors


def _names_dispatcher(command: str) -> bool:
    return any(name in f"{command} " for name in VETTED_OP_DISPATCHER_NAMES)


def _bash_rule_matches(rule: str, command: str) -> bool:
    """Whether a `Bash` permission rule matches ``command`` (fnmatch-style)."""
    if rule == "Bash":
        return True
    if not (rule.startswith("Bash(") and rule.endswith(")")):
        return False
    pattern = rule[len("Bash(") : -1]
    if pattern.endswith(":*"):  # legacy prefix form
        pattern = pattern[:-2] + "*"
    return fnmatch.fnmatchcase(command, pattern)


def _vetted_op_read_never_prompts(
    perms: dict[str, Any], ask: set[str], deny: set[str], excluded: list[str]
) -> list[str]:
    """Violations of the never-prompt shape for the vetted-ops read dispatcher.

    Applies only when a `Bash(...)` permission rule or a
    ``sandbox.excludedCommands`` entry names a dispatcher. The defensive
    `Edit(...vetted-ops/**)` deny rules alone do not trigger it.
    """
    bash_rules = [
        r[len("Bash(") : -1]
        for key in ("allow", "ask", "deny")
        for r in perms.get(key, []) or []
        if isinstance(r, str) and r.startswith("Bash(") and r.endswith(")")
    ]
    if not any(_names_dispatcher(c) for c in [*bash_rules, *excluded]):
        return []
    errors: list[str] = []
    allow = set(perms.get("allow", []) or [])
    for required in REQUIRED_VETTED_OP_READ_ALLOW:
        if required not in allow:
            errors.append(
                f"permissions.allow: must contain {required!r} "
                "(a vetted-op-read call must never prompt; a background gatherer cannot answer it)"
            )
    for rule in sorted(ask):
        if any(_bash_rule_matches(rule, c) for c in VETTED_OP_READ_SAMPLE_COMMANDS):
            errors.append(
                f"permissions.ask: must not contain {rule!r} "
                "(ask beats allow, so every vetted-op-read call would prompt)"
            )
    if perms.get("blockReadsOutsideWorkingDirectories") is True:
        errors.append(
            "permissions.blockReadsOutsideWorkingDirectories: must not be true where vetted-ops is used "
            "(the read check cannot resolve the literal '~' the commands spell, so every call prompts)"
        )
    for required in REQUIRED_VETTED_OPS_DENY:
        if required not in deny:
            errors.append(
                f"permissions.deny: must contain {required!r} "
                "(tamper protection for the vetted-ops catalogue, fixed path and policy)"
            )
    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_json(p: Path) -> dict[str, Any]:
    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"sandbox-lint: file not found: {p}") from None
    except json.JSONDecodeError as e:
        raise SystemExit(f"sandbox-lint: invalid JSON in {p}: {e}") from None
    if not isinstance(data, dict):
        raise SystemExit(f"sandbox-lint: top-level value in {p} is not an object")
    return data


def _load_toml(p: Path) -> dict[str, Any]:
    try:
        with p.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise SystemExit(f"sandbox-lint: file not found: {p}") from None
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(f"sandbox-lint: invalid TOML in {p}: {e}") from None
    return data


def _lint_opencode(config_path: Path) -> int:
    """Lint an OpenCode opencode.json permission policy (invariants only)."""
    from sandbox_lint.opencode import check_opencode_invariants

    config = _load_json(config_path)
    errors = check_opencode_invariants(config)
    if not errors:
        print(f"sandbox-lint: OK ({config_path} permission policy satisfies the OpenCode invariants)")
        return 0
    print(f"sandbox-lint: OpenCode permission-policy violations in {config_path}:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


def _lint_kiro(config_path: Path) -> int:
    """Lint a Kiro CLI agent-config permission policy (invariants only)."""
    from sandbox_lint.kiro import check_kiro_invariants

    config = _load_json(config_path)
    errors = check_kiro_invariants(config)
    if not errors:
        print(f"sandbox-lint: OK ({config_path} permission policy satisfies the Kiro invariants)")
        return 0
    print(f"sandbox-lint: Kiro permission-policy violations in {config_path}:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


def _lint_codex(config_dir: Path, *, guard_from_plugin: bool = False) -> int:
    """Lint a project-scoped Codex sandbox + exec-policy profile."""
    from sandbox_lint.codex import check_codex_invariants

    config = _load_toml(config_dir / "config.toml")
    rules_path = config_dir / "rules" / "magpie.rules"
    try:
        rules_text = rules_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"sandbox-lint: file not found: {rules_path}") from None

    errors = check_codex_invariants(
        config, rules_text, guard_from_plugin=guard_from_plugin, repo_root=config_dir.resolve().parent
    )
    if not errors:
        print(f"sandbox-lint: OK ({config_dir} satisfies the Codex security invariants)")
        if guard_from_plugin:
            print("sandbox-lint: plugin guard not inspected; verify its registration and trust in /hooks")
        return 0
    print(f"sandbox-lint: Codex profile violations in {config_dir}:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


def _lint_gemini(config_dir: Path) -> int:
    """Check the committed Gemini profile; this does not inspect a live session."""
    from sandbox_lint.gemini import check_gemini_invariants

    errors = check_gemini_invariants(
        _load_json(config_dir / "settings.json"),
        _load_toml(config_dir / "policies" / "magpie.toml"),
    )
    if not errors:
        print(
            f"sandbox-lint: OK ({config_dir} satisfies the Gemini static profile checks; live enforcement not tested)"
        )
        return 0
    for error in errors:
        print(f"sandbox-lint: {error}", file=sys.stderr)
    return 1


def _lint_any_harness(framework_root: Path | None) -> int:
    """Validate the harness-neutral OS-level security posture.

    Checks that the two harness-agnostic enforcement components —
    ``tools/agent-isolation/`` (layer 0, clean-env wrapper) and
    ``tools/agent-guard/`` (layer 3, action guard) — are present in the
    framework tree. This is the posture check for runtimes that do not have a
    dedicated per-harness config mode here (Cursor, Grok, …).
    """
    from sandbox_lint.posture import PostureViolation, check_posture_violations, find_framework_root

    root = framework_root if framework_root is not None else find_framework_root()
    violations: list[PostureViolation] = check_posture_violations(root)
    if not violations:
        # Presence check only: this proves the enforcement components exist in
        # the tree, NOT that a harness is wired to use them (see the module
        # docstring and README § Scope). Word the success line so it cannot be
        # mistaken for a live-enforcement guarantee.
        print(
            "sandbox-lint: OK (harness-neutral enforcement components present at "
            f"{root}; run setup-isolated-setup-doctor to verify live enforcement)"
        )
        return 0
    print(
        f"sandbox-lint: harness-neutral posture violations at {root} —\n"
        "  For runtimes without a dedicated config mode (Cursor, Grok, …)\n"
        "  the security posture is enforced by these OS-level components:",
        file=sys.stderr,
    )
    for v in violations:
        print(f"  - [{v.layer}] {v.detail}", file=sys.stderr)
    return 1


def _infer_project_root(settings_path: Path) -> Path | None:
    """The project root implied by ``settings_path``, when it is recoverable.

    The convention this repository and every adopter follow is
    ``<project_root>/.claude/settings.json``; when ``settings_path`` fits
    that shape, its grandparent is the project root ``check_invariants``
    needs to anchor the ``allowUnixSockets`` daemon-socket exemption. A
    ``--settings`` path that does not sit under a ``.claude/`` directory
    (e.g. an ad-hoc fixture in a test) yields ``None``, and
    ``check_invariants`` falls back to its documented unanchored-suffix
    residual for that call.
    """
    resolved = settings_path.resolve()
    if resolved.parent.name != ".claude":
        return None
    return resolved.parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sandbox-lint",
        description=(
            "Lint .claude/settings.json against the shipped baseline and the "
            "security invariants from docs/security/threat-model.md (M.29); "
            "or lint an OpenCode opencode.json permission policy (--opencode); "
            "or lint a project Codex profile (--codex); "
            "or lint a project Gemini profile (--gemini); "
            "or validate the harness-neutral OS-level posture for runtimes "
            "without a dedicated config file (--any-harness)."
        ),
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=DEFAULT_SETTINGS,
        help=f"Path to the live settings file (default: {DEFAULT_SETTINGS})",
    )
    parser.add_argument(
        "--local-template",
        type=Path,
        default=None,
        help=(
            "Local settings template merged over --settings before the baseline "
            f"diff (default: <project>/{DEFAULT_LOCAL_TEMPLATE} when --settings is "
            "<project>/.claude/settings.json and the template exists)"
        ),
    )
    parser.add_argument(
        "--expected",
        type=Path,
        default=DEFAULT_EXPECTED,
        help=f"Path to the canonical baseline (default: {DEFAULT_EXPECTED})",
    )
    # --opencode and --any-harness select alternate lint modes and are mutually
    # exclusive; passing both is a usage error rather than one silently winning.
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--opencode",
        type=Path,
        default=None,
        metavar="OPENCODE_JSON",
        help=(
            "Lint an OpenCode opencode.json permission policy against the "
            "OpenCode security invariants instead of the Claude Code sandbox "
            "config (invariants only — no baseline diff)."
        ),
    )
    mode.add_argument(
        "--kiro",
        type=Path,
        default=None,
        metavar="KIRO_AGENT_JSON",
        help=(
            "Lint a Kiro CLI agent-config (.kiro/agents/<name>.json) permission "
            "policy against the Kiro security invariants instead of the Claude "
            "Code sandbox config (invariants only — no baseline diff)."
        ),
    )
    mode.add_argument(
        "--codex",
        type=Path,
        default=None,
        metavar="CODEX_DIR",
        help=(
            "Lint a project-scoped Codex directory containing config.toml "
            "and rules/magpie.rules against the Codex security invariants "
            "(invariants only — no baseline diff)."
        ),
    )
    mode.add_argument(
        "--gemini",
        type=Path,
        metavar="GEMINI_DIR",
        help="Lint Gemini settings.json and policies/magpie.toml (static checks, not live enforcement).",
    )
    mode.add_argument(
        "--any-harness",
        nargs="?",
        const=True,  # True when flag given without a path → auto-detect framework root
        default=None,  # None when flag not given at all
        metavar="FRAMEWORK_ROOT",
        help=(
            "Validate the harness-neutral security posture for runtimes without "
            "a dedicated settings file (Cursor, Grok, …). "
            "Checks that the OS-level enforcement components (agent-isolation "
            "layer-0 clean-env wrapper and agent-guard layer-3 action guard) "
            "are present. Optionally supply the framework root directory; "
            "default: auto-detected by walking up from the current directory."
        ),
    )
    parser.add_argument(
        "--guard-from-plugin",
        action="store_true",
        help="Codex only: verify plugin guard registration/trust separately, without requiring a duplicate project hook.",
    )
    args = parser.parse_args(argv)
    if args.guard_from_plugin and args.codex is None:
        parser.error("--guard-from-plugin requires --codex")

    if args.gemini is not None:
        return _lint_gemini(args.gemini)
    if args.codex is not None:
        return _lint_codex(args.codex, guard_from_plugin=args.guard_from_plugin)
    if args.kiro is not None:
        return _lint_kiro(args.kiro)
    if args.opencode is not None:
        return _lint_opencode(args.opencode)

    if args.any_harness is not None:
        # True → auto-detect; string path → convert to Path
        explicit_root = None if args.any_harness is True else Path(args.any_harness)
        return _lint_any_harness(explicit_root)

    floor = _load_json(args.settings)
    expected = _load_json(args.expected)
    # The template belongs to the project whose settings are linted, never to
    # the current directory: a settings file outside `<root>/.claude/` gets none.
    template_path = args.local_template
    settings_root = _infer_project_root(args.settings)
    if (
        template_path is None
        and settings_root is not None
        and (settings_root / DEFAULT_LOCAL_TEMPLATE).is_file()
    ):
        template_path = settings_root / DEFAULT_LOCAL_TEMPLATE
    split: list[str] = []
    local_errors: list[str] = []
    if settings_root is not None and (settings_root / LOCAL_LIVE_SETTINGS).is_file():
        live_local = _load_json(settings_root / LOCAL_LIVE_SETTINGS)
        local_errors = override_errors(floor, live_local, label=str(LOCAL_LIVE_SETTINGS))
        local_errors += check_invariants(merge_layers(floor, live_local), project_root=settings_root)
    if settings_root is not None and (settings_root / FAMILY_MCP_REGISTRY).is_file():
        split.extend(registry_errors(floor, _load_json(settings_root / FAMILY_MCP_REGISTRY)))
    elif (
        template_path is not None
        and settings_root is not None
        and template_path == settings_root / DEFAULT_LOCAL_TEMPLATE
    ):
        # The framework checkout always carries both; a missing registry must
        # not silently skip the check of the committed MCP allows.
        split.append(f"{FAMILY_MCP_REGISTRY} is missing beside {DEFAULT_LOCAL_TEMPLATE}")
    if template_path is not None:
        template = _load_json(template_path)
        split.extend(split_errors(floor, template))
        # Someone with no local file runs on the floor alone, so every
        # protective setting, not only deny/ask rules, must stay in it.
        split.extend(f"floor alone: {e}" for e in check_invariants(floor, project_root=settings_root))
        settings = merge_layers(floor, template)
    else:
        settings = floor

    project_root = _infer_project_root(args.settings)
    invariant_errors = check_invariants(settings, project_root=project_root)
    diff_errors = deep_diff(settings, expected)
    # Run invariants on the baseline too: if a future PR weakens both
    # files in lockstep, the baseline must still pass on its own.
    baseline_invariant_errors = check_invariants(expected, project_root=project_root)

    if local_errors:
        print(
            f"sandbox-lint: your local {LOCAL_LIVE_SETTINGS} weakens a control the committed floor keeps:",
            file=sys.stderr,
        )
        for e in local_errors:
            print(f"  - {e}", file=sys.stderr)

    if (
        not invariant_errors
        and not diff_errors
        and not baseline_invariant_errors
        and not split
        and not local_errors
    ):
        layered = f" + {template_path}" if template_path is not None else ""
        print(f"sandbox-lint: OK ({args.settings}{layered} matches {args.expected})")
        return 0

    if split:
        layers = f"{args.settings} / {template_path}" if template_path is not None else str(args.settings)
        print(f"sandbox-lint: {layers} split violations:", file=sys.stderr)
        for e in split:
            print(f"  - {e}", file=sys.stderr)

    if invariant_errors:
        print(f"sandbox-lint: invariant violations in {args.settings}:", file=sys.stderr)
        for e in invariant_errors:
            print(f"  - {e}", file=sys.stderr)

    if baseline_invariant_errors:
        print(
            f"sandbox-lint: invariant violations in {args.expected} "
            "(the baseline itself is unsafe — fix the baseline before merging):",
            file=sys.stderr,
        )
        for e in baseline_invariant_errors:
            print(f"  - {e}", file=sys.stderr)

    if diff_errors:
        print(
            f"sandbox-lint: {args.settings} differs from {args.expected}. "
            "Every change to the live sandbox must be mirrored in the baseline "
            "(see docs/security/threat-model.md mitigation M.29):",
            file=sys.stderr,
        )
        for e in diff_errors:
            print(f"  - {e}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
