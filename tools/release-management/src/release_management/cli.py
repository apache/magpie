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
"""`release-management <skill> <command>`.

Each skill family is a subpackage exposing `FAMILY`, `add_parsers(sub)` and
`dispatch(args) -> int`; adding one needs no edit here. Every command prints
JSON and executes nothing: the agent presents what it prints, and the release
manager runs the commands on their own machine.
"""

from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import sys
from collections.abc import Sequence
from types import ModuleType
from typing import Any

import release_management


def _families() -> list[ModuleType]:
    found: list[ModuleType] = []
    for info in pkgutil.iter_modules(release_management.__path__):
        if not info.ispkg:
            continue
        try:
            module = importlib.import_module(f"release_management.{info.name}.cli")
        except ModuleNotFoundError:
            continue
        if all(hasattr(module, name) for name in ("FAMILY", "add_parsers", "dispatch")):
            found.append(module)
    return sorted(found, key=lambda m: str(m.FAMILY))


def emit(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release-management", description=__doc__)
    sub = parser.add_subparsers(dest="family", required=True)
    families = {str(m.FAMILY): m for m in _families()}
    for module in families.values():
        module.add_parsers(sub)
    args = parser.parse_args(argv)
    return int(families[args.family].dispatch(args))


if __name__ == "__main__":
    sys.exit(main())
