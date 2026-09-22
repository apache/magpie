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

"""The command a skill's pre-flight runs, and the JSON it answers with.

One invocation, one verdict.  `{"verdict": "ok"}` means continue in
silence and is the overwhelmingly common answer; anything else lists
findings, each naming the `preflight-detail.md` section whose rules apply.
The agent never interprets the state itself — that is the whole point of
the command existing.

**Exit status is always 0 for a verdict.**  A finding is not an error; it
is the answer.  A non-zero exit means the check itself could not run, and
the caller falls back to reading the detail file rather than assuming the
project is fine.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .core import (
    DEFAULT_VERIFY_INTERVAL_DAYS,
    Verdict,
    cached_project_findings,
    skill_findings,
    verify_findings,
)
from .lockfile import MalformedLock


def read_installed(explicit: str | None) -> dict[str, str] | None:
    """The installed plugin map, or `None` for *unknown* — never `{}` for it.

    `--plugin-list` lets the caller supply what it already read; otherwise
    the harness CLI is asked directly.  Every failure mode collapses to
    `None`: the command missing, a non-zero exit, unparsable output, or a
    sandbox that denies the plugin cache.  The one case that is *not*
    unknown is a listing that parsed and was genuinely empty, which only a
    harness with no plugins installed produces.
    """
    if explicit is not None:
        text = sys.stdin.read() if explicit == "-" else Path(explicit).read_text(encoding="utf-8")
    else:
        try:
            completed = subprocess.run(
                ["claude", "plugin", "list", "--json"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        text = completed.stdout
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    installed: dict[str, str] = {}
    for entry in parsed:
        if not isinstance(entry, dict):
            return None
        name, version = entry.get("name"), entry.get("version")
        if isinstance(name, str) and isinstance(version, str):
            installed[name] = version
    # An empty *parsed* list inside a sandbox is the read-denied case, and
    # is indistinguishable from a genuinely plugin-free harness. Unknown is
    # the safe reading of the ambiguity: it proposes nothing.
    return installed or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="setup-preflight",
        description="Resolve this project's Magpie setup state and one skill's fingerprint.",
    )
    parser.add_argument("--skill", required=True, help="the skill's frontmatter `name:`")
    parser.add_argument("--hash", dest="surface_hash", help="that skill's `surface_hash:`")
    parser.add_argument(
        "--requires",
        action="append",
        default=[],
        metavar="FILE",
        help="one `requires_config:` entry; repeat for each",
    )
    parser.add_argument("--project-root", default=".", type=Path)
    parser.add_argument(
        "--plugin-list",
        metavar="PATH",
        help="`claude plugin list --json` output to use instead of running it ('-' for stdin)",
    )
    parser.add_argument(
        "--verify-interval-days",
        type=int,
        default=DEFAULT_VERIFY_INTERVAL_DAYS,
        help="0 disables the periodic verify suggestion",
    )
    parser.add_argument(
        "--no-rules",
        action="store_true",
        help="omit each finding's rules text (the verdict alone)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="recompute the project scope instead of reusing a recent identical verdict",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.project_root

    try:
        installed = read_installed(args.plugin_list)
        if args.no_cache:
            from .core import project_findings

            project, cached = project_findings(root, installed), False
        else:
            project, cached = cached_project_findings(root, installed)
        findings = [
            *project,
            *skill_findings(root, args.skill, args.surface_hash, args.requires),
            *verify_findings(root, args.verify_interval_days),
        ]
    except MalformedLock as exc:
        print(f"setup-preflight: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"setup-preflight: {exc}", file=sys.stderr)
        return 2

    verdict = Verdict("action" if findings else "ok", findings, project_cached=cached)
    print(verdict.to_json(with_rules=not args.no_rules))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
