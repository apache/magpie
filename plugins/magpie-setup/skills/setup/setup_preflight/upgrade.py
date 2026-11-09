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

"""Whether Magpie changed since this project's last install or upgrade.

Every skill's pre-flight asks this.  When the Magpie version running now
differs from the one this project last installed, configured or upgraded
to, the skill asks the user whether to run `setup-upgrade` before it
carries on, and asks again on the next skill until that run is recorded
here.  Nothing is suppressed on a decline: that is the point.

The running version comes from what the sandbox can read:

1. the harness's plugin listing, when the pre-flight could read it;
2. the version marker the `magpie-setup` session hook writes at every
   session start, in the plugin's data directory (Claude Code), or the
   hook's own XDG fallback.

The baseline is, first hit wins: the `upgraded` block this module's
`record` writes, the personal stamp's `version` (written when the project
was configured), then the committed lock's `reconciled.version`.  A
project with none of them has never been set up here, and nobody is asked
to upgrade what they never installed.

A pinned snapshot is left to the snapshot-drift finding, which already
asks on every run, and a framework checkout (`method: local`) upgrades
with `git pull`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path

from .core import SNAPSHOT_METHODS, STAMP_NAME, Finding
from .layers import LOCK_NAME, personal_dir, personal_layers
from .lockfile import MalformedLock, load
from .version import InvalidVersion, compare

BLOCK = "upgraded"
SECTION = "step-15"
#: The plugin whose session hook writes the marker, and its marketplace.
PLUGIN = "magpie-setup"
MARKETPLACE = "apache-magpie"
MARKER = "magpie-plugin-version"


def _load_stamp(root: Path) -> dict[str, object]:
    """The stamp as read: personal layer first, then the legacy in-tree one."""
    for layer in personal_layers(root):
        try:
            loaded = json.loads((layer / STAMP_NAME).read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, json.JSONDecodeError):
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _marker_paths(env: Mapping[str, str], home: Path) -> list[Path]:
    """Where the session hook leaves the version it saw, most specific first."""
    claude = Path(env["CLAUDE_CONFIG_DIR"]) if env.get("CLAUDE_CONFIG_DIR") else home / ".claude"
    state = Path(env["XDG_STATE_HOME"]) if env.get("XDG_STATE_HOME") else home / ".local" / "state"
    return [
        claude / "plugins" / "data" / f"{PLUGIN}-{MARKETPLACE}" / MARKER,
        state / "magpie" / MARKER,
    ]


def _valid(text: object) -> str | None:
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        compare(text, text)
    except InvalidVersion:
        return None
    return text.strip()


def running_version(
    installed: dict[str, str] | None,
    harness: str | None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> str | None:
    """The Magpie version this session runs, or `None` when it cannot be told."""
    if installed:
        listed = _valid(installed.get("magpie" if harness == "antigravity" else PLUGIN))
        if listed:
            return listed
    env = os.environ if env is None else env
    for marker in _marker_paths(env, home or Path.home()):
        try:
            found = _valid(marker.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if found:
            return found
    return None


def baseline(root: Path) -> str | None:
    """The version this project was last installed, configured or upgraded to."""
    stamp = _load_stamp(root)
    block = stamp.get(BLOCK)
    if isinstance(block, dict) and _valid(block.get("version")):
        return _valid(block.get("version"))
    if _valid(stamp.get("version")):
        return _valid(stamp.get("version"))
    try:
        lock = load(root / LOCK_NAME)
    except MalformedLock:
        return None
    if lock and lock.reconciled:
        return _valid(lock.reconciled.version)
    return None


def findings(
    root: Path,
    installed: dict[str, str] | None,
    harness: str | None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> list[Finding]:
    """One `upgrade-pending` finding while the two versions differ."""
    try:
        lock = load(root / LOCK_NAME)
    except MalformedLock:
        lock = None
    if lock is not None and (lock.method in SNAPSHOT_METHODS or lock.method == "local"):
        return []
    last = baseline(root)
    if last is None:
        return []
    now = running_version(installed, harness, env, home)
    if now is None or compare(now, last) == 0:
        return []
    return [
        Finding(
            "machine",
            "upgrade-pending",
            SECTION,
            {"from": last, "to": now, "downgrade": compare(now, last) < 0},
        )
    ]


def record(
    root: Path,
    version: str | None = None,
    today: date | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> dict[str, object]:
    """Record that `setup-upgrade` finished here against `version`.

    Without `version`, the running version is read as the pre-flight reads
    it.  Merged into the personal layer's stamp, every other key intact.
    """
    resolved = _valid(version) if version is not None else running_version(None, None, env, home)
    if resolved is None:
        raise ValueError("the running Magpie version cannot be read; pass --version")
    stamp = _load_stamp(root)
    block: dict[str, object] = {"version": resolved, "at": (today or date.today()).isoformat()}
    stamp[BLOCK] = block
    path = personal_dir(root) / STAMP_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return block


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="setup_preflight.upgrade", description=__doc__.split("\n")[0])
    parser.add_argument("action", choices=["status", "record"])
    parser.add_argument("--project-root", default=".", type=Path)
    parser.add_argument("--version", help="record: the version upgraded to (default: the running one)")
    args = parser.parse_args(argv)
    root: Path = args.project_root
    if args.action == "status":
        print(
            json.dumps(
                {
                    "running": running_version(None, None),
                    "baseline": baseline(root),
                    "pending": [f.facts for f in findings(root, None, None)],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    try:
        block = record(root, args.version)
    except ValueError as exc:
        print(f"setup_preflight.upgrade: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({BLOCK: block}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
