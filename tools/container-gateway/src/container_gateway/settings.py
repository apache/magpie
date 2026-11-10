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

"""The Claude Code settings a project needs to reach its container gateway.

A sandboxed ``podman`` / ``docker`` reaches the gateway only when the
per-machine ``.claude/settings.local.json`` carries two things
(docs/setup/secure-agent-setup.md § Container gateway):

* ``env.CONTAINER_HOST`` / ``env.DOCKER_HOST`` as ``unix:///<absolute path>``
  to the gateway's sockets (a ``unix://./relative`` URL does not resolve);
* both socket paths in ``sandbox.network.allowUnixSockets`` (macOS; Linux
  ignores the list and needs ``allowAllUnixSockets``, which is the operator's
  decision and never written here).

``proposal`` computes that block from the gateway's own run directory, so the
paths are the ones ``serve`` will actually bind. ``apply`` merges it into one
settings file, and is written to be the only safe way to do that from an
agent session:

* **additive** — it adds the two env keys and two socket entries and touches
  nothing else; an env key already set to a *different* value is a conflict
  that is reported, never overwritten, because the operator chose it;
* **idempotent** — a file that already carries the block is not rewritten;
* **guarded** — it takes an exclusive ``flock`` on the file, re-parses it
  under the lock, and refuses to replace it if what is at the path moved
  between the read and the write: a different inode (an editor that saves by
  renaming a new file over it), or a changed mtime or size (one that writes
  in place without the lock); the new content goes to a sibling temp file,
  is fsynced, and ``os.replace``s into place, keeping the file's mode;
* **strict** — it refuses a symlinked target or a symlinked directory above
  it (every operation runs relative to a descriptor of the real directory,
  and only that last directory is ever created), and a file that is not a
  JSON object, rather than guess.

It never decides whether to apply: the caller (``setup config``) shows the
proposal and applies it only on the operator's explicit yes.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import json
import os
import secrets
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ENV_KEYS = {"podman": "CONTAINER_HOST", "docker": "DOCKER_HOST"}


class SettingsError(Exception):
    """The settings file cannot be merged safely; nothing was written."""


@dataclass
class Proposal:
    run_dir: Path
    env: dict[str, str]
    sockets: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "run_dir": str(self.run_dir),
            "env": dict(self.env),
            "sandbox": {"network": {"allowUnixSockets": list(self.sockets)}},
        }


@dataclass
class ApplyResult:
    path: Path
    status: str  # "written" | "unchanged"; conflicts are reported separately
    added_env: dict[str, str] = field(default_factory=dict)
    added_sockets: list[str] = field(default_factory=list)
    conflicts: dict[str, dict[str, str]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "status": self.status,
            "added_env": self.added_env,
            "added_sockets": self.added_sockets,
            "conflicts": self.conflicts,
        }


def proposal(run_dir: Path, socket_paths: dict[str, Path]) -> Proposal:
    """The block for ``run_dir``; ``socket_paths`` maps backend -> socket."""
    if not run_dir.is_absolute():
        raise SettingsError(f"run directory must be absolute, got {run_dir}")
    env: dict[str, str] = {}
    sockets: list[str] = []
    for backend, key in ENV_KEYS.items():
        sock = socket_paths[backend]
        env[key] = f"unix://{sock}"  # absolute path: unix:///abs/…
        sockets.append(str(sock))
    return Proposal(run_dir=run_dir, env=env, sockets=sockets)


def _merge(data: dict[str, Any], prop: Proposal) -> tuple[dict[str, Any], ApplyResult]:
    result = ApplyResult(path=Path(), status="unchanged")
    env = data.get("env", {})
    if not isinstance(env, dict):
        raise SettingsError("`env` is not a JSON object")
    sandbox = data.get("sandbox", {})
    if not isinstance(sandbox, dict):
        raise SettingsError("`sandbox` is not a JSON object")
    network = sandbox.get("network", {})
    if not isinstance(network, dict):
        raise SettingsError("`sandbox.network` is not a JSON object")
    sockets = network.get("allowUnixSockets", [])
    if not isinstance(sockets, list) or not all(isinstance(s, str) for s in sockets):
        raise SettingsError("`sandbox.network.allowUnixSockets` is not a list of strings")

    for key, value in prop.env.items():
        current = env.get(key)
        if current is None:
            env[key] = value
            result.added_env[key] = value
        elif current != value:
            result.conflicts[key] = {"current": str(current), "proposed": value}
    for sock in prop.sockets:
        if sock not in sockets:
            sockets.append(sock)
            result.added_sockets.append(sock)

    if result.added_env:
        data["env"] = env
    if result.added_sockets:
        network["allowUnixSockets"] = sockets
        sandbox["network"] = network
        data["sandbox"] = sandbox
    return data, result


def _name_fingerprint(dir_fd: int, name: str) -> tuple[int, int, int, int]:
    """What is at ``name`` now: catches an in-place edit and a rename-replace."""
    st = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    return st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size


def _open_parent(parent: Path) -> int:
    """Open the settings file's directory without following a symlink.

    Only the last component is created (never its ancestors), and a symlinked
    directory is refused: every later operation is relative to this
    descriptor, so a repository-controlled ``.claude`` symlink cannot
    redirect the write.
    """
    try:
        parent.mkdir(exist_ok=True)
    except FileNotFoundError as exc:
        raise SettingsError(f"{parent.parent} does not exist") from exc
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(parent, flags)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise SettingsError(
                f"{parent} is a symlink or not a directory; refusing to write through it"
            ) from exc
        raise


def apply(path: Path, prop: Proposal) -> ApplyResult:
    """Merge ``prop`` into the settings file at ``path`` (created if absent)."""
    if path.is_symlink():
        raise SettingsError(f"{path} is a symlink; refusing to write through it")
    dir_fd = _open_parent(path.parent)
    name = path.name
    try:
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(name, flags, 0o600, dir_fd=dir_fd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise SettingsError(f"{path} is a symlink; refusing to write through it") from exc
            raise
        try:
            return _apply_locked(path, prop, dir_fd, name, fd)
        finally:
            os.close(fd)
    finally:
        os.close(dir_fd)


def _apply_locked(path: Path, prop: Proposal, dir_fd: int, name: str, fd: int) -> ApplyResult:
    fcntl.flock(fd, fcntl.LOCK_EX)
    before = _name_fingerprint(dir_fd, name)
    opened = os.fstat(fd)
    if (opened.st_dev, opened.st_ino) != before[:2]:
        raise SettingsError(f"{path} was replaced while it was being opened; nothing written, re-run")
    chunks = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    raw = b"".join(chunks)
    text = raw.decode("utf-8") if raw else ""
    if text.strip():
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SettingsError(f"{path} is not valid JSON ({exc.msg} at line {exc.lineno})") from exc
        if not isinstance(data, dict):
            raise SettingsError(f"{path} is not a JSON object")
    else:
        data = {}
    merged, result = _merge(data, prop)
    result.path = path
    if not result.added_env and not result.added_sockets:
        return result  # nothing to add (possibly with conflicts): never rewrite
    changed = SettingsError(f"{path} changed while it was being merged; nothing written, re-run")
    if _name_fingerprint(dir_fd, name) != before:
        raise changed
    mode = stat.S_IMODE(opened.st_mode)
    tmp_name = f".{name}.{secrets.token_hex(8)}"
    tmp_fd = os.open(
        tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=dir_fd
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp:
            json.dump(merged, tmp, indent=2)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            os.fchmod(tmp.fileno(), mode)
        # Last look before the swap: a writer that ignores the lock, in place
        # or by renaming a new file over the name.
        if _name_fingerprint(dir_fd, name) != before:
            raise changed
        os.replace(tmp_name, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name, dir_fd=dir_fd)
        raise
    result.status = "written"
    return result
