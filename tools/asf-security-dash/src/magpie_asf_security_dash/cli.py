# SPDX-License-Identifier: Apache-2.0
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

"""Command line interface for the ASF Security dashboard bridge."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from magpie_asf_security_dash import cases
from magpie_asf_security_dash.client import DashError, check_pmc, fetch_reports, load_cookie, parse_reports


def main(argv: Sequence[str] | None = None) -> int:
    """Run the magpie-asf-security-dash command line interface."""
    args = _build_parser().parse_args(argv)
    pmc = check_pmc(args.pmc)
    raw = parse_reports(args.input.read_bytes()) if args.input else fetch_reports(pmc, load_cookie())
    found = cases.normalise(raw)

    result: Any
    if args.command == "cases":
        result = {"pmc": pmc, "cases": found}
    else:
        tracker = _read_json(args.tracker)
        if not isinstance(tracker, list):
            raise DashError(f"{args.tracker} must hold a JSON list of tracker issues")
        result = cases.reconcile(pmc, found, tracker)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DashError(f"cannot read {path}: {exc}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="magpie-asf-security-dash",
        description="Read-only bridge to the ASF Security dashboard (dash.security.apache.org).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (
        ("cases", "List the PMC's open cases."),
        ("reconcile", "Compare the PMC's open cases with the project's own tracker."),
    ):
        command = sub.add_parser(name, help=text, description=text)
        command.add_argument(
            "--pmc", required=True, help="PMC id, as the dashboard spells it (e.g. airflow)."
        )
        command.add_argument(
            "--input",
            type=Path,
            help="Read the reports API's JSON from this file instead of fetching it "
            "(e.g. saved from a signed-in browser).",
        )
        if name == "reconcile":
            command.add_argument(
                "--tracker",
                type=Path,
                required=True,
                help="JSON list of tracker issues: {id, url, state, decision, cves, message_ids}.",
            )
    return parser
