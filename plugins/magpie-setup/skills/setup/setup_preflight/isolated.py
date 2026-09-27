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

"""The isolated (secure agent) setup: has it changed, and is a re-check due?

The secure setup is installed per machine, from framework files: the
sandbox wrapper and helper scripts, the agent-guard engine, the container
gateway, and the dogfooded `.claude/settings.json`.  When a framework
upgrade changes any of those, the user's installed copy can be behind
without anything saying so.  `setup-isolated-setup-update` is the skill
that finds that drift, so the pre-flight proposes it:

* **once per change** — the fingerprint of those files moved since the
  update skill last ran on this machine; and
* **on a timer** — the update was last run or last suggested longer ago
  than the configured interval (a week by default), because the pinned
  tools and harness move upstream whatever this repository does.

Only when the setup is **used here**: an `isolated_setup` block in the
local stamp (written by the install and update skills), or a project
`.claude/settings*.json` that enables the sandbox.  Anyone else is never
told about it.

The fingerprint is computed from the framework source when this checkout
has it — the framework's own tree, or a pinned snapshot under
`.apache-magpie/` — and otherwise taken from the constant generated into
`isolated_fingerprint.py`.  The constant is what a marketplace install
sees: the copy of this package in `.apache-magpie-local/` is refreshed by
`/magpie-setup upgrade`, which is exactly the moment the constant moves.

Run as a module it also records what happened, so nothing hand-writes a
fingerprint into the stamp:

    python3 -m setup_preflight.isolated record-update     # the update skill ran
    python3 -m setup_preflight.isolated record-reminder   # the suggestion was shown
    python3 -m setup_preflight.isolated fingerprint       # print the current value
    python3 -m setup_preflight.isolated write-constant    # framework repo only (prek)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

#: The files a secure-setup install copies or mirrors, relative to the
#: framework root.  Documentation is left out on purpose: a reworded
#: paragraph changes nothing on the user's machine and must not send them
#: to re-run the update.
SOURCES: tuple[str, ...] = (
    ".claude/settings.json",
    "tools/agent-guard/src",
    "tools/agent-isolation",
    "tools/container-gateway/src",
)
_SKIP_DIRS = frozenset({"__pycache__", "tests", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
_SKIP_SUFFIXES = (".md", ".pyc")
_SKIP_NAMES = frozenset({".DS_Store"})

#: The directory whose presence marks a tree as carrying the framework source.
_MARKER = "tools/agent-isolation"
SNAPSHOT_DIR = ".apache-magpie"

LOCAL_DIR = ".apache-magpie-local"
STAMP_NAME = "reconciled.json"
BLOCK = "isolated_setup"

DEFAULT_INTERVAL_DAYS = 7
INTERVAL_KEY = "isolated_setup_update_interval_days"
_INTERVAL_RE = re.compile(rf"^\s*{INTERVAL_KEY}\s*:\s*(\d+)\b", re.M)


def _files(base: Path) -> list[Path]:
    found: list[Path] = []
    for source in SOURCES:
        path = base / source
        if path.is_file():
            found.append(path)
            continue
        if not path.is_dir():
            continue
        for candidate in path.rglob("*"):
            relative = candidate.relative_to(base)
            if not candidate.is_file() or _SKIP_DIRS.intersection(relative.parts):
                continue
            if candidate.name in _SKIP_NAMES or candidate.name.endswith(_SKIP_SUFFIXES):
                continue
            found.append(candidate)
    return sorted(found, key=lambda p: p.relative_to(base).as_posix())


def compute(base: Path) -> str | None:
    """The fingerprint of `SOURCES` under `base`, or `None` if none exist."""
    files = _files(base)
    if not files:
        return None
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(base).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()[:16]


def shipped() -> str | None:
    """The fingerprint generated into this package, if the constant exists."""
    try:
        from .isolated_fingerprint import FRAMEWORK_FINGERPRINT
    except ImportError:
        return None
    return FRAMEWORK_FINGERPRINT


def current(root: Path) -> str | None:
    """The framework's current fingerprint, as seen from this checkout."""
    for base in (root, root / SNAPSHOT_DIR):
        if (base / _MARKER).is_dir():
            return compute(base)
    return shipped()


