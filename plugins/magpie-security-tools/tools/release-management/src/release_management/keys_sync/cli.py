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
"""`release-management keys-sync …` — every command prints JSON and runs nothing.

`--preflight` is what `release-config preflight --skill keys-sync …` printed,
`--load` what `release-config load --skill keys-sync` printed, and each
`--…-listing` what `release-verify list-keys --file <file>` printed, each
saved to a file. release-verify, not this tool, reads the keys with gpg.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from release_management.cli import emit
from release_management.keys_sync import check, render

FAMILY = "keys-sync"


def _json(path: str | None) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY,
        help="release-keys-sync: Step 0 KEYS lookup, Step 1 strength floor, Step 2 KEYS block and commands",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    verdict = commands.add_parser(
        "verdict", help="Step 0: is the fingerprint in KEYS, and under the keyserver's UID"
    )
    verdict.add_argument("--preflight", required=True, help="file holding `release-config preflight` output")
    verdict.add_argument(
        "--keys-listing", help="file holding `release-verify list-keys --file <KEYS>` output"
    )
    verdict.add_argument(
        "--key-listing", help="file holding `release-verify list-keys --file <fetched.asc>` output"
    )

    key = commands.add_parser("check", help="Step 1: the fetched key against the ASF strength floor")
    key.add_argument(
        "--key-listing", required=True, help="`release-verify list-keys --file <fetched.asc>` output"
    )
    key.add_argument("--fingerprint", required=True)
    key.add_argument("--today", help="YYYY-MM-DD; defaults to the current UTC date")

    keys_dir = commands.add_parser(
        "keys-dir", help="the svn directory holding KEYS (keys_file_url minus /KEYS)"
    )
    keys_dir.add_argument("--keys-url", required=True)

    render_p = commands.add_parser(
        "render", help="Step 2: the KEYS block, command sequence and upload reminder"
    )
    render_p.add_argument("--step", required=True, choices=["2"])
    render_p.add_argument("--preflight", required=True)
    render_p.add_argument(
        "--load", required=True, help="file holding `release-config load --skill keys-sync` output"
    )
    render_p.add_argument(
        "--check", required=True, help="file holding the Step 1 JSON (`keys-sync check` output)"
    )
    render_p.add_argument(
        "--key-file", required=True, help="the public key fetched from the keyserver (armoured)"
    )
    render_p.add_argument(
        "--key-listing",
        required=True,
        help="`release-verify list-keys --file <fetched.asc>` output, the listing Step 1 checked",
    )
    render_p.add_argument("--backend", choices=list(render.BACKENDS), help="default: from keys_file_url")


def dispatch(args: argparse.Namespace) -> int:
    try:
        if args.command == "verdict":
            out = render.verdict(_json(args.preflight), _json(args.keys_listing), _json(args.key_listing))
        elif args.command == "check":
            fpr = check.normalise_fpr(args.fingerprint)
            today = dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(dt.UTC).date()
            keys = check.listed_keys(_json(args.key_listing), "--key-listing")
            out = check.assess(check.find_key(keys, fpr), fpr, today)
        elif args.command == "keys-dir":
            out = check.keys_dir(args.keys_url)
        else:
            out = render.step2(
                _json(args.preflight),
                _json(args.load),
                _json(args.check),
                Path(args.key_file).read_text(encoding="utf-8", errors="replace"),
                _json(args.key_listing),
                backend=args.backend,
            )
    except render.RenderError as exc:
        emit({"ok": False, "refused": str(exc)})
        return 2
    except (check.InputError, OSError, ValueError) as exc:
        emit({"error": str(exc)})
        return 2
    emit(out)
    return 0
