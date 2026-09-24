#
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
"""
``adversarial-review detect``  — which reviewer CLIs are installed, and which one is running this.
``adversarial-review run``     — run reviewers over a change; print merged findings as JSON.

The review is advisory. ``run`` exits 0 whenever it completes, whatever each
reviewer's status; 2 means the invocation itself was wrong.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict

from .detect import detect, resolve_self

EXIT_OK = 0
EXIT_USAGE = 2


def _usage(message: str) -> int:
    print(f"adversarial-review: {message}", file=sys.stderr)
    return EXIT_USAGE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adversarial-review",
        description="Run other models' CLIs read-only over a change and merge their findings.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    det = sub.add_parser("detect", help="report installed reviewer CLIs and the running harness")
    det.add_argument(
        "--self", dest="self_name", help="override the detected harness (a backend name, or 'none')"
    )
    sub.add_parser("run", help="run reviewers over a change and print merged findings as JSON")
    return parser


def cmd_detect(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    try:
        me = resolve_self(args.self_name, env)
    except ValueError as exc:
        return _usage(str(exc))
    rows = [asdict(d) for d in detect(env, me)]
    print(json.dumps({"self": me, "backends": rows}, indent=2))
    return EXIT_OK


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    environ: Mapping[str, str] = os.environ if env is None else env
    if args.command == "detect":
        return cmd_detect(args, environ)
    return EXIT_OK
