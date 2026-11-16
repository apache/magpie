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
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from .core import LOCAL_METHOD, SNAPSHOT_METHODS, STAMP_NAME, Finding, configured_at_all, project_findings
from .installed import read_installed
from .layers import LOCK_NAME, OVERRIDES_DIR, describe, personal_dir, personal_layers
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


# --- gather: the facts `setup-upgrade` decides its catalogue reads from -------------

#: Personal-layer entries that are bookkeeping, never configuration a project commits.
_NOT_CONFIG = frozenset({STAMP_NAME, "setup_preflight", "run"})


def _install(method: str | None) -> str:
    """The `setup verify` branch for this install: `local`, `snapshot`, `marketplace` or `none`."""
    if method is None:
        return "none"
    if method == LOCAL_METHOD:
        return "local"
    if method in SNAPSHOT_METHODS:
        return "snapshot"
    return "marketplace" if method == "marketplace" else "unknown"


def shadowed(root: Path) -> list[dict[str, object]]:
    """Personal-layer files with a committed `.apache-magpie-overrides/` file at the same path.

    The first personal layer to hold a path wins, as the lookup chain reads
    them.  `identical` is a byte comparison.  Symlinks are neither followed
    nor reported, and bookkeeping (the stamp, dot-files, a checker copy,
    run state) is not configuration.  Read-only.
    """
    committed = root / OVERRIDES_DIR
    if not committed.is_dir():
        return []
    found: dict[str, dict[str, object]] = {}
    for layer in personal_layers(root):
        if not layer.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(layer, followlinks=False):
            base = Path(dirpath)
            dirnames[:] = sorted(
                d for d in dirnames if not d.startswith(".") and not (base == layer and d in _NOT_CONFIG)
            )
            for name in sorted(filenames):
                path = base / name
                rel = path.relative_to(layer).as_posix()
                if name.startswith(".") or rel in _NOT_CONFIG or rel in found or path.is_symlink():
                    continue
                target = committed / rel
                if target.is_symlink() or not target.is_file():
                    continue
                try:
                    identical = path.read_bytes() == target.read_bytes()
                except OSError:
                    continue
                found[rel] = {"file": rel, "layer": str(layer), "identical": identical}
    return [found[rel] for rel in sorted(found)]


def _day(text: object) -> date | None:
    if not isinstance(text, str):
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def isolated_summary(root: Path, today: date | None = None, home: Path | None = None) -> dict[str, object]:
    """The isolated setup as `setup-upgrade` needs it: in use, and changed since its last check.

    `state` is `opted-out` (the stamp's `enabled: false`), `in-use`, or
    `unknown`, never `absent`: inside the sandbox the user-scope settings
    are read-denied, so a `False` from `isolated.configured` proves nothing.
    `changed` is true when the secure-setup fingerprint differs from the one
    the last `setup-isolated-setup-update` run recorded, or either is
    unknown; a reminder that was only shown (`acknowledged`) is not a check
    that ran, so it does not count.  `due` is true when that run is at least
    the interval old, or never happened; an interval of 0 turns it off.
    `attention` is `in-use` and (`changed` or `due`).
    """
    from . import isolated

    raw = _load_stamp(root).get(isolated.BLOCK)
    block: dict[str, object] = raw if isinstance(raw, dict) else {}
    if block.get("enabled") is False:
        state = "opted-out"
    elif isolated.installed(root, home):
        state = "in-use"
    else:
        state = "unknown"
    recorded = block.get("fingerprint")
    current = isolated.current(root)
    changed = current is None or recorded != current
    interval = isolated.interval_days(root)
    updated = _day(block.get("updated_at"))
    due = interval > 0 and (updated is None or ((today or date.today()) - updated).days >= interval)
    return {
        "state": state,
        "recorded": recorded if isinstance(recorded, str) else None,
        "current": current,
        "changed": changed,
        "updated_at": updated.isoformat() if updated else None,
        "interval_days": interval,
        "due": due,
        "attention": state == "in-use" and (changed or due),
    }


def gather(
    root: Path,
    installed: dict[str, str] | None,
    harness: str | None,
    today: date | None = None,
    home: Path | None = None,
) -> dict[str, object]:
    """The facts `setup-upgrade`'s Gather decides which catalogue sections to read from.  Read-only."""
    try:
        lock = load(root / LOCK_NAME)
        install = _install(lock.method if lock else None)
        project = [asdict(f) for f in project_findings(root, installed, harness)]
    except MalformedLock as exc:
        install = "unreadable"
        project = [
            {"scope": "project", "code": "lock-unreadable", "section": "step-2", "facts": {"error": str(exc)}}
        ]
    return {
        "layers": describe(root),
        "configured": configured_at_all(root),
        "install": install,
        "listing_known": installed is not None,
        "project_findings": project,
        "shadowed": shadowed(root),
        "isolated": isolated_summary(root, today, home),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="setup_preflight.upgrade", description=__doc__.split("\n")[0])
    parser.add_argument("action", choices=["status", "record", "gather"])
    parser.add_argument("--project-root", default=".", type=Path)
    parser.add_argument("--version", help="record: the version upgraded to (default: the running one)")
    parser.add_argument(
        "--plugin-list",
        help="gather: harness plugin listing JSON to use instead of running it ('-' for stdin)",
    )
    args = parser.parse_args(argv)
    root: Path = args.project_root
    if args.action == "gather":
        harness, installed = read_installed(args.plugin_list)
        print(json.dumps(gather(root, installed, harness), indent=2, sort_keys=True))
        return 0
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
