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

"""Merge the derived Claude Code wiring into `.claude/settings.json`.

`setup adopt` Step 3 derives three things from `.apache-magpie.lock`: the
marketplace entry, the floor's `enabledPlugins` entries, and the MCP allows
for the families in the floor.  The merge rules are prose in `adopt.md`
because the file is not Magpie's: an adopter's settings carry whatever else
they put there, and the merge must touch only those three things.

This command performs that merge deterministically, so the step is a named
operation instead of code the agent composes.  It never removes or rewrites
an entry, never rewrites a pinned marketplace definition, and refuses a file
it cannot parse rather than replacing it.

Run it as a console script (`setup-settings-merge`, from the
`setup-preflight` workspace member) or as a module:

    python3 -m setup_preflight.settings_merge --write
    python3 -m setup_preflight.settings_merge --settings path/to/settings.json

The lock's `url` is a security boundary: only `apache/magpie` may be
merged from without asking.  The report names the repository it read, and
any other value is refused until `--accept-marketplace` confirms it in so
many words.

Without `--write` it reports what the merge would do and leaves the file
untouched.  The report is JSON:

    {"action": "create" | "merge" | "refuse", "keys_preserved": [...],
     "plugins_added": [...], "allows_added": [...],
     "plugins_removed": [...], "marketplace_definition_changed": true | false,
     "marketplace_repo": "apache/magpie"}
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .lockfile import Lock, MalformedLock, load

HERE = Path(__file__).resolve().parent
DEFAULT_SETTINGS = Path(".claude/settings.json")
DEFAULT_LOCK = Path(".apache-magpie.lock")
DEFAULT_REGISTRY = HERE / "family-mcp-allows.json"
MARKETPLACE = "apache-magpie"
DEFAULT_REPO = "apache/magpie"
VETTED_OPS = "magpie-vetted-ops"
TOUCHED_KEYS = ("extraKnownMarketplaces", "enabledPlugins")


class Refused(ValueError):
    """The settings file exists but cannot be merged safely."""

    def __init__(self, message: str, report: dict | None = None) -> None:
        super().__init__(message)
        self.report = report or {}


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Refused(f"{path} does not parse as JSON: {exc}") from exc


def _object(container: dict, key: str, path: Path) -> dict:
    if key not in container:
        return {}
    value = container[key]
    if not isinstance(value, dict):
        raise Refused(f"{path}: `{key}` is not a JSON object")
    return value


def _list(container: dict, key: str, path: Path) -> list:
    if key not in container:
        return []
    value = container[key]
    if not isinstance(value, list):
        raise Refused(f"{path}: `{key}` is not a JSON list")
    return value


def derived_plugins(lock: Lock) -> list[str]:
    """The floor's plugins, in lock order, with the vetted-ops plugin ensured."""
    plugins = list(lock.plugins)
    if VETTED_OPS not in plugins:
        plugins.append(VETTED_OPS)
    return plugins


def derived_allows(plugins: list[str], registry: dict) -> list[str]:
    """The MCP allows the floor's families derive, in registry order."""
    families = {plugin.removeprefix("magpie-") for plugin in plugins}
    allows: list[str] = []
    servers = registry.get("servers", {})
    if not isinstance(servers, dict):
        raise Refused("registry: `servers` is not an object")
    for server, entry in servers.items():
        if not isinstance(entry, dict):
            continue
        served = entry.get("families", [])
        if not isinstance(served, list) or not families.intersection(served):
            continue
        for tool in entry.get("tools", []):
            allows.append(f"mcp__{server}__{tool}")
    return allows


