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
"""The dependency constraint ledger: intersect every mandatory path's range, then classify.

The agent gathers the ledger — every mandatory direct and transitive path to
the package, each with its specifier and environment markers, the versions
the metadata shows and whether that metadata covers the supported version
space exhaustively, and the versions it found lacking the API the change
uses. This module does the arithmetic and the classification the Step 4
rule prescribes:

* the effective intersection is empty in some supported environment → `broken`
  (uninstallable; no failing resolution needed);
* a version satisfies every path yet lacks the API → `broken`, with that
  resolution as the evidence;
* otherwise, exhaustive coverage → `compatible`; partial coverage → `unknown`.

Specifiers follow PEP 440's operators on dotted numeric versions
(`==`, `!=`, `>=`, `<=`, `>`, `<`, `~=`, `==X.*`); markers are compared as
literal environment names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_SPEC = re.compile(r"^\s*(==|!=|>=|<=|~=|>|<)\s*([0-9][0-9A-Za-z.*+-]*)\s*$")


def version(value: str) -> tuple[int, ...]:
    parts = []
    for piece in value.split("."):
        digits = re.match(r"\d+", piece)
        parts.append(int(digits.group(0)) if digits else 0)
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


@dataclass(frozen=True)
class Clause:
    op: str
    value: str

    def admits(self, candidate: str) -> bool:
        v = version(candidate)
        if self.value.endswith(".*"):
            prefix = version(self.value[:-2])
            hit = v[: len(prefix)] == prefix
            return hit if self.op == "==" else not hit
        target = version(self.value)
        if self.op == "==":
            return v == target
        if self.op == "!=":
            return v != target
        if self.op == ">=":
            return v >= target
        if self.op == "<=":
            return v <= target
        if self.op == ">":
            return v > target
        if self.op == "<":
            return v < target
        # ~=X.Y  ->  >=X.Y, ==X.*
        base = version(self.value)
        upper = base[:-1] if len(base) > 1 else base
        return v >= base and v[: len(upper)] == upper


def clauses(specifier: str) -> list[Clause]:
    found = []
    for part in (specifier or "").split(","):
        if not part.strip():
            continue
        match = _SPEC.match(part)
        if not match:
            raise ValueError(f"unsupported specifier clause {part.strip()!r}")
        found.append(Clause(match.group(1), match.group(2)))
    return found


def classify(ledger: dict[str, Any]) -> dict[str, Any]:
    """Classify one package's ledger.

    `ledger` keys: `package`, `paths` (each `{via, specifier, environments?}`),
    `environments` (the supported ones; default `["*"]`), `available_versions`,
    `exhaustive` (bool), `lacking_api` (versions without the API the change uses).
    """
    environments = ledger.get("environments") or ["*"]
    available = [str(v) for v in ledger.get("available_versions") or []]
    lacking = {str(v) for v in ledger.get("lacking_api") or []}
    per_env: dict[str, dict[str, Any]] = {}
    for env in environments:
        active = [
            p
            for p in ledger.get("paths") or []
            if not p.get("environments") or env in p["environments"] or "*" in p.get("environments", [])
        ]
        rules = [c for p in active for c in clauses(str(p.get("specifier") or ""))]
        satisfying = sorted((v for v in available if all(c.admits(v) for c in rules)), key=version)
        failing = [v for v in satisfying if v in lacking]
        per_env[env] = {"paths": [p.get("via") for p in active], "satisfying": satisfying, "failing": failing}
    empty = [env for env, r in per_env.items() if not r["satisfying"]]
    failing_by_env = {env: r["failing"] for env, r in per_env.items() if r["failing"]}
    evidence: dict[str, Any]
    if empty:
        status, evidence = "broken", {"uninstallable_in": empty}
    elif failing_by_env:
        status, evidence = "broken", {"failing_resolution": failing_by_env}
    elif ledger.get("exhaustive"):
        status, evidence = "compatible", {"exhaustive": True}
    else:
        status, evidence = "unknown", {"partial_coverage": True}
    return {
        "package": ledger.get("package"),
        "classification": status,
        "evidence": evidence,
        "environments": per_env,
        "runtime_finding_allowed": status == "broken",
        "note": "Apply the project's AGENTS.md / dependency policy for the remediation, whatever the classification.",
    }
