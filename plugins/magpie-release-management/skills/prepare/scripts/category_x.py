#!/usr/bin/env python3
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
"""Scan manifest and lock files for Category-X dependency identifiers.

Usage::

    category_x.py --deny <identifier> [--deny ...] <file> [<file> ...]

Each ``<file>`` is a local copy of a ``version_manifest_files`` entry or a
configured dependency-lock file; pass it as ``<repo-path>=<local-copy>`` to
report the repository path. An identifier matches as a whole token,
case-insensitively, treating ``-``, ``_`` and ``.`` as equivalent (package
names are normalised that way). A Maven-style ``group:artifact`` identifier
also matches its bare ``artifact`` part, since Python and other manifests
name only the artifact.

Prints the Step 2b hard-stop JSON when anything matches, otherwise
``{"category_x_hit": false, ...}``. Exit 0 on success, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HANDOFF = "Category-X dependency found. Remove before preparing the release."
SEPARATORS = r"[-_.]"
TOKEN_CHARS = r"A-Za-z0-9_.\-"


def pattern_for(term: str) -> re.Pattern[str]:
    pieces = re.split(SEPARATORS, term)
    body = SEPARATORS.join(re.escape(p) for p in pieces)
    return re.compile(rf"(?<![{TOKEN_CHARS}:/]){body}(?![A-Za-z0-9_\-:]|\.[A-Za-z0-9])", re.IGNORECASE)


def terms(identifier: str) -> list[str]:
    found = [identifier]
    if ":" in identifier:
        artifact = identifier.split(":")[1]
        if artifact and artifact not in found:
            found.append(artifact)
    return found


def scan(deny: list[str], files: list[tuple[str, str]]) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    lines_hit: list[dict[str, Any]] = []
    for identifier in deny:
        patterns = [pattern_for(t) for t in terms(identifier)]
        for shown, local in files:
            lines = Path(local).read_text(encoding="utf-8", errors="replace").splitlines()
            for number, line in enumerate(lines, start=1):
                if any(p.search(line) for p in patterns):
                    violations.append({"identifier": identifier, "found_in": shown})
                    lines_hit.append({"identifier": identifier, "found_in": shown, "line": number})
                    break
    if violations:
        return {
            "category_x_hit": True,
            "category_x_violations": violations,
            "handoff_reason": HANDOFF,
            "first_match_lines": lines_hit,
        }
    return {"category_x_hit": False, "category_x_violations": [], "files_scanned": [s for s, _ in files]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--deny", action="append", default=[], help="a category_x_dependencies identifier")
    parser.add_argument("files", nargs="+", help="<repo-path>=<local-copy> or a local path")
    args = parser.parse_args(argv)
    deny = [d.strip() for d in args.deny if d.strip()]
    files = [tuple(f.split("=", 1)) if "=" in f else (f, f) for f in args.files]
    try:
        if not deny:
            out: dict[str, Any] = {"category_x_hit": False, "category_x_violations": [], "files_scanned": []}
        else:
            out = scan(deny, files)  # type: ignore[arg-type]
    except OSError as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
