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

Specifiers follow PEP 440 and are evaluated with `packaging` (`==`, `!=`,
`>=`, `<=`, `>`, `<`, `~=`, `==X.*`, `!=X.*`); markers are compared as
literal environment names. Version ordering and matching are PEP 440's, so
pre-releases, post-releases and development releases compare and satisfy a
specifier the way `packaging` says they do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

_SPEC = re.compile(r"^\s*(==|!=|>=|<=|~=|>|<)\s*([0-9][0-9A-Za-z.*+_-]*)\s*$")


def version(value: str) -> Version:
    """The PEP 440 version, used to order candidates by full precedence."""
    return Version(value)


@dataclass(frozen=True)
class Clause:
    op: str
    value: str

    def admits(self, candidate: str) -> bool:
        return SpecifierSet(f"{self.op}{self.value}").contains(candidate)


def clauses(specifier: str) -> list[Clause]:
    found = []
    for part in (specifier or "").split(","):
        if not part.strip():
            continue
        match = _SPEC.match(part)
        if not match:
            raise ValueError(f"unsupported specifier clause {part.strip()!r}")
        op, value = match.group(1), match.group(2)
        try:
            SpecifierSet(f"{op}{value}")
        except InvalidSpecifier as exc:
            raise ValueError(f"unsupported specifier clause {part.strip()!r}") from exc
        found.append(Clause(op, value))
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
