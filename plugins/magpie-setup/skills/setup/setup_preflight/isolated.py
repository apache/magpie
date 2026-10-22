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
sees: the copy of this package in the personal config layer (see
`layers.py`) is refreshed by `/magpie-setup upgrade`, which is exactly the
moment the constant moves.

Run as a module it also records what happened, so nothing hand-writes a
fingerprint into the stamp:

    python3 -m setup_preflight.isolated record-update     # the update skill ran
    python3 -m setup_preflight.isolated record-reminder   # the suggestion was shown
    python3 -m setup_preflight.isolated fingerprint       # print the current value
    python3 -m setup_preflight.isolated configured        # {"configured": true|false}
    python3 -m setup_preflight.isolated session-start     # the SessionStart hook's output
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

from .layers import OVERRIDES_DIR, adopted, config_layers, personal_dir, personal_layers

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


def _sandbox_enabled(paths: list[Path]) -> bool:
    for path in paths:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        sandbox = loaded.get("sandbox") if isinstance(loaded, dict) else None
        if isinstance(sandbox, dict) and sandbox.get("enabled") is True:
            return True
    return False


def sandbox_enabled_in_project(root: Path) -> bool:
    return _sandbox_enabled([root / ".claude" / name for name in ("settings.json", "settings.local.json")])


def configured(root: Path, home: Path | None = None) -> bool:
    """Whether the isolated setup is in place for this project on this machine.

    The stamp the install and update skills write, or a sandbox the project's
    or the user's Claude Code settings enable. The install offers a whole-user
    scope, which leaves no trace in the project, hence the user settings. A
    file that cannot be read counts as not configured: inside the sandbox the
    user's settings are read-denied, so callers that run there see `False` and
    must treat it as "not known to be configured", never as proof of absence.
    """
    block = _load_stamp(root).get(BLOCK)
    if isinstance(block, dict) and block:
        return block.get("enabled") is not False
    user = (home if home is not None else Path.home()) / ".claude" / "settings.json"
    return sandbox_enabled_in_project(root) or _sandbox_enabled([user])


#: Shown to the user once per session, at session start, while the isolated
#: setup is not configured. Not a blocker: trying Magpie out does not need it.
UNCONFIGURED_WARNING = """\
Apache Magpie: the isolated setup is not configured on this machine.

You do not need it to try Magpie out. If you plan to use Magpie for longer, \
enable it: run /magpie-setup:isolated-setup-install.

Why it matters: Magpie skills read text written by other people - pull \
requests, issues, comments, mailing-list threads, attachments. Any of it can \
hide instructions aimed at your agent (prompt injection). Without the isolated \
setup the agent runs with your full access: it can read your credentials (SSH \
keys, GitHub and cloud tokens, .env files), reach any host on the network, and \
act in your name. An injected instruction could leak those secrets or private \
content such as unreleased security reports, or push, comment, close or merge \
as you.

Until it is enabled, do not use Magpie on untrusted content - pull requests, \
issues, comments or mail from people you do not know - and read every command \
before you approve it."""

#: What the model is told alongside the warning, so it neither repeats the
#: warning on every turn nor forgets it at the moment it matters.
UNCONFIGURED_CONTEXT = (
    "The Apache Magpie isolated setup is not configured on this machine. The user was shown a "
    "warning about it at session start; do not repeat it unprompted. Before a Magpie skill reads "
    "pull requests, issues, comments, mail or other content written by people outside the project, "
    "remind the user once in this session that the isolated setup is off, and suggest "
    "/magpie-setup:isolated-setup-install."
)


WARNING_KEY = "isolation_warning"
_WARNING_OFF_RE = re.compile(rf"^\s*{WARNING_KEY}\s*:\s*off\b", re.M)


def warning_opted_out(root: Path) -> bool:
    """Whether the project turned the warning off when it adopted Magpie.

    Read from the committed `.apache-magpie-overrides/project.md` only: it is
    the project's choice, made at adoption, not one a personal layer makes.
    """
    try:
        text = (root / OVERRIDES_DIR / "project.md").read_text(encoding="utf-8")
    except OSError:
        return False
    return _WARNING_OFF_RE.search(text) is not None


def _adopted_root(start: Path) -> Path | None:
    """The adopted repository `start` sits in: up to the first `.git`, never past it."""
    for directory in (start, *start.parents):
        if adopted(directory):
            return directory
        if (directory / ".git").exists():
            return None
    return None


def session_start(root: Path, notice: str = "", home: Path | None = None) -> str:
    """What the SessionStart hook prints: its own notice, plus the warning while unconfigured.

    The hook fires once per session, which is the cadence the warning wants.
    Only in a repository that has adopted Magpie, and not when that project
    opted out at adoption. Hooks run outside the sandbox, so the user's
    settings are readable here and "not configured" means what it says.
    Plain text keeps the hook's original output when there is nothing to
    warn about.
    """
    project = _adopted_root(root.resolve())
    if project is None or warning_opted_out(project) or configured(project, home):
        return notice
    context = "\n\n".join(part for part in (notice, UNCONFIGURED_CONTEXT) if part)
    return json.dumps(
        {
            "systemMessage": UNCONFIGURED_WARNING,
            "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context},
        }
    )


def interval_days(root: Path) -> int:
    """`isolated_setup_update_interval_days`, personal config first.

    Read from `project.md` in each config layer in turn (`layers.py`:
    personal, legacy in-tree, then `.apache-magpie-overrides/`); a week when
    none sets it.  `0` turns the timed reminder off (a change is still
    reported).
    """
    for directory in config_layers(root):
        path = directory / "project.md"
        try:
            match = _INTERVAL_RE.search(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if match:
            return int(match.group(1))
    return DEFAULT_INTERVAL_DAYS


# --- recording ----------------------------------------------------------------------


class NoPersonalLayer(RuntimeError):
    """An unadopted project outside a git repository has nowhere to record."""


def _stamp_path(root: Path) -> Path:
    home = personal_dir(root)
    if home is None:
        raise NoPersonalLayer(
            f"{root} has not adopted Magpie and is not a git repository; "
            "there is no personal config layer to record into"
        )
    return home / STAMP_NAME


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


def record(root: Path, event: str, today: date | None = None) -> dict[str, object]:
    """Write what just happened into the local stamp and return the block.

    `update` — the update skill ran here: its fingerprint is now the one it
    checked against.  `reminder` — the suggestion was shown, taken or not,
    which re-arms both the timer and this particular change.

    The stamp is written to the personal layer, which this creates when it
    does not exist yet (inside the git directory for an unadopted
    repository, never the working tree).  A stamp still in the legacy
    in-tree directory is read and carried over, not deleted.
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
    path.parent.mkdir(parents=True, exist_ok=True)
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
        choices=[
            "fingerprint",
            "configured",
            "session-start",
            "record-update",
            "record-reminder",
            "write-constant",
            "check-constant",
        ],
    )
    parser.add_argument("--project-root", default=".", type=Path)
    parser.add_argument("--notice", default="", help="session-start: the hook's own notice, passed through")
    args = parser.parse_args(argv)
    root: Path = args.project_root

    if args.action == "fingerprint":
        print(current(root) or "")
        return 0
    if args.action == "configured":
        print(json.dumps({"configured": configured(root)}))
        return 0
    if args.action == "session-start":
        output = session_start(root, args.notice)
        if output:
            print(output)
        return 0
    if args.action in ("record-update", "record-reminder"):
        try:
            block = record(root, args.action.removeprefix("record-"))
        except NoPersonalLayer as exc:
            print(f"{args.action}: {exc}", file=sys.stderr)
            return 2
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