def merge(
    settings: dict,
    plugins: list[str],
    allows: list[str],
    repo: str,
    path: Path,
) -> tuple[dict, dict]:
    """Apply the merge rules in place, returning the report."""
    keys_preserved = [key for key in settings if key not in TOUCHED_KEYS]

    marketplaces = _object(settings, "extraKnownMarketplaces", path)
    settings["extraKnownMarketplaces"] = marketplaces
    marketplace_definition_changed = MARKETPLACE not in marketplaces
    if marketplace_definition_changed:
        marketplaces[MARKETPLACE] = {"source": {"source": "github", "repo": repo}}

    enabled = _object(settings, "enabledPlugins", path)
    settings["enabledPlugins"] = enabled
    plugins_added = []
    for plugin in plugins:
        key = f"{plugin}@{MARKETPLACE}"
        if key not in enabled:
            enabled[key] = True
            plugins_added.append(key)

    permissions = _object(settings, "permissions", path)
    allow = _list(permissions, "allow", path)
    allows_added = [entry for entry in dict.fromkeys(allows) if entry not in allow]
    if allows_added:
        permissions["allow"] = allow + allows_added
        settings["permissions"] = permissions

    report = {
        "action": "merge",
        "keys_preserved": keys_preserved,
        "plugins_added": plugins_added,
        "allows_added": allows_added,
        "plugins_removed": [],
        "marketplace_definition_changed": marketplace_definition_changed,
        "marketplace_repo": repo,
    }
    return settings, report


def _write(path: Path, settings: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
        if path.exists():
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def run(
    settings_path: Path,
    lock_path: Path,
    registry_path: Path,
    write: bool,
    accept_marketplace: bool = False,
) -> dict:
    try:
        lock = load(lock_path)
    except MalformedLock as exc:
        raise Refused(str(exc)) from exc
    if lock is None:
        raise Refused(f"{lock_path} does not exist: there is no adoption floor to wire")
    if not lock.plugins:
        raise Refused(f"{lock_path} names no plugins: adoption has no floor to wire")

    repo = lock.url or DEFAULT_REPO
    if repo != DEFAULT_REPO and not accept_marketplace:
        raise Refused(
            f"{lock_path} names the marketplace {repo!r}: merging from any marketplace other "
            f"than {DEFAULT_REPO!r} is confirmed first. Re-run with --accept-marketplace to "
            "merge from it.",
            {"marketplace_repo": repo},
        )

    try:
        registry = _read_json(registry_path)
        if not isinstance(registry, dict):
            raise Refused(f"{registry_path} is not a JSON object")

        plugins = derived_plugins(lock)
        allows = derived_allows(plugins, registry)

        if settings_path.exists():
            original = _read_json(settings_path)
            if not isinstance(original, dict):
                raise Refused(f"{settings_path} is not a JSON object")
            settings, report = merge(original, plugins, allows, repo, settings_path)
        else:
            settings, report = merge({}, plugins, allows, repo, settings_path)
            report["action"] = "create"
    except Refused as exc:
        exc.report.setdefault("marketplace_repo", repo)
        raise

    unchanged = not (
        report["plugins_added"] or report["allows_added"] or report["marketplace_definition_changed"]
    )
    if write and not unchanged:
        _write(settings_path, settings)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="setup-settings-merge",
        description="Merge the derived Claude Code wiring into .claude/settings.json.",
    )
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help="family MCP allowlist (default: the copy shipped beside setup_preflight)",
    )
    parser.add_argument("--write", action="store_true", help="write the merged file")
    parser.add_argument(
        "--accept-marketplace",
        action="store_true",
        help=f"merge from the marketplace the lock names even when it is not {DEFAULT_REPO}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run(args.settings, args.lock, args.registry, args.write, args.accept_marketplace)
    except Refused as exc:
        print(f"setup-settings-merge: {exc}", file=sys.stderr)
        refused = {
            "action": "refuse",
            "keys_preserved": [],
            "plugins_added": [],
            "allows_added": [],
            "plugins_removed": [],
            "marketplace_definition_changed": False,
            "marketplace_repo": None,
        }
        refused.update(exc.report)
        print(json.dumps(refused))
        return 2
    except (OSError, ValueError) as exc:
        print(f"setup-settings-merge: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
