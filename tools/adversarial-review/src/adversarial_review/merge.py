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
Merge the same problem reported by several reviewers into one finding.

Two findings match when they are in the same file, their lines are within
LINE_WINDOW of each other (or both are unknown), and their claims are similar
(difflib ratio ≥ CLAIM_SIMILARITY on normalised text). Each merged finding
keeps every reviewer's report and takes the most severe one's claim.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .findings import SEVERITIES, Finding

LINE_WINDOW = 3
CLAIM_SIMILARITY = 0.6
RANK = {severity: i for i, severity in enumerate(SEVERITIES)}


@dataclass
class MergedFinding:
    severity: str
    file: str
    line: int | None
    claim: str
    reports: list[Finding] = field(default_factory=list)

    @property
    def reviewers(self) -> list[str]:
        return list(dict.fromkeys(r.reviewer for r in self.reports))

    def as_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "claim": self.claim,
            "reviewers": self.reviewers,
            "reports": [
                {"reviewer": r.reviewer, "severity": r.severity, "claim": r.claim, "evidence": r.evidence}
                for r in self.reports
            ],
        }


def _norm(claim: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", claim.lower()).strip()


def _lines_close(a: int | None, b: int | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= LINE_WINDOW


def _similar(a: Finding, b: Finding) -> bool:
    return (
        a.file == b.file
        and _lines_close(a.line, b.line)
        and SequenceMatcher(None, _norm(a.claim), _norm(b.claim)).ratio() >= CLAIM_SIMILARITY
    )


def merge(findings: Iterable[Finding]) -> list[MergedFinding]:
    groups: list[MergedFinding] = []
    for finding in findings:
        for group in groups:
            if any(_similar(report, finding) for report in group.reports):
                group.reports.append(finding)
                if RANK[finding.severity] < RANK[group.severity]:
                    group.severity, group.claim = finding.severity, finding.claim
                break
        else:
            groups.append(
                MergedFinding(finding.severity, finding.file, finding.line, finding.claim, [finding])
            )
    return sorted(groups, key=lambda g: (RANK[g.severity], g.file, -1 if g.line is None else g.line))
