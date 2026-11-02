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
"""``pii-list`` — print the local PII mapping for debugging.

Output goes to stdout (the user's terminal), not into any
LLM-bound surface. The command exists so the user can answer
"what mapped to what" without inspecting the JSON file by hand.
"""

from __future__ import annotations

import argparse
import json
import sys

from redactor.mapping import (
    MAPPING_VERSION,
    load_mapping,
    locate_mapping_path,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pii-list",
        description="Print the current PII mapping for debugging.",
    )
    parser.add_argument(
        "--mapping-path",
        default=None,
        help=(
            "Override the mapping file path. "
            "Default: $PII_MAPPING_PATH or ~/.config/apache-magpie/pii-mapping.json."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format. Default: text.",
    )
    args = parser.parse_args(argv)

    mapping_path = locate_mapping_path(args.mapping_path)
    try:
        mapping = load_mapping(mapping_path)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    if args.format == "json":
        payload = {
            "version": MAPPING_VERSION,
            "mapping_path": str(mapping_path),
            "entries": {
                ident: {"type": entry.type, "value": entry.value} for ident, entry in sorted(mapping.items())
            },
        }
        json.dump(payload, sys.stdout, indent=2, sort_keys=False)
        sys.stdout.write("\n")
        return 0

    if not mapping:
        print(f"(empty — {mapping_path} has no entries)")
        return 0

    # Text format: ident<TAB>type<TAB>value, sorted by identifier.
    for ident, entry in sorted(mapping.items()):
        print(f"{ident}\t{entry.type}\t{entry.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
