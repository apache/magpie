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
"""`release-config load|preflight` — JSON on stdout, exit 0 whenever JSON was written."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from release_config.config import load
from release_config.preflight import SKILLS, metadata, normalise_skill, preflight


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project-root", default=".", help="adopter repo root holding .apache-magpie-local/ and .apache-magpie-overrides/ (default: cwd)")
    common.add_argument("--config-dir", help="read every config file from this one directory instead of the layered lookup")
    common.add_argument(
        "--user-config", help="user.md to read (default: $APACHE_MAGPIE_USER_CONFIG, ~/.config/apache-magpie/user.md, <project-config>/user.md)"
    )
    common.add_argument("--skill", help=f"one of: {', '.join(SKILLS)} (a release- / magpie- prefix is accepted)")
    common.add_argument("args", nargs="*", help="the skill's positional arguments, as the RM typed them")
    # The skills' own flags. Planning-issue facts the skill read are passed as flags too.
    for flag in ("--planning-issue", "--release-branch", "--remote", "--previous-tag", "--result-vote-url", "--post-to"):
        common.add_argument(flag)
    for flag in (
        "--allow-unreviewed-archive",
        "--skip-repro-check",
        "--skip-repro",
        "--trusted-hardware",
        "--skip-empty-check",
        "--review-archive",
    ):
        common.add_argument(flag, action="store_true")
    common.add_argument("--skip-verify-check", metavar="REASON")
    common.add_argument("--expedited", metavar="REASON")
    common.add_argument("--skip-promote-wait", metavar="REASON")
    common.add_argument("--force-close", metavar="REASON")
    common.add_argument("--promote-timestamp", metavar="ISO-8601", help="announce-draft: promote commit time from the planning issue")
    common.add_argument("--download-page", metavar="URL")
    common.add_argument("--vote-opened", metavar="ISO-8601", help="vote-tally: when the [VOTE] thread opened, from the planning issue")
    common.add_argument("--now", metavar="ISO-8601", help="override the current UTC time (tests, evals)")
    common.add_argument("--rm", metavar="ID", help="promote: the RM's Apache ID, email or GitHub handle for the PMC gate")
    common.add_argument("--verify-binary", action="append", metavar="NAME=STATUS", help="promote: verify-rc Step 9 result per convenience artefact")
    common.add_argument("--fingerprint")
    common.add_argument("--keys-url")
    common.add_argument("--keyserver")

    parser = argparse.ArgumentParser(prog="release-config", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("load", parents=[common], help="parsed config, defaults applied, derived values; with --skill, that skill's Step 1 metadata")
    sub.add_parser("preflight", parents=[common], help="the skill's deterministic Step 0 checks: {ok, blockers, warnings, values}")
    return parser


def run(argv: list[str] | None = None) -> dict[str, Any]:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        skill = normalise_skill(args.skill) if args.skill else None
    except ValueError as exc:
        parser.error(str(exc))
    if args.command == "preflight" and skill is None:
        parser.error("preflight needs --skill")
    cfg = load(Path(args.project_root).resolve(), Path(args.config_dir).resolve() if args.config_dir else None, args.user_config)
    if args.command == "preflight":
        assert skill is not None
        return preflight(skill, cfg, args)
    return {
        "skill": skill,
        "sources": cfg.sources,
        "organization": cfg.organization,
        "config": cfg.config_with_defaults(),
        "build": cfg.build.as_dict(),
        "derived": {
            "signing_mode": cfg.signing_mode,
            "is_asf": cfg.is_asf,
            "non_asf": cfg.non_asf,
            "automated_signing_offered": cfg.automated_signing_offered,
            "automated_signing_source": cfg.automated_signing_source,
            "approver_roster_path": cfg.approver_roster_path,
            "release_lines": cfg.release_lines(),
        },
        "metadata": metadata(skill, cfg, args),
    }


def main(argv: list[str] | None = None) -> int:
    json.dump(run(argv), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
