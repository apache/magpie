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

"""The mechanical checks of `setup-isolated-setup-verify`, for Claude Code.

The verify skill walks nineteen checks.  Most of what they ask is not
judgement: merge four settings files and look for a key, see whether a
script is executable, order two version strings.  This module answers those
deterministically, and says which checks it cannot finish so the agent does
the rest by hand:

* **Decided here** — checks 1 (settings shape), 2 (user-scope hook wiring),
  3 (hook scripts), 4 (`claude-iso` sourced), 5 (tool versions), 6
  (effective `sandbox.enabled`), 8 (the static half: project-root grants in
  every worktree's `settings.local.json`) and 11 (the `gh` exclusion and the
  catch-all ask rule).
* **Gated here** — checks 9, 10, 12, 13, 15, 16, 17 and 19 apply only in
  some setups; the gate is evaluated, and a check whose gate is closed is
  `n/a`.  An open gate is `manual`: the agent runs that check from the
  skill's prose.
* **Always by hand** — checks 7 (live denial probes, one Bash call each),
  14 and 18, the live probe of check 8.

Statuses: `pass` (✓), `fail` (✗), `warn` (⚠), `n/a`, `unchecked` (no
framework checkout to compare against), `unknown` (an input could not be
read from here, usually the sandbox's read-deny on the home directory;
`unreadable` names it and the agent finishes the check by hand) and
`manual`.  Within one check, `fail` beats `warn`, which beats `unknown` and
`unchecked`: a gap found is reported even when another part could not be
read.

Read-only: no file is written, nothing reaches the network.  It runs
`git`, `claude --version`, `bwrap --version` and `socat -V`, nothing else,
and never prints a shell rc file beyond the matched `source` and `alias`
lines.

    python3 -P -m setup_preflight.isolated_verify check [--project-root DIR] [--framework DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .cli import _running_harness
from .gateway import _read_regular, managed_settings_files
from .layers import main_worktree

#: The check prose the agent falls back to for each mechanical check.
BY_HAND = "manual-checks.md"
CONDITIONAL = "conditional-checks.md"
#: The section of `BY_HAND` that holds each mechanical check's rules.
SECTIONS = {
    "1": "check-1--effective-settings-shape",
    "2": "check-2--user-scope-hook-wiring",
    "3": "check-3--hook-scripts-present-and-executable",
    "4": "check-4--claude-iso-sourced",
    "5": "check-5--tool-versions",
    "6": "check-6--status-line-prefix",
    "8": "check-8--project-root-grants",
    "11": "check-11--gh-runs-outside-the-sandbox",
}

#: Within one check, the first status in this order that any part has wins.
_ORDER = ("fail", "warn", "unknown", "unchecked", "pass")

HOOK_SCRIPTS = ("sandbox-bypass-warn.sh", "sandbox-error-hint.sh", "sandbox-status-line.sh")
#: A missing or non-executable copy of this one is ⚠, not ✗: the hook is a discoverability aid.
SOFT_SCRIPT = "sandbox-error-hint.sh"
RC_FILES = (".bashrc", ".zshrc")
_SOURCE_RE = re.compile(r"""^\s*(?:source|\.)\s+["']?([^"'\s;]*(?:agent|claude)-iso\.sh)""", re.MULTILINE)
_ALIAS_RE = re.compile(r"""^\s*alias\s+claude=["']?claude-iso\b""", re.MULTILINE)
PINNED = Path("tools/agent-isolation/pinned-versions.toml")
#: Linux sandbox primitives and the command that prints each one's version.
PRIMITIVES = (("bubblewrap", ("bwrap", "--version")), ("socat", ("socat", "-V")))
#: Absolute dev-tool paths `sandbox-add-project-root.sh` adds beside the project root.
DEV_TOOL_PATHS = (".local/bin", ".local/share/uv", ".cache", ".gitconfig", ".config/git")
GH_EXCLUSION = "gh *"
GH_CATCH_ALL = frozenset({"Bash(gh *)", "Bash(gh:*)", "Bash(gh)", "Bash(gh*)"})
EVALS_EXCLUSION = "~/.claude/scripts/magpie-run-evals.sh *"
VETTED_OPS_CONFIG = Path(".apache-magpie-overrides/tools/vetted-ops/config.toml")
_VERSION_RE = re.compile(r"(\d+(?:\.\d+)+)")


@dataclass
class Settings:
    """One settings file as this process sees it."""

    path: Path
    scope: str
    #: `read`, `absent`, `unreadable`, `placeholder` (a sandbox `/dev/null` stand-in) or `invalid`.
    state: str
    data: dict = field(default_factory=dict)

    @property
    def unseen(self) -> bool:
        """Whether the host may hold content this process could not read."""
        return self.state in ("unreadable", "placeholder")


def _run(argv: list[str]) -> str | None:
    """The command's combined output, or `None` when it cannot run or fails."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return (done.stdout or "") + (done.stderr or "")


@dataclass
class Context:
    root: Path
    home: Path
    env: Mapping[str, str]
    system: str
    framework_arg: Path | None = None
    managed_dirs: tuple[Path, ...] | None = None
    run: Callable[[list[str]], str | None] = field(default=_run)
    which: Callable[[str], str | None] = field(default=shutil.which)


def _is_placeholder(path: Path) -> bool:
    """A character device with `/dev/null`'s numbers: the sandbox's stand-in for a denied path."""
    try:
        info = path.stat()
        null = os.stat(os.devnull)
    except OSError:
        return False
    return stat.S_ISCHR(info.st_mode) and info.st_rdev == null.st_rdev


def load(path: Path, scope: str) -> Settings:
    if _is_placeholder(path):
        return Settings(path, scope, "placeholder")
    try:
        raw = _read_regular(path)
    except FileNotFoundError:
        return Settings(path, scope, "absent")
    except PermissionError:
        return Settings(path, scope, "unreadable")
    except OSError:
        return Settings(path, scope, "absent" if not os.path.lexists(path) else "unreadable")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return Settings(path, scope, "invalid")
    return Settings(path, scope, "read", data) if isinstance(data, dict) else Settings(path, scope, "invalid")


def _get(data: object, *keys: str) -> object:
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _strings(data: object, *keys: str) -> list[str]:
    value = _get(data, *keys)
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


class Verifier:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        root, home = ctx.root, ctx.home
        main = main_worktree(root)
        self.managed = [load(path, "managed") for path in managed_settings_files(ctx.managed_dirs)]
        self.local = load(root / ".claude" / "settings.local.json", "project-local")
        self.project = load(root / ".claude" / "settings.json", "project")
        self.main = (
            [
                load(main / ".claude" / "settings.local.json", "main-checkout-local"),
                load(main / ".claude" / "settings.json", "main-checkout"),
            ]
            if main is not None
            else []
        )
        self.user = load(home / ".claude" / "settings.json", "user")
        #: Claude Code does not load this one; it is read only to explain a missing sandbox.
        self.user_local = load(home / ".claude" / "settings.local.json", "user-local (not loaded)")
        self.rc: dict[str, str | None] = {}
        self.rc_state: dict[str, str] = {}
        for name in RC_FILES:
            path = home / name
            try:
                self.rc[name] = _read_regular(path).decode("utf-8", errors="replace")
                self.rc_state[name] = "read"
            except FileNotFoundError:
                self.rc[name], self.rc_state[name] = None, "absent"
            except OSError:
                placeholder = _is_placeholder(path)
                self.rc[name] = None
                self.rc_state[name] = "placeholder" if placeholder else "unreadable"

    # -- helpers ----------------------------------------------------------

    def show(self, path: Path | str) -> str:
        text = str(path)
        root, home = str(self.ctx.root), str(self.ctx.home)
        if text == root or text.startswith(root + os.sep):
            return os.path.relpath(text, root)
        if text == home or text.startswith(home + os.sep):
            return "~" + text[len(home) :]
        return text

    @property
    def merged(self) -> list[Settings]:
        """Every file Claude Code merges for this session, highest precedence first."""
        return [*self.managed, self.local, self.project, *self.main, self.user]

    def unseen(self, files: Iterable[Settings]) -> list[str]:
        return [f"{self.show(f.path)} ({f.state})" for f in files if f.unseen]

    def carriers(self, *keys: str, files: Iterable[Settings] | None = None) -> list[Settings]:
        return [
            f
            for f in (self.merged if files is None else files)
            if f.state == "read" and _get(f.data, *keys) not in (None, [], {})
        ]

    def sandbox_walk(self) -> list[Settings]:
        """The `sandbox.enabled` precedence walk, highest first."""
        return [*self.managed, self.local, self.project, *self.main, self.user]

    def sandbox_enabled(self) -> tuple[bool | None, Settings | None, list[Settings]]:
        """The effective value, the file that decided it, and unseen files above it."""
        above: list[Settings] = []
        for settings in self.sandbox_walk():
            value = _get(settings.data, "sandbox", "enabled") if settings.state == "read" else None
            if isinstance(value, bool):
                return value, settings, above
            if settings.unseen:
                above.append(settings)
        return None, None, above

    def expand(self, text: str) -> Path:
        if text == "~" or text.startswith("~/"):
            text = str(self.ctx.home) + text[1:]
        text = text.replace("$HOME", str(self.ctx.home))
        return Path(text)

    def sourced_scripts(self) -> list[tuple[str, str]]:
        """`(rc file, sourced path)` for each `agent-iso.sh` / `claude-iso.sh` source line."""
        return [
            (name, match.group(1))
            for name, text in self.rc.items()
            if text is not None
            for match in _SOURCE_RE.finditer(text)
        ]

    def framework(self) -> tuple[Path | None, str | None, list[str]]:
        """The framework checkout, how it was found, and candidates rejected on the way."""
        rejected: list[str] = []
        candidates: list[tuple[Path, str]] = []
        if self.ctx.framework_arg is not None:
            candidates.append((self.ctx.framework_arg, "argument"))
        candidates.append((self.ctx.root, "this repository"))
        candidates.append((self.ctx.root / ".apache-magpie", "snapshot"))
        for rc, sourced in self.sourced_scripts():
            start = self.expand(sourced).parent
            for parent in [start, *start.parents]:
                if parent == self.ctx.home or parent == Path(parent.anchor):
                    break
                candidates.append((parent, f"sourced from ~/{rc}"))
        for path, how in candidates:
            try:
                if (path / PINNED).is_file():
                    return path, how, rejected
            except OSError:
                pass  # an unreadable directory is not a checkout; try the next candidate
            if how == "argument":
                rejected.append(f"{path}: no {PINNED}")
        return None, None, rejected

    # -- the checks -------------------------------------------------------

    def check_1(self) -> dict:
        needed = {
            "permissions.deny": ("permissions", "deny"),
            "permissions.ask": ("permissions", "ask"),
            "sandbox.network.allowedDomains": ("sandbox", "network", "allowedDomains"),
            "sandbox.filesystem.allowRead": ("sandbox", "filesystem", "allowRead"),
            "sandbox.filesystem.allowWrite": ("sandbox", "filesystem", "allowWrite"),
        }
        evidence: list[str] = []
        missing: list[str] = []
        enabled, decider, _ = self.sandbox_enabled()
        if enabled is True and decider is not None:
            evidence.append(f"sandbox.enabled: true ({self.show(decider.path)})")
        else:
            missing.append("sandbox.enabled: true" if enabled is None else "sandbox.enabled is false")
            if decider is not None:
                evidence.append(f"sandbox.enabled: false ({self.show(decider.path)})")
        for label, keys in needed.items():
            found = self.carriers(*keys)
            if found:
                evidence.append(f"{label}: {', '.join(self.show(f.path) for f in found)}")
            else:
                missing.append(label)
        home = str(self.ctx.home)
        home_forms = {"~", "~/", home, home + "/", "$HOME", "$HOME/"}
        deny_read = [
            f
            for f in self.merged
            if f.state == "read" and home_forms & set(_strings(f.data, "sandbox", "filesystem", "denyRead"))
        ]
        if deny_read:
            evidence.append(
                f"sandbox.filesystem.denyRead covers ~/: {', '.join(self.show(f.path) for f in deny_read)}"
            )
        else:
            missing.append("sandbox.filesystem.denyRead containing ~/")
        if self.project.state != "read":
            evidence.append(f"{self.show(self.project.path)}: {self.project.state}")
        unseen = self.unseen(self.merged)
        if not missing:
            return self.result("1", "pass", evidence)
        evidence.insert(0, "missing: " + "; ".join(missing))
        if unseen:
            return self.result("1", "unknown", evidence, unreadable=unseen)
        return self.result("1", "fail", evidence)

    def check_2(self) -> dict:
        user = self.user
        if user.state != "read":
            status = "fail" if user.state == "absent" else "unknown"
            return self.result(
                "2", status, [f"{self.show(user.path)}: {user.state}"], unreadable=self.unseen([user])
            )
        parts: list[tuple[str, str]] = []
        for event, script, missing_status in (
            ("PreToolUse", "sandbox-bypass-warn.sh", "fail"),
            ("PostToolUse", "sandbox-error-hint.sh", "warn"),
        ):
            if self._hooked(user.data, event, script):
                parts.append(("pass", f"{event} Bash → {script}"))
            else:
                parts.append((missing_status, f"no {event} Bash hook running {script}"))
        line = _get(user.data, "statusLine")
        command = _get(line, "command") if isinstance(line, dict) else line
        if not isinstance(command, str) or not command.strip():
            parts.append(("fail", "no statusLine"))
        elif "sandbox-status-line.sh" in command:
            parts.append(("pass", f"statusLine → {command.strip()}"))
        else:
            custom = self.expand(command.split()[0])
            try:
                text = _read_regular(custom).decode("utf-8", errors="replace")
            except OSError:
                parts.append(("unknown", f"statusLine → {command.strip()}: script not readable from here"))
            else:
                if "[sandbox]" in text or "NO SANDBOX" in text:
                    parts.append(
                        ("warn", f"statusLine → custom {self.show(custom)}, embeds the sandbox prefix")
                    )
                else:
                    parts.append(("fail", f"statusLine → {self.show(custom)}, no sandbox prefix logic"))
        return self.combine("2", parts)

    @staticmethod
    def _hooked(data: dict, event: str, script: str) -> bool:
        entries = _get(data, "hooks", event)
        for entry in entries if isinstance(entries, list) else []:
            matcher = entry.get("matcher", "") if isinstance(entry, dict) else None
            if not isinstance(matcher, str) or not ("Bash" in matcher or matcher in ("", "*")):
                continue
            handlers = _get(entry, "hooks")
            for hook in handlers if isinstance(handlers, list) else []:
                command = _get(hook, "command")
                if isinstance(command, str) and script in command:
                    return True
        return False

    def check_3(self) -> dict:
        parts: list[tuple[str, str]] = []
        scripts = self.ctx.home / ".claude" / "scripts"
        for name in HOOK_SCRIPTS:
            gap = "warn" if name == SOFT_SCRIPT else "fail"
            path = scripts / name
            try:
                target = path.resolve() if path.is_symlink() else path
                if not target.is_file():
                    parts.append(
                        (
                            gap,
                            f"{name}: missing"
                            + (f" (link to {self.show(target)})" if target != path else ""),
                        )
                    )
                elif not os.access(target, os.X_OK):
                    parts.append((gap, f"{name}: not executable"))
                else:
                    via = f" → {self.show(target)}" if target != path else ""
                    parts.append(("pass", f"{name}: executable{via}"))
            except PermissionError:
                parts.append(("unknown", f"{name}: not readable from here"))
        result = self.combine("3", parts)
        if result["status"] == "unknown":
            result["unreadable"] = [self.show(scripts)]
        return result

    def check_4(self) -> dict:
        sourced = self.sourced_scripts()
        evidence = [f"~/{rc}: source {path}" for rc, path in sourced]
        for name, text in self.rc.items():
            if text is not None and _ALIAS_RE.search(text):
                evidence.append(f"note: alias claude='claude-iso' set in ~/{name}")
        if sourced:
            if not any(line.startswith("note:") for line in evidence):
                evidence.append("note: alias claude='claude-iso' not set (optional)")
            return self.result("4", "pass", evidence)
        unseen = [
            f"~/{name} ({state})"
            for name, state in self.rc_state.items()
            if state in ("unreadable", "placeholder")
        ]
        states = ", ".join(f"~/{name}: {state}" for name, state in self.rc_state.items())
        if unseen:
            return self.result("4", "unknown", [f"no source line found ({states})"], unreadable=unseen)
        return self.result("4", "fail", [f"no agent-iso.sh / claude-iso.sh source line ({states})"])

    def check_5(self) -> dict:
        framework, _, _ = self.framework()
        harness, _ = _running_harness(self.ctx.env)
        parts: list[tuple[str, str]] = []
        out = self.ctx.run(["claude", "--version"])
        match = _VERSION_RE.search(out or "")
        running = match.group(1) if match else None
        manifest: dict = {}
        if framework is not None:
            try:
                manifest = tomllib.loads((framework / PINNED).read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError) as error:
                parts.append(("unknown", f"{PINNED}: {error}"))
        floor = _get(manifest, "tools", "claude-code", "min_version")
        shown = running or "not available"
        if framework is None:
            parts.append(
                ("warn", f"claude-code {shown}; min_version floor not enforced: no framework checkout")
            )
        elif not isinstance(floor, str):
            parts.append(
                ("unknown", f"claude-code {shown}; no [tools.claude-code] min_version in the manifest")
            )
        elif running is None:
            parts.append(
                (
                    "unknown" if harness == "claude" else "warn",
                    f"claude --version: not available; floor {floor}",
                )
            )
        elif _key(running) < _key(floor):
            status = "fail" if harness == "claude" else "warn"
            note = (
                ""
                if harness == "claude"
                else " (not running under Claude Code: floor not enforced as a hard gate)"
            )
            parts.append((status, f"claude-code {running} is below the min_version floor {floor}{note}"))
        else:
            parts.append(("pass", f"claude-code {running}, at or above the min_version floor {floor}"))
        if self.ctx.system != "Linux":
            parts.append(("pass", "bubblewrap/socat: not needed here (Seatbelt is built in)"))
        else:
            for tool, argv in PRIMITIVES:
                out = self.ctx.run(list(argv))
                found = _primitive_version(tool, out)
                pin = _get(manifest, "tools", tool, "version")
                if found is None:
                    parts.append(
                        ("unknown", f"{tool}: version not readable ({argv[0]} not runnable from here)")
                    )
                elif framework is None:
                    parts.append(("unchecked", f"{tool} {found}: pin unchecked, no framework checkout"))
                elif found != pin:
                    parts.append(("warn", f"{tool} {found} differs from the pin {pin}"))
                else:
                    parts.append(("pass", f"{tool} {found} matches the pin"))
        return self.combine("5", parts)

    def check_6(self) -> dict:
        evidence = []
        for settings in [*self.sandbox_walk(), self.user_local]:
            if settings.state == "read":
                value = _get(settings.data, "sandbox", "enabled")
                shown = json.dumps(value) if isinstance(value, bool) else "not set"
            else:
                shown = settings.state
            evidence.append(f"{self.show(settings.path)}: sandbox.enabled = {shown}")
        enabled, decider, above = self.sandbox_enabled()
        if above:
            return self.result("6", "unknown", evidence, unreadable=self.unseen(above))
        if enabled is True and decider is not None:
            evidence.insert(0, f"effective sandbox.enabled: true (from {self.show(decider.path)}): [sandbox]")
            return self.result("6", "pass", evidence)
        if enabled is False and decider is not None:
            evidence.insert(
                0, f"effective sandbox.enabled: false (from {self.show(decider.path)}): [NO SANDBOX]"
            )
            return self.result("6", "fail", evidence)
        if self.user_local.state == "read" and _get(self.user_local.data, "sandbox", "enabled") is True:
            evidence.insert(
                0,
                "sandbox.enabled is true only in ~/.claude/settings.local.json, which Claude Code does not load:"
                " the session has no sandbox",
            )
        else:
            evidence.insert(0, "sandbox.enabled is set in no file Claude Code loads: [NO SANDBOX]")
        return self.result("6", "fail", evidence)

    def worktrees(self) -> list[tuple[Path, bool]]:
        """`(path, prunable)` for every worktree of this repository, this one first."""
        out = self.ctx.run(["git", "-C", str(self.ctx.root), "worktree", "list", "--porcelain"])
        found: list[tuple[Path, bool]] = []
        for block in (out or "").split("\n\n"):
            lines = block.splitlines()
            path = next((line[len("worktree ") :] for line in lines if line.startswith("worktree ")), None)
            if path:
                found.append((Path(path), any(line.startswith("prunable") for line in lines)))
        here = _norm(str(self.ctx.root))
        rest = [(path, prunable) for path, prunable in found if _norm(str(path)) != here]
        return [(self.ctx.root, False), *rest]

    def check_8(self) -> dict:
        parts: list[tuple[str, str]] = []
        unseen: list[str] = []
        for index, (tree, prunable) in enumerate(self.worktrees()):
            settings = (
                self.local if index == 0 else load(tree / ".claude" / "settings.local.json", "worktree")
            )
            label = self.show(settings.path) if index == 0 else str(settings.path)
            if settings.unseen or (index and not tree.is_dir()):
                why = "prunable or not visible from here" if prunable or not tree.is_dir() else settings.state
                parts.append(("unknown", f"{label}: {why}"))
                unseen.append(f"{label} ({why})")
                continue
            reads = _strings(settings.data, "sandbox", "filesystem", "allowRead")
            writes = _strings(settings.data, "sandbox", "filesystem", "allowWrite")
            missing = [
                name
                for name, entries in (("allowRead", reads), ("allowWrite", writes))
                if not _covers(entries, tree)
            ]
            if missing:
                parts.append(("fail", f"{label}: {tree} missing from {' and '.join(missing)}"))
            else:
                parts.append(("pass", f"{label}: {tree} in allowRead and allowWrite"))
            if index == 0:
                absent = [
                    str(self.ctx.home / rel)
                    for rel in DEV_TOOL_PATHS
                    if not _covers(reads, self.ctx.home / rel)
                ]
                if absent:
                    parts.append(
                        ("warn", f"{label}: dev-tool paths missing from allowRead: {', '.join(absent)}")
                    )
        hooks_path = (self.ctx.run(["git", "config", "--global", "--get", "core.hooksPath"]) or "").strip()
        whole_user = bool(hooks_path) and _norm(str(self.expand(hooks_path))) == _norm(
            str(self.ctx.home / ".claude" / "git-hooks")
        )
        parts.append(
            (
                "pass",
                f"scope: {'whole-user' if whole_user else 'per-project'} (core.hooksPath {hooks_path or 'unset'})",
            )
        )
        result = self.combine("8", parts)
        if unseen:
            result["unreadable"] = unseen
        result["manual"] = ["live probe"] + (["whole-user scope sub-checks"] if whole_user else [])
        result["see"] = f"{CONDITIONAL}#check-8--whole-user-scope-detection" if whole_user else None
        return result

    def check_11(self) -> dict:
        parts: list[tuple[str, str]] = []
        files = self.merged
        excluded = [
            f
            for f in files
            if f.state == "read" and GH_EXCLUSION in _strings(f.data, "sandbox", "excludedCommands")
        ]
        if excluded:
            parts.append(
                (
                    "pass",
                    f'"{GH_EXCLUSION}" in sandbox.excludedCommands: {", ".join(self.show(f.path) for f in excluded)}',
                )
            )
        elif self.unseen(files):
            parts.append(("unknown", f'"{GH_EXCLUSION}" not in any readable sandbox.excludedCommands'))
        else:
            status = "fail" if self.ctx.system == "Darwin" else "warn"
            parts.append((status, f'"{GH_EXCLUSION}" missing from sandbox.excludedCommands in every scope'))
        catch_all = [
            f"{self.show(f.path)}: {rule}"
            for f in files
            if f.state == "read"
            for rule in _strings(f.data, "permissions", "ask")
            if rule.replace(" ", "") in {r.replace(" ", "") for r in GH_CATCH_ALL} or rule in GH_CATCH_ALL
        ]
        if catch_all:
            parts.append(("fail", "11b catch-all gh ask rule: " + "; ".join(catch_all)))
        elif self.unseen(files):
            parts.append(("unknown", "11b: no catch-all gh ask rule in any readable file"))
        else:
            parts.append(("pass", "11b: no catch-all gh ask rule"))
        result = self.combine("11", parts)
        if result["status"] == "unknown":
            result["unreadable"] = self.unseen(files)
        return result

    # -- gated and manual checks ------------------------------------------

    def _rules(self, *keys: str) -> list[tuple[Settings, str]]:
        return [(f, rule) for f in self.merged if f.state == "read" for rule in _strings(f.data, *keys)]

    def gate_vetted_ops(self, n: str) -> dict:
        rule_keys = (
            ("permissions", "allow"),
            ("permissions", "ask"),
            ("permissions", "deny"),
            ("sandbox", "excludedCommands"),
        )
        rules = [(f, rule) for keys in rule_keys for f, rule in self._rules(*keys) if "vetted-op" in rule]
        config = (self.ctx.root / VETTED_OPS_CONFIG).is_file()
        see = f"{CONDITIONAL}#check-{n}--" + (
            "the-vetted-ops-split-and-exclusion" if n == "9" else "read-only-vetted-ops-never-prompt"
        )
        if not config and not rules:
            if self.unseen(self.merged):
                return self.result(
                    n,
                    "unknown",
                    ["no vetted-ops config and no vetted-op rule in any readable file"],
                    unreadable=self.unseen(self.merged),
                    see=see,
                )
            return self.result(n, "n/a", ["no vetted-ops config.toml and no vetted-op rule"])
        enabled, _, _ = self.sandbox_enabled()
        if enabled is not True:
            if n == "9":
                bypass = [
                    f"{self.show(f.path)}: {rule}"
                    for keys in (("permissions", "allow"), ("sandbox", "excludedCommands"))
                    for f, rule in self._rules(*keys)
                    if "vetted-op-read" in rule
                ]
                if bypass:
                    return self.result(
                        n,
                        "fail",
                        [
                            "sandbox not enabled, yet vetted-op-read is allowed or excluded: "
                            + "; ".join(bypass)
                        ],
                    )
            return self.result(n, "n/a", ["sandbox not enabled"])
        return self.result(
            n, "manual", ["vetted-ops in use" + (" (config.toml present)" if config else "")], see=see
        )

    def gate_10(self) -> dict:
        gpgsign = (
            self.ctx.run(["git", "-C", str(self.ctx.root), "config", "--get", "commit.gpgsign"]) or ""
        ).strip()
        sock = self.ctx.env.get("SSH_AUTH_SOCK", "")
        via_gpg = "S.gpg-agent" in sock or "gpg-agent" in sock
        evidence = [
            f"commit.gpgsign: {gpgsign or 'unset'}",
            f"SSH_AUTH_SOCK via gpg-agent: {'yes' if via_gpg else 'no'}",
        ]
        if gpgsign.lower() != "true" and not via_gpg:
            return self.result("10", "n/a", evidence)
        return self.result(
            "10",
            "manual",
            evidence,
            see=f"{CONDITIONAL}#check-10--hardware-key-touch-overlay-and-the-signing-key",
        )

    def gate_12(self) -> dict:
        runtimes = [name for name in ("podman", "docker") if self.ctx.which(name)]
        evidence = [f"container runtimes on PATH: {', '.join(runtimes) or 'none (12a-12d n/a)'}"]
        return self.result("12", "manual", evidence, see=f"{CONDITIONAL}#check-12--container-gateway-wired")

    def gate_13(self) -> dict:
        excluded = [f for f, rule in self._rules("sandbox", "excludedCommands") if rule == EVALS_EXCLUSION]
        script = (self.ctx.home / ".claude" / "scripts" / "magpie-run-evals.sh").exists()
        if not excluded and not script:
            return self.result(
                "13", "n/a", ["no eval-harness exclusion and no ~/.claude/scripts/magpie-run-evals.sh"]
            )
        evidence = [
            f"exclusion: {'yes' if excluded else 'no'}",
            f"wrapper script: {'present' if script else 'absent'}",
        ]
        return self.result(
            "13", "manual", evidence, see=f"{CONDITIONAL}#check-13--eval-harness-exclusion-if-installed"
        )

    def gate_15(self) -> dict:
        on = [
            f
            for f in self.merged
            if f.state == "read"
            and _get(f.data, "permissions", "blockReadsOutsideWorkingDirectories") is True
        ]
        see = f"{CONDITIONAL}#check-15--working-directories-under-the-read-block"
        if on:
            return self.result(
                "15",
                "manual",
                [f"blockReadsOutsideWorkingDirectories: {', '.join(self.show(f.path) for f in on)}"],
                see=see,
            )
        if self.unseen(self.merged):
            return self.result(
                "15",
                "unknown",
                ["blockReadsOutsideWorkingDirectories not set in any readable file"],
                unreadable=self.unseen(self.merged),
                see=see,
            )
        return self.result(
            "15", "n/a", ["permissions.blockReadsOutsideWorkingDirectories not true in any scope"]
        )

    def gate_17(self) -> dict:
        found = self.ctx.which("roborev")
        if not found:
            return self.result("17", "n/a", ["roborev not on PATH"])
        return self.result(
            "17",
            "manual",
            [f"roborev: {self.show(found)}"],
            see=f"{CONDITIONAL}#check-17--roborev-exclusion-if-installed",
        )

    def gate_19(self) -> dict:
        enabled, _, _ = self.sandbox_enabled()
        if enabled is not True:
            return self.result("19", "n/a", ["sandbox not enabled"])
        return self.result("19", "manual", ["sandbox enabled"])

    # -- assembly ---------------------------------------------------------

    @staticmethod
    def result(
        n: str, status: str, evidence: list[str], unreadable: list[str] | None = None, see: str | None = None
    ) -> dict:
        out: dict[str, object] = {"check": n, "status": status, "evidence": evidence}
        if unreadable and status == "unknown":
            out["unreadable"] = unreadable
            out["see"] = see or f"{BY_HAND}#{SECTIONS[n]}"
        elif see:
            out["see"] = see
        return out

    def combine(self, n: str, parts: list[tuple[str, str]]) -> dict:
        statuses = {status for status, _ in parts}
        status = next((s for s in _ORDER if s in statuses), "pass")
        result = self.result(n, status, [text for _, text in parts])
        if status == "unknown":
            result["see"] = f"{BY_HAND}#{SECTIONS[n]}"
        return result

    def run(self) -> dict:
        framework, how, rejected = self.framework()
        harness, _ = _running_harness(self.ctx.env)
        findings = [
            self.check_1(),
            self.check_2(),
            self.check_3(),
            self.check_4(),
            self.check_5(),
            self.check_6(),
            self.result("7", "manual", ["live denial probes, one Bash call each"]),
            self.check_8(),
            self.gate_vetted_ops("9"),
            self.gate_10(),
            self.check_11(),
            self.gate_12(),
            self.gate_13(),
            self.result(
                "14",
                "manual",
                ["n/a unless the magpie-adversarial-review plugin is installed"],
                see=f"{CONDITIONAL}#check-14--adversarial-review-exclusion-if-installed",
            ),
            self.gate_15(),
            self.gate_vetted_ops("16"),
            self.gate_17(),
            self.result("18", "manual", ["local agent settings against the reconciliation"]),
            self.gate_19(),
        ]
        facts = {
            "platform": self.ctx.system,
            "harness": harness,
            "project_root": str(self.ctx.root),
            "framework_checkout": str(framework) if framework else None,
            "framework_found_via": how,
            "framework_rejected": rejected,
            "settings": [
                {"path": self.show(f.path), "scope": f.scope, "state": f.state}
                for f in [*self.merged, self.user_local]
            ],
        }
        return {"facts": facts, "findings": findings}


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def _primitive_version(tool: str, out: str | None) -> str | None:
    if not out:
        return None
    match = re.search(rf"{tool}\s+(?:version\s+)?(\d[\w.]*)", out, re.IGNORECASE)
    match = match or _VERSION_RE.search(out)
    return match.group(1) if match else None


def _norm(path: str) -> str:
    if path.startswith("//"):
        path = path[1:]
    return path.rstrip("/") or "/"


def _covers(entries: list[str], target: Path) -> bool:
    """Whether an absolute entry names `target` itself, literally or once symlinks resolve.

    Relative and `~/` entries never count: the harness drops them on the read
    side (issue #197), which is why the helper writes absolute paths.
    """
    wanted = {_norm(str(target)), _norm(os.path.realpath(target))}
    for entry in entries:
        if not entry.startswith("/"):
            continue
        entry = _norm(entry)
        if entry in wanted or _norm(os.path.realpath(entry)) in wanted:
            return True
    return False


def _top_level(start: Path, run: Callable[[list[str]], str | None]) -> Path:
    out = run(["git", "-C", str(start), "rev-parse", "--show-toplevel"])
    return Path(out.strip()) if out and out.strip() else start


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -P -m setup_preflight.isolated_verify", description=__doc__.split("\n\n")[0]
    )
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="run the mechanical checks and print the JSON report")
    check.add_argument("--project-root", type=Path, default=Path.cwd())
    check.add_argument("--framework", type=Path, default=None, help="the magpie checkout to compare against")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    start = args.project_root.resolve()
    root = _top_level(start, _run)
    ctx = Context(
        root=root,
        home=Path.home(),
        env=os.environ,
        system=platform.system(),
        framework_arg=args.framework.expanduser().resolve() if args.framework else None,
        run=_run,
    )
    json.dump(Verifier(ctx).run(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
