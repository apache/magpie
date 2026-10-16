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
    Finding,
    Verdict,
    cached_project_findings,
    isolated_setup_findings,
    skill_findings,
    verify_findings,
    welcome_findings,
)
from .delegation import findings as delegation_findings
from .lockfile import MalformedLock

#: Each harness's own plugin-listing command, in probe order.  The floor
#: must be readable on every harness, not only Claude Code: a missing
#: `claude` binary on Codex or Gemini CLI is that harness answering with
#: its own listing (`install.md` Step M5), never *unknown*.  The first
#: binary that exists decides the answer; a listing it cannot read is
#: unknown, and a machine running none of them stays unknown too.
HARNESS_LISTINGS: tuple[tuple[str, list[str]], ...] = (
    ("claude-code", ["claude", "plugin", "list", "--json"]),
    ("codex", ["codex", "plugin", "list"]),
    ("gemini", ["gemini", "extensions", "list"]),
)


def _parse_listing(text: str) -> dict[str, str] | None:
    """One harness listing, parsed into the shared `{name: version}` map.

    Shared by every harness's listing command: `None` for unknown (the
    output did not parse, or an empty parsed listing leaves the sandbox
    read-denial ambiguity standing), never an empty map.
    """
    try:
        listing = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(listing, list):
        return None
    out: dict[str, str] = {}
    for item in listing:
        if not isinstance(item, dict):
            return None
        version = item.get("version")
        if isinstance(item.get("name"), str) and isinstance(version, str):
            out[item["name"]] = version
    # A listing that parses but is empty leaves the sandbox read-denial
    # ambiguity standing, so we report unknown rather than an empty map.
    return out or None


def read_installed(explicit: str | None) -> dict[str, str] | None:
    """The installed plugin map, or `None` for *unknown* — never `{}` for it.

    `--plugin-list` lets the caller supply what it already read; otherwise
    each harness's own listing command is probed in order and the first
    binary that exists answers for the machine.  Every failure mode
    collapses to `None`: the command missing, a non-zero exit, unparsable
    output, or a sandbox that denies the plugin cache.  The one case that
    is *not* unknown is a listing that parsed and was genuinely empty,
    which only a harness with no plugins installed produces.
    """
    if explicit is not None:
        text = sys.stdin.read() if explicit == "-" else Path(explicit).read_text(encoding="utf-8")
        return _parse_listing(text)
    for _harness, argv in HARNESS_LISTINGS:
        try:
            completed = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except (OSError, subprocess.SubprocessError):
            # The binary is not on PATH: this is not the running harness,
            # so the next harness's own command decides.
            continue
        if completed.returncode != 0:
            return None
        return _parse_listing(completed.stdout)
    # No harness CLI exists on this machine: nothing was ever installed
    # with one, and unknown stays the safe reading.
    return None


def _delegation(root: Path, skill: str) -> list[Finding]:
    """Delegation findings, never fatal to the verdict.

    Unreadable override files are already reported per file; anything worse
    (a layer directory that cannot be listed) drops delegation for this run,
    which leaves the framework default -- the safe reading -- in charge.
    """
    try:
        return delegation_findings(root, skill)
    except OSError:
        return []


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
        "--isolated-setup-interval-days",
        type=int,
        default=None,
        help="days between isolated-setup-update reminders (default: the "
        "`isolated_setup_update_interval_days` config key, else 7); 0 disables the timer",
    )
    parser.add_argument(
        "--no-welcome",
        action="store_true",
        help="omit the skill family's first-run welcome guide",
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
            *([] if args.no_welcome else welcome_findings(root, args.skill)),
            *project,
            *skill_findings(root, args.skill, args.surface_hash, args.requires),
            *_delegation(root, args.skill),
            *isolated_setup_findings(root, args.isolated_setup_interval_days),
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
