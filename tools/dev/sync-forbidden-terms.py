#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Sync and check the canonical forbidden-term list for public surface scrubbing.

Source of truth: `DEFAULT_TERMS` in `tools/vcs/src/magpie_vcs/publication.py`.
Output target: `plugins/magpie-security/hooks/forbidden-terms.ts`

Usage:
    python tools/dev/sync-forbidden-terms.py          # Write updated file
    python tools/dev/sync-forbidden-terms.py --check  # Fail if drifted
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VCS_SRC = REPO_ROOT / "tools" / "vcs" / "src"
TARGET_TS = REPO_ROOT / "plugins" / "magpie-security" / "hooks" / "forbidden-terms.ts"
# vetted-op-git's pull-request text check reads the same list (it runs outside
# the sandbox, where the guard does not see the files it publishes).
TARGET_PY = REPO_ROOT / "tools" / "vetted-ops" / "src" / "vetted_ops" / "forbidden_terms.py"

PY_HEADER = '''# Licensed to the Apache Software Foundation (ASF) under one
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
"""Terms never published before disclosure, matched case-insensitively.

Generated from tools/vcs/src/magpie_vcs/publication.py:DEFAULT_TERMS by
tools/dev/sync-forbidden-terms.py. Do not edit.
"""

DEFAULT_TERMS: tuple[tuple[str, str], ...] = (
'''

if str(VCS_SRC) not in sys.path:
    sys.path.insert(0, str(VCS_SRC))

try:
    from magpie_vcs.publication import DEFAULT_TERMS
except ImportError as err:
    sys.stderr.write(f"sync-forbidden-terms: failed to import magpie_vcs: {err}\n")
    sys.exit(1)

TS_HEADER = """// SPDX-License-Identifier: Apache-2.0
//
// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.

// Generated from tools/vcs/src/magpie_vcs/publication.py:DEFAULT_TERMS. Do not edit.

export interface CanonicalForbiddenTerm {
  name: string;
  pattern: string;
  flags: string;
}

export const CANONICAL_FORBIDDEN_TERMS: ReadonlyArray<CanonicalForbiddenTerm> = [
"""


def generate_terms_data() -> list[dict[str, str]]:
    """Convert DEFAULT_TERMS into canonical serializable objects."""
    terms: list[dict[str, str]] = []
    for label, pattern in DEFAULT_TERMS:
        terms.append(
            {
                "name": label,
                "pattern": pattern,
                "flags": "i",
            }
        )
    return terms


def generate_ts_content(terms: list[dict[str, str]]) -> str:
    lines = [TS_HEADER]
    for term in terms:
        name_esc = json.dumps(term["name"])
        pat_esc = json.dumps(term["pattern"])
        flags_esc = json.dumps(term["flags"])
        lines.append(f"  {{ name: {name_esc}, pattern: {pat_esc}, flags: {flags_esc} }},")
    lines.append("];\n")
    return "\n".join(lines)


def generate_py_content(terms: list[dict[str, str]]) -> str:
    lines = [PY_HEADER.rstrip("\n")]
    for term in terms:
        # Double-quoted, the pattern as a raw string: the form ruff format keeps.
        if '"' in term["pattern"] or term["pattern"].endswith("\\"):
            raise ValueError(f"pattern {term['name']!r} cannot be written as a raw string")
        lines.append(f'    ({json.dumps(term["name"])}, r"{term["pattern"]}"),')
    lines.append(")\n")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if forbidden-terms file matches DEFAULT_TERMS without writing.",
    )
    args = parser.parse_args()

    data = generate_terms_data()
    targets = {TARGET_TS: generate_ts_content(data), TARGET_PY: generate_py_content(data)}

    if args.check:
        for target, content in targets.items():
            if not target.exists():
                sys.stderr.write(
                    f"sync-forbidden-terms: {target.name} does not exist. "
                    "Run 'python tools/dev/sync-forbidden-terms.py' to generate.\n"
                )
                return 1
            if target.read_text(encoding="utf-8") != content:
                sys.stderr.write(
                    f"sync-forbidden-terms: {target.name} has drifted from DEFAULT_TERMS. "
                    "Run 'python tools/dev/sync-forbidden-terms.py' to synchronize.\n"
                )
                return 1
        return 0

    for target, content in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"Synchronized {len(data)} canonical forbidden terms to {target.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
