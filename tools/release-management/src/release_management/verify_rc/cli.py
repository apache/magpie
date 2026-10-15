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
"""`release-management verify-rc …` — every command reads saved files, prints JSON and runs nothing.

`--load` is the JSON `release-config load --skill verify-rc <version>-rcN`
printed, saved to a file. The other file arguments are what the agent (or the
release manager) saved from a check's own run: a tool's JSON, RAT's report,
the Nexus probe output.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from release_management.cli import emit
from release_management.verify_rc import args as args_mod
from release_management.verify_rc import checks, jvm, nexus, report, repro
from release_management.verify_rc.common import VerifyError, VerifyRc

FAMILY = "verify-rc"


def _read(path: str | None) -> str | None:
    return None if path is None else Path(path).read_text(encoding="utf-8")


def _json(path: str | None) -> Any:
    text = _read(path)
    return None if text is None else json.loads(text)


def _load(args: argparse.Namespace) -> VerifyRc:
    return VerifyRc.from_load(_json(args.load))


def _names(args: argparse.Namespace) -> list[str] | None:
    return jvm.staged_names(_json(args.inventory), args.staged_dir)


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY, help="release-verify-rc: classify each check's saved output and render the report"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def with_load(name: str, help_text: str) -> argparse.ArgumentParser:
        p: argparse.ArgumentParser = commands.add_parser(name, help=help_text)
        p.add_argument(
            "--load", required=True, help="file holding `release-config load --skill verify-rc …` output"
        )
        return p

    p = with_load("args", "the release-verify invocations of Steps 1-3 and 5-8, from release-build.md")
    p.add_argument("--staging-copy", default="<staging-copy>", help="local copy of the staging directory")
    p.add_argument("--keys-file", default="<keys-file>", help="local copy of the project KEYS file")
    p.add_argument(
        "--unpacked-dir", help="unpacked source artefact (default: its filename without extension)"
    )
    p.add_argument("--previous-dir", help="directory holding the previous release's NOTICE and LICENSE")

    p = with_load("rat", "Step 4: RAT exit code and report → PASS / FAIL; no RAT config → SKIP + WARN")
    p.add_argument("--exit-code", type=int, help="RAT's exit code")
    p.add_argument("--report", help="file holding RAT's report / output")
    p.add_argument("--unpacked-dir")

    # `--load` is accepted (the skill's `<verify-rc>` prefix passes it to every command) but unused.
    p = with_load("source-tree", "Step 7: resolve release-verify symlinks' REVIEW from validator exit codes")
    p.add_argument("--symlinks", required=True, help="file holding `release-verify symlinks` JSON")
    p.add_argument(
        "--validator-result",
        action="append",
        default=[],
        metavar="CODE[:DETAIL]",
        help="one per validator, in validators_to_run order",
    )

    for name, help_text in (
        ("jvm", "Step 6b: gate, maven-artifact-verify recipe, and the report's classification"),
        (
            "nexus",
            "Step 6c: gates, id-shape check, read-only probe recipe, and the probe output's classification",
        ),
    ):
        p = with_load(name, help_text)
        p.add_argument("--inventory", help="file holding the Step 1 `release-verify inventory` JSON")
        p.add_argument("--staged-dir", help="local staging copy (listed for .jar / .pom)")
        if name == "jvm":
            p.add_argument(
                "--tree", help="unpacked source artefact (DISCLAIMER / DISCLAIMER-WIP → --podling)"
            )
            p.add_argument("--report", help="file holding maven-artifact-verify's JSON report")
        else:
            p.add_argument(
                "--issue-body", help="planning issue body (--post-to only), for a nexus-staging-repo: line"
            )
            p.add_argument(
                "--rm-credentials", action="store_true", help="the RM runs recipes 2-3 with their netrc"
            )
            p.add_argument("--not-probed", action="store_true", help="the sandbox refused the probe")
            p.add_argument("--existence-code", type=int, help="HTTP code recipe 1 printed")
            p.add_argument("--state", help="file holding what recipe 2 printed")
            p.add_argument("--profile", help="file holding what recipe 3 printed")
            p.add_argument("--crawl", help="file holding what recipe 4 printed")

    p = with_load("repro", "Step 9: mandatory / skip, recipe, and the status roll-up")
    p.add_argument("--skip-repro", action="store_true")
    p.add_argument("--trusted-hardware", action="store_true")
    p.add_argument("--recorded-commit", help="commit on the planning issue's reproducibility record")
    p.add_argument("--tag-commit", help='what `git rev-parse "<rc-tag>^{commit}"` printed')
    p.add_argument("--recorded-swhid", help="swh:1:dir: on the planning issue (qualifiers ignored)")
    p.add_argument("--atr-swhid", help="swh:1:dir: the ATR candidate page shows")
    p.add_argument("--epoch", type=int, help="recorded SOURCE_DATE_EPOCH")
    p.add_argument("--check", help="file holding `repro-archive check --json` output")
    p.add_argument("--compare", help="file holding `repro-archive compare --json` output")
    p.add_argument(
        "--binary",
        action="append",
        default=[],
        metavar="NAME=identical|differs|known:<pattern>",
        help="one per convenience artefact rebuilt",
    )
    p.add_argument("--upstream-clone", default="<upstream-clone>")
    p.add_argument("--remote", default="<remote>")
    p.add_argument("--staged-dir", default="<staged-dir>")

    p = with_load("report", "Step 10: attestation decision, report text and the --post-to comment")
    p.add_argument("--verdict", required=True, help="file holding `release-verify verdict` (or `all`) JSON")
    p.add_argument("--repro", help="file holding the Step 9 JSON (`verify-rc repro`)")
    p.add_argument("--compare", help="file holding `repro-archive compare --json` output (rebuilt sha512)")
    p.add_argument("--staging-url")
    p.add_argument("--utc", help="verification timestamp (default: now)")
    p.add_argument("--post-to", help="planning issue URL: render the comment to propose (never posted)")
    p.add_argument("--trusted-hardware", action="store_true")
    p.add_argument("--committer", help="GitHub handle of the person who passed --trusted-hardware")
    p.add_argument("--finding", action="append", default=[], metavar="STEP=TEXT")
    p.add_argument("--fail-detail", action="append", default=[])
    p.add_argument("--warn-detail", action="append", default=[])


def _run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "source-tree":
        return checks.source_tree(_json(args.symlinks), args.validator_result)
    v = _load(args)
    if args.command == "args":
        return args_mod.invocations(
            v,
            staging_copy=args.staging_copy,
            keys_file=args.keys_file,
            unpacked_dir=args.unpacked_dir,
            previous_dir=args.previous_dir,
        )
    if args.command == "rat":
        return checks.rat(
            v, report=_read(args.report), exit_code=args.exit_code, unpacked_dir=args.unpacked_dir
        )
    if args.command == "jvm":
        return jvm.jvm(
            v, names=_names(args), tree=args.tree, staged_dir=args.staged_dir, report_text=_read(args.report)
        )
    if args.command == "nexus":
        skipped, repo = nexus.gate(v, _names(args), _read(args.issue_body))
        if skipped is not None or repo is None:
            return skipped or {}
        return nexus.classify(
            v,
            repo,
            rm_credentials=args.rm_credentials,
            not_probed=args.not_probed,
            existence_code=args.existence_code,
            state_text=_read(args.state),
            profile_text=_read(args.profile),
            crawl_text=_read(args.crawl),
        )
    if args.command == "repro":
        return repro.reproducibility(
            v,
            skip_repro=args.skip_repro,
            trusted_hardware=args.trusted_hardware,
            recorded_commit=args.recorded_commit,
            tag_commit=args.tag_commit,
            recorded_swhid=args.recorded_swhid,
            atr_swhid=args.atr_swhid,
            epoch=args.epoch,
            check=_json(args.check),
            compare=_json(args.compare),
            binary_results=args.binary,
            clone=args.upstream_clone,
            remote=args.remote,
            staged_dir=args.staged_dir,
        )
    compare = _json(args.compare) or {}
    return report.report(
        v,
        _json(args.verdict),
        repro=_json(args.repro),
        rebuilt_sha512=compare.get("sha512_b"),
        staging_url=args.staging_url,
        utc=args.utc or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        post_to=args.post_to,
        trusted_hardware=args.trusted_hardware,
        committer=args.committer,
        findings=args.finding,
        fail_details=args.fail_detail,
        warn_details=args.warn_detail,
    )


def dispatch(args: argparse.Namespace) -> int:
    try:
        out = _run(args)
    except (VerifyError, OSError, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    emit(out)
    return 0
