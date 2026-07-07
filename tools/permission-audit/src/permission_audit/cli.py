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
"""CLI front-end for the permission allow-list audit + edit tool.

Two subcommands:

- ``audit``  — read a settings file, classify allow-list entries
  against the forbidden and family-scoped recommended lists, print
  findings as JSON for the calling skill to surface.

- ``apply`` — atomic add/remove against `.permissions.allow[]`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from permission_audit.audit import (
    FORBIDDEN_PATTERNS,
    RECOMMENDED_BY_FAMILY,
    audit_settings,
)
from permission_audit.edit import apply_changes
from permission_audit.kiro import audit_kiro
from permission_audit.opencode import audit_opencode


def _read_allow(settings_path: Path) -> list[str]:
    if not settings_path.exists():
        return []
    raw = settings_path.read_text(encoding="utf-8")
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"{settings_path}: invalid JSON: {e}\n")
        raise SystemExit(2) from e
    perms = data.get("permissions", {}) if isinstance(data, dict) else {}
    allow = perms.get("allow", []) if isinstance(perms, dict) else []
    if not isinstance(allow, list):
        sys.stderr.write(f"{settings_path}: .permissions.allow is not a list\n")
        raise SystemExit(2)
    return [e for e in allow if isinstance(e, str)]


def _cmd_audit(args: argparse.Namespace) -> int:
    settings_path = Path(args.settings_path).resolve()
    allow = _read_allow(settings_path)
    families = [f.strip() for f in (args.families or "").split(",") if f.strip()]
    result = audit_settings(allow, families)

    output = {
        "settings_path": str(settings_path),
        "file_exists": settings_path.exists(),
        "allow_count": len(allow),
        "families": families,
        "forbidden": [asdict(f) for f in result.forbidden],
        "missing_recommended": [asdict(f) for f in result.missing_recommended],
    }
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    # Exit non-zero on forbidden hits so a shell caller can pipeline.
    return 1 if result.forbidden else 0


def _cmd_apply(args: argparse.Namespace) -> int:
    settings_path = Path(args.settings_path).resolve()
    additions = list(args.add or [])
    removals = list(args.remove or [])
    if not additions and not removals:
        sys.stderr.write("nothing to do — pass --add and/or --remove\n")
        return 2
    outcome = apply_changes(
        settings_path=settings_path,
        additions=additions,
        removals=removals,
        create_if_missing=args.create_if_missing,
    )
    output = {
        "settings_path": str(settings_path),
        "file_was_created": outcome.file_was_created,
        "added": outcome.added,
        "removed": outcome.removed,
    }
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _read_opencode_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    raw = config_path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"{config_path}: invalid JSON: {e}\n")
        raise SystemExit(2) from e
    return data if isinstance(data, dict) else {}


def _cmd_audit_opencode(args: argparse.Namespace) -> int:
    config_path = Path(args.config_path).resolve()
    config = _read_opencode_config(config_path)
    result = audit_opencode(config)

    output = {
        "config_path": str(config_path),
        "file_exists": config_path.exists(),
        "harness": "opencode",
        "forbidden": [asdict(f) for f in result.forbidden],
    }
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 1 if result.forbidden else 0


def _cmd_audit_kiro(args: argparse.Namespace) -> int:
    config_path = Path(args.config_path).resolve()
    config = _read_opencode_config(config_path)
    result = audit_kiro(config)

    output = {
        "config_path": str(config_path),
        "file_exists": config_path.exists(),
        "harness": "kiro",
        "forbidden": [asdict(f) for f in result.forbidden],
    }
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 1 if result.forbidden else 0


def _cmd_list_known(args: argparse.Namespace) -> int:
    output = {
        "forbidden_patterns": sorted(FORBIDDEN_PATTERNS),
        "recommended_by_family": {k: sorted(v) for k, v in RECOMMENDED_BY_FAMILY.items()},
    }
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="permission-audit",
        description=(
            "Audit + atomically edit Claude Code permissions.allow[] entries "
            "in .claude/settings.json / .claude/settings.local.json; and "
            "audit an OpenCode opencode.json permission config (audit-opencode)."
        ),
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    p_audit = subparsers.add_parser("audit", help="Audit an existing settings file.")
    p_audit.add_argument("settings_path", help="Path to .claude/settings*.json file.")
    p_audit.add_argument(
        "--families",
        default="",
        help="Comma-separated opt-in family names (e.g. 'security,issue').",
    )
    p_audit.set_defaults(func=_cmd_audit)

    p_apply = subparsers.add_parser("apply", help="Atomically add/remove allow-list entries.")
    p_apply.add_argument("settings_path", help="Path to .claude/settings*.json file.")
    p_apply.add_argument(
        "--add",
        action="append",
        default=[],
        help="Allow-list entry to add (repeatable).",
    )
    p_apply.add_argument(
        "--remove",
        action="append",
        default=[],
        help="Allow-list entry to remove (repeatable).",
    )
    p_apply.add_argument(
        "--create-if-missing",
        action="store_true",
        help="Create the settings file if it does not exist.",
    )
    p_apply.set_defaults(func=_cmd_apply)

    p_audit_oc = subparsers.add_parser(
        "audit-opencode",
        help="Audit an OpenCode opencode.json permission config for over-permissioning.",
    )
    p_audit_oc.add_argument("config_path", help="Path to opencode.json.")
    p_audit_oc.set_defaults(func=_cmd_audit_opencode)

    p_audit_kiro = subparsers.add_parser(
        "audit-kiro",
        help="Audit a Kiro CLI agent-config (.kiro/agents/<name>.json) for over-permissioning.",
    )
    p_audit_kiro.add_argument("config_path", help="Path to a Kiro agent config JSON.")
    p_audit_kiro.set_defaults(func=_cmd_audit_kiro)

    p_known = subparsers.add_parser(
        "list-known",
        help="Print the canonical forbidden + recommended-by-family lists.",
    )
    p_known.set_defaults(func=_cmd_list_known)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
