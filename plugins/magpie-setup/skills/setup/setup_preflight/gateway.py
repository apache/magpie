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

"""Is the container gateway's hook wired where Claude Code loads it?

A project wired for the gateway points `DOCKER_HOST` / `CONTAINER_HOST` at a
socket under its `.apache-magpie-local/run/`. The socket exists only while the
gateway runs, and the gateway starts only from the `SessionStart` /
`PreToolUse` hooks running `container-gateway-hook.sh`. Hooks registered in a
file Claude Code never loads -- `~/.claude/settings.local.json`, which the
setup guide once recommended -- never run, so every container command fails
with a missing socket and nothing says why.

Reported only when all three hold: the project is wired, no wired socket
exists, and no settings file Claude Code loads registers the `start` hook. A
registered hook means `ensure` restarts the gateway on the next container
command, so a gateway that merely exited is not reported. Inside the sandbox
`~/.claude/` may be read-denied; the managed-settings directories and the
project's own settings stay readable, and the facts say which user files could
be read so the rules can tell "not registered" from "not visible from here".
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

from .layers import main_worktree

#: Where Claude Code reads per-machine policy: `managed-settings.json`, then
#: every `*.json` drop-in in `managed-settings.d/`, merged alphabetically.
MANAGED_SETTINGS_DIRS: tuple[Path, ...] = (
    Path("/Library/Application Support/ClaudeCode"),
    Path("/etc/claude-code"),
)
#: The hook script itself (user scope) and the dispatcher the managed drop-in runs.
HOOK_COMMANDS = ("container-gateway-hook.sh", "container-gateway-dispatch")
# The gateway's run directory: `<root>/.apache-magpie-local/run/` in an adopted project,
# `<git-common-dir>/apache-magpie/run/<worktree-id>/` otherwise.
_SOCKET_RE = re.compile(
    r"^unix://(/.+/(?:\.apache-magpie-local/run|apache-magpie/run/[^/]+)/(?:docker|podman)\.sock)$"
)
_SOCKET_VARS = ("DOCKER_HOST", "CONTAINER_HOST")
#: The gateway and its Unix sockets are POSIX-only, and so is the non-blocking open below.
SUPPORTED = os.name == "posix"


def _read_regular(path: Path) -> bytes:
    """The file's bytes, or `OSError` for anything but a regular file.

    Opened non-blocking and checked with `fstat` before reading: a FIFO planted
    at a settings path (directly or through a symlink) would otherwise block
    the read, and with it every skill's pre-flight.
    """
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(f"{path} is not a regular file")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(fd)


def _load(path: Path) -> dict | None:
    """The file's JSON object; `None` when it is missing, unreadable, not regular or not an object."""
    try:
        loaded = json.loads(_read_regular(path).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _readable_or_absent(path: Path) -> bool:
    """False only when the file exists but cannot be read, as under a sandbox read-deny."""
    try:
        _read_regular(path)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def _start_commands(settings: dict) -> list[str]:
    """The `SessionStart` hook commands in `settings` that start the container gateway."""
    found: list[str] = []
    hooks = settings.get("hooks")
    entries = hooks.get("SessionStart") if isinstance(hooks, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        handlers = entry.get("hooks") if isinstance(entry, dict) else None
        for handler in handlers if isinstance(handlers, list) else []:
            command = handler.get("command") if isinstance(handler, dict) else None
            if (
                isinstance(command, str)
                and any(name in command for name in HOOK_COMMANDS)
                and command.split()[-1:] == ["start"]
            ):
                found.append(command)
    return found


def _starts_gateway(settings: dict) -> bool:
    return bool(_start_commands(settings))


def _dispatches(settings: dict) -> bool:
    """Whether every gateway `start` hook in `settings` runs through the dispatcher."""
    starts = _start_commands(settings)
    return bool(starts) and all("container-gateway-dispatch" in command for command in starts)


def _is_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError:
        return False


def managed_settings_files(dirs: tuple[Path, ...] | None = None) -> list[Path]:
    found: list[Path] = []
    for directory in MANAGED_SETTINGS_DIRS if dirs is None else dirs:
        found.append(directory / "managed-settings.json")
        # Claude Code ignores hidden drop-ins, so a disabled `.name.json` must not count.
        drop_ins = (directory / "managed-settings.d").glob("*.json")
        found.extend(sorted(path for path in drop_ins if not path.name.startswith(".")))
    return found


def _project_settings(root: Path) -> list[Path]:
    """The project settings a session in `root` loads, highest precedence first.

    In a linked worktree the main checkout's settings lead, as in the setup guide's
    "Sandbox-state status line" walk (the order `sandbox-status-line.sh` reads).
    """
    checkouts = [*filter(None, [main_worktree(root)]), root]
    return [
        checkout / ".claude" / name
        for checkout in checkouts
        for name in ("settings.local.json", "settings.json")
    ]


def wired_sockets(root: Path) -> list[str]:
    """Gateway socket paths the project's effective `env` points the container CLIs at."""
    envs = [settings.get("env") for settings in filter(None, map(_load, _project_settings(root)))]
    sockets: list[str] = []
    for var in _SOCKET_VARS:
        value = next((env[var] for env in envs if isinstance(env, dict) and var in env), None)
        match = _SOCKET_RE.match(value) if isinstance(value, str) else None
        if match and match.group(1) not in sockets:
            sockets.append(match.group(1))
    return sockets


def unstarted_gateway(
    root: Path,
    home: Path | None = None,
    managed_dirs: tuple[Path, ...] | None = None,
) -> dict[str, object] | None:
    """Facts for the finding, or `None` when there is nothing to report."""
    if not SUPPORTED:
        return None
    sockets = wired_sockets(root)
    if not sockets or any(Path(socket).exists() for socket in sockets):
        return None
    user_dir = (home if home is not None else Path.home()) / ".claude"
    loaded = [*managed_settings_files(managed_dirs), user_dir / "settings.json", *_project_settings(root)]
    registered = [settings for settings in filter(None, map(_load, loaded)) if _starts_gateway(settings)]
    hook = user_dir / "scripts" / "container-gateway-hook.sh"
    if registered and not (all(map(_dispatches, registered)) and _is_symlink(hook)):
        return None
    if registered:
        return {"sockets": sockets, "hook_is_symlink": str(hook)}
    unloaded = _load(user_dir / "settings.local.json")
    return {
        "sockets": sockets,
        "user_settings_readable": _readable_or_absent(user_dir / "settings.json"),
        "registered_in_unloaded_file": (
            str(user_dir / "settings.local.json")
            if unloaded is not None and _starts_gateway(unloaded)
            else None
        ),
    }