def sandbox_enabled_in_project(root: Path) -> bool:
    for name in ("settings.json", "settings.local.json"):
        path = root / ".claude" / name
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        sandbox = loaded.get("sandbox") if isinstance(loaded, dict) else None
        if isinstance(sandbox, dict) and sandbox.get("enabled") is True:
            return True
    return False


def interval_days(root: Path) -> int:
    """`isolated_setup_update_interval_days`, personal config first.

    Read from `.apache-magpie-local/project.md`, then
    `.apache-magpie-overrides/project.md`; a week when neither sets it.
    `0` turns the timed reminder off (a change is still reported).
    """
    for directory in (LOCAL_DIR, ".apache-magpie-overrides"):
        path = root / directory / "project.md"
        try:
            match = _INTERVAL_RE.search(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if match:
            return int(match.group(1))
    return DEFAULT_INTERVAL_DAYS


# --- recording ----------------------------------------------------------------------


def _stamp_path(root: Path) -> Path:
    return root / LOCAL_DIR / STAMP_NAME


def _load_stamp(root: Path) -> dict[str, object]:
    try:
        loaded = json.loads(_stamp_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def record(root: Path, event: str, today: date | None = None) -> dict[str, object]:
    """Write what just happened into the local stamp and return the block.

    `update` — the update skill ran here: its fingerprint is now the one it
    checked against.  `reminder` — the suggestion was shown, taken or not,
    which re-arms both the timer and this particular change.
    """
    stamp = _load_stamp(root)
    raw = stamp.get(BLOCK)
    block: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
    day = (today or date.today()).isoformat()
    fingerprint = current(root)
    if event == "update":
        block["updated_at"] = day
        if fingerprint:
            block["fingerprint"] = fingerprint
    elif event == "reminder":
        block["reminded_at"] = day
    else:
        raise ValueError(f"unknown event {event!r}")
    if fingerprint:
        block["acknowledged"] = fingerprint
    stamp[BLOCK] = block
    path = _stamp_path(root)
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return block


# --- the generated constant ---------------------------------------------------------

CONSTANT_PATH = Path(__file__).with_name("isolated_fingerprint.py")
_CONSTANT_TEMPLATE = '''\
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

"""Generated by `python -m setup_preflight.isolated write-constant`. Do not edit.

The isolated-setup fingerprint of the framework this package shipped with,
for installs that do not carry the framework source (see `isolated.py`).
"""

FRAMEWORK_FINGERPRINT = "{value}"
'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="setup_preflight.isolated", description=__doc__.split("\n")[0])
    parser.add_argument(
        "action",
        choices=["fingerprint", "record-update", "record-reminder", "write-constant", "check-constant"],
    )
    parser.add_argument("--project-root", default=".", type=Path)
    args = parser.parse_args(argv)
    root: Path = args.project_root

    if args.action == "fingerprint":
        print(current(root) or "")
        return 0
    if args.action in ("record-update", "record-reminder"):
        block = record(root, args.action.removeprefix("record-"))
        print(json.dumps({BLOCK: block}, indent=2, sort_keys=True))
        return 0

    value = compute(root)
    if value is None:
        print(f"{args.action}: no isolated-setup sources under {root}", file=sys.stderr)
        return 2
    wanted = _CONSTANT_TEMPLATE.format(value=value)
    have = CONSTANT_PATH.read_text(encoding="utf-8") if CONSTANT_PATH.exists() else ""
    if have == wanted:
        return 0
    if args.action == "check-constant":
        print(f"{CONSTANT_PATH.name} is stale; run write-constant", file=sys.stderr)
        return 1
    CONSTANT_PATH.write_text(wanted, encoding="utf-8")
    print(f"{CONSTANT_PATH.name}: {value}")
    return 1  # a fixer that changed a file fails the hook, as prek expects


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
