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
"""Audit logic for Claude Code `permissions.allow[]` entries.

Pure data + classification — no I/O. The CLI layer in `cli.py`
drives reads/writes; this module just answers "given the allow
list and the opted-in families, what should be removed and what
should be added?".

Two canonical lists:

- `FORBIDDEN_PATTERNS` — broad wildcards that grant arbitrary code
  execution. Any match → ✗ removal proposal. The list is
  **deliberately not exhaustive** (see the *"same category"* rule
  in the verify check 8d doc) — these are the concrete patterns we
  have observed accumulating in real adopter trees.
- `RECOMMENDED_BY_FAMILY` — narrow read-only patterns the framework
  invokes constantly. Family-scoped: an adopter who skipped a
  family does not see its recommendations flagged as gaps.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

FORBIDDEN_PATTERNS: frozenset[str] = frozenset(
    {
        # Interpreters
        "Bash(python *)",
        "Bash(python3 *)",
        "Bash(node *)",
        "Bash(bun *)",
        "Bash(deno *)",
        "Bash(ruby *)",
        "Bash(perl *)",
        "Bash(php *)",
        "Bash(lua *)",
        # Shells
        "Bash(bash *)",
        "Bash(sh *)",
        "Bash(zsh *)",
        "Bash(fish *)",
        "Bash(eval *)",
        "Bash(exec *)",
        "Bash(ssh *)",
        # Package runners
        "Bash(npx *)",
        "Bash(bunx *)",
        "Bash(uvx *)",
        "Bash(uv run *)",
        # Task-runner wildcards
        "Bash(npm run *)",
        "Bash(yarn run *)",
        "Bash(pnpm run *)",
        "Bash(bun run *)",
        "Bash(make *)",
        "Bash(just *)",
        "Bash(cargo run *)",
        "Bash(go run *)",
        # Broad API / container / privilege wildcards
        "Bash(gh api *)",
        "Bash(docker run *)",
        "Bash(docker exec *)",
        "Bash(kubectl exec *)",
        "Bash(sudo *)",
    }
)

# Family name → patterns the framework's skills in that family
# invoke often. Keep narrow — every entry MUST be read-only and
# scoped to a specific tool.
#
# Empty-string key "" means "applies to every adopter regardless
# of family choice" (e.g. lychee — the framework itself ships
# docs, so every adopter ends up running it).
RECOMMENDED_BY_FAMILY: dict[str, frozenset[str]] = {
    "": frozenset(
        {
            "Bash(lychee *)",
        }
    ),
    "security": frozenset(
        {
            "mcp__claude_ai_Gmail__get_thread",
            "mcp__claude_ai_Gmail__search_threads",
            "mcp__claude_ai_Gmail__list_drafts",
            "mcp__claude_ai_Gmail__list_labels",
        }
    ),
}

# Organization → family → patterns recommended only to that organization's
# projects: the ASF's PonyMail archive, its project directory and its CVE
# tool mean nothing to a project outside the ASF, so recommending them
# there would only widen the allow-list.
RECOMMENDED_BY_ORGANIZATION: dict[str, dict[str, frozenset[str]]] = {
    "ASF": {
        "security": frozenset(
            {
                "mcp__ponymail__search_list",
                "mcp__ponymail__auth_status",
                "mcp__ponymail__get_thread",
                "mcp__ponymail__get_email",
                "mcp__ponymail__list_restrictions",
                "mcp__apache-projects__project_stats",
                "mcp__apache-projects__get_committee",
                "mcp__apache-projects__get_group_members",
                "mcp__apache-projects__get_person",
                "mcp__apache-projects__search_people",
                "Bash(vulnogram-api-record-fetch *)",
            }
        ),
    },
}


@dataclass(frozen=True)
class AuditFinding:
    """A single audit finding.

    `severity` is one of:
      - `"forbidden"` — the entry grants arbitrary code execution
        and should be removed (✗).
      - `"missing-recommended"` — a narrow read-only recommended
        entry is absent (⚠).
    """

    severity: str
    pattern: str
    json_pointer: str | None  # `.permissions.allow[<index>]` for forbidden; None for missing.
    family: str | None  # which family's recommended list this came from; None for forbidden.


@dataclass
class AuditResult:
    forbidden: list[AuditFinding] = field(default_factory=list)
    missing_recommended: list[AuditFinding] = field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(self.forbidden or self.missing_recommended)


def audit_settings(
    allow_list: Iterable[str], families: Iterable[str], organization: str | None = None
) -> AuditResult:
    """Classify allow-list entries against forbidden + recommended lists.

    Args:
        allow_list: the contents of `permissions.allow[]` from the
            settings file, in declaration order.
        families: the opt-in family names the adopter has selected
            (e.g. `["security"]`). The empty-family bucket ("")
            is always included regardless.
        organization: the project's `organization` (`project.md`);
            only that organization's own recommendations are added,
            so the ASF-only ones appear for `ASF` alone.

    Returns:
        `AuditResult` with two buckets — entries to remove
        (forbidden) and entries to consider adding (missing
        recommended).
    """
    result = AuditResult()
    allow_set = set(allow_list)

    # Forbidden — record JSON-pointer index for each hit so the
    # operator can locate the entry in the file instantly. We walk
    # the list in declaration order (rather than the set above) so
    # duplicate entries get separate pointers.
    for idx, entry in enumerate(allow_list):
        if entry in FORBIDDEN_PATTERNS:
            result.forbidden.append(
                AuditFinding(
                    severity="forbidden",
                    pattern=entry,
                    json_pointer=f".permissions.allow[{idx}]",
                    family=None,
                )
            )

    # Recommended — always include the empty-family bucket.
    effective_families = {""} | set(families)
    by_org = RECOMMENDED_BY_ORGANIZATION.get(organization or "", {})
    for family in sorted(effective_families):
        recommended = RECOMMENDED_BY_FAMILY.get(family, frozenset()) | by_org.get(family, frozenset())
        for pattern in sorted(recommended):
            if pattern not in allow_set:
                result.missing_recommended.append(
                    AuditFinding(
                        severity="missing-recommended",
                        pattern=pattern,
                        json_pointer=None,
                        family=family or None,
                    )
                )

    return result
