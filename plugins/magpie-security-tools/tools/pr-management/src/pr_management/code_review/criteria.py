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
"""`<project-config>/pr-management-code-review-criteria.md`: which sources a PR is reviewed against.

The rules themselves stay in those source files — the agent reads and quotes
them. This only resolves *which* files apply to a PR, the section anchor each
finding category links to, and whether the base is a backport branch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import mdconfig

CATEGORIES = (
    "Architecture boundaries",
    "Database / query correctness",
    "Code quality",
    "Third-party license compliance",
    "License headers",
    "Testing",
    "API correctness",
    "UI (React/TypeScript)",
    "Generated files",
    "AI-generated code signals",
    "Quality signals to check",
    "Commits and PRs (newsfragments, commit messages, tracking issues)",
    "Security model",
)


@dataclass
class Criteria:
    repo_wide: list[str] = field(default_factory=list)
    per_area: list[tuple[str, str]] = field(default_factory=list)  # (file, subtree)
    security_model: str | None = None
    backport_pattern: str | None = None
    anchors: dict[str, str] = field(default_factory=dict)
    source: str | None = None

    def applies(self, paths: list[str]) -> list[str]:
        """Repo-wide files, plus per-area files whose subtree a path is under."""
        found = list(self.repo_wide)
        for file, subtree in self.per_area:
            if (
                any(p == subtree or p.startswith(subtree.rstrip("/") + "/") for p in paths)
                and file not in found
            ):
                found.append(file)
        return found

    def is_backport(self, base: str) -> bool:
        return bool(self.backport_pattern and re.fullmatch(self.backport_pattern, base))


def _real(value: str | None) -> bool:
    return bool(value) and "<" not in (value or "") and "TODO" not in (value or "")


def load(project_root: Path, config_dir: Path | None) -> Criteria:
    resolver = mdconfig.Resolver(project_root, config_dir)
    name = "pr-management-code-review-criteria.md"
    text = resolver.read(name)
    found = Criteria(source=str(resolver.find(name)) if resolver.find(name) else None)
    if text is None:
        return found
    repo = mdconfig.section(text, "Repo-wide source files")
    for cells in mdconfig.table_rows(repo):
        value = mdconfig.first_token(cells[0]) if cells else None
        if value and _real(value) and value.lower() != "file":
            found.repo_wide.append(value)
    area = mdconfig.section(text, "Per-area source files")
    for cells in mdconfig.table_rows(area):
        value = mdconfig.first_token(cells[0]) if cells else None
        if not value or not _real(value) or value.lower() == "file" or len(cells) < 2:
            continue
        subtree = re.search(r"`([^`]+)`", cells[1])
        found.per_area.append((value, (subtree.group(1) if subtree else value.rsplit("/", 1)[0]).strip("/")))
    security = mdconfig.section(text, "Security-model calibration")
    for cells in mdconfig.table_rows(security):
        value = mdconfig.first_token(cells[0]) if cells else None
        if value and _real(value) and value.lower() != "file":
            found.security_model = value
            break
    backports = mdconfig.section(text, "Backports")
    for cells in mdconfig.table_rows(backports):
        if len(cells) >= 2 and cells[0].lower().startswith("backport branch pattern"):
            value = mdconfig.first_token(cells[1])
            if _real(value):
                found.backport_pattern = value
    anchors = mdconfig.section(text, "Section anchors")
    for cells in mdconfig.table_rows(anchors):
        if len(cells) >= 2 and cells[0] != "Section":
            url = mdconfig.first_token(cells[1])
            if _real(url) and url is not None:
                found.anchors[cells[0]] = url
    return found
