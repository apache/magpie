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
import os
from collections.abc import Mapping, Sequence

EXIT_OK = 0
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adversarial-review",
        description="Run other models' CLIs read-only over a change and merge their findings.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("detect", help="report installed reviewer CLIs and the running harness")
    sub.add_parser("run", help="run reviewers over a change and print merged findings as JSON")
    return parser


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    build_parser().parse_args(argv)
    _ = os.environ if env is None else env
    return EXIT_OK
