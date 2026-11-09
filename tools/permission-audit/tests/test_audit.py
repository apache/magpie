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
import json
from pathlib import Path

from permission_audit.audit import (
    RECOMMENDED_BY_FAMILY,
    RECOMMENDED_BY_ORGANIZATION,
    audit_settings,
)


def test_empty_allow_only_misses_recommended():
    result = audit_settings(allow_list=[], families=["security"])
    assert result.forbidden == []
    expected = {
        "Bash(lychee *)",
        "mcp__claude_ai_Gmail__get_thread",
        "mcp__claude_ai_Gmail__get_message",
        "mcp__claude_ai_Gmail__list_drafts",
        "mcp__claude_ai_Gmail__get_draft",
        "mcp__gmail-plaintext__check_auth",
    }
    assert {f.pattern for f in result.missing_recommended} == expected


def test_release_management_family_recommendations():
    result = audit_settings(allow_list=[], families=["release-management"])
    assert result.forbidden == []
    expected_generic = {
        "Bash(lychee *)",
        "mcp__gmail-plaintext__check_auth",
    }
    assert {f.pattern for f in result.missing_recommended} == expected_generic

    result_asf = audit_settings(allow_list=[], families=["release-management"], organization="ASF")
    expected_asf = expected_generic | {
        "mcp__ponymail__auth_status",
        "mcp__ponymail__get_thread",
        "mcp__ponymail__get_email",
        "mcp__ponymail__get_source",
        "mcp__ponymail__list_lists",
        "mcp__ponymail__list_restrictions",
    }
    assert {f.pattern for f in result_asf.missing_recommended} == expected_asf


def test_forbidden_python_wildcard_flagged_with_pointer():
    allow = [
        "Bash(git status *)",
        "Bash(python3 *)",  # forbidden
        "Bash(uv run *)",  # forbidden
        "mcp__claude_ai_Gmail__get_thread",
    ]
    result = audit_settings(allow_list=allow, families=["security"])
    forbidden_pointers = {f.pattern: f.json_pointer for f in result.forbidden}
    assert forbidden_pointers == {
        "Bash(python3 *)": ".permissions.allow[1]",
        "Bash(uv run *)": ".permissions.allow[2]",
    }


def test_family_scoping_excludes_other_families():
    # Adopter only opted into the default "" family — security MCPs
    # must not appear as gaps.
    result = audit_settings(allow_list=[], families=[])
    patterns = {f.pattern for f in result.missing_recommended}
    assert "Bash(lychee *)" in patterns
    # No security-family entries surfaced.
    assert "mcp__claude_ai_Gmail__get_thread" not in patterns


def test_recommended_present_is_not_flagged_missing():
    allow = ["Bash(lychee *)", "mcp__claude_ai_Gmail__get_thread"]
    result = audit_settings(allow_list=allow, families=["security"])
    missing = {f.pattern for f in result.missing_recommended}
    assert "Bash(lychee *)" not in missing
    assert "mcp__claude_ai_Gmail__get_thread" not in missing


def test_duplicate_forbidden_entries_get_distinct_pointers():
    allow = ["Bash(uv run *)", "Bash(uv run *)"]
    result = audit_settings(allow_list=allow, families=[])
    pointers = [f.json_pointer for f in result.forbidden]
    assert pointers == [".permissions.allow[0]", ".permissions.allow[1]"]


def test_default_family_always_included_even_when_not_requested():
    result = audit_settings(allow_list=[], families=["security"])
    patterns = {f.pattern for f in result.missing_recommended}
    assert "Bash(lychee *)" in patterns


def test_asf_only_recommendations_need_the_asf_organization():
    """PonyMail and Vulnogram are ASF services."""
    asf_only = {
        "mcp__ponymail__auth_status",
        "mcp__ponymail__get_thread",
        "mcp__ponymail__get_email",
        "mcp__ponymail__get_source",
        "mcp__ponymail__list_lists",
        "mcp__ponymail__list_restrictions",
        "Bash(vulnogram-api-record-fetch *)",
    }
    elsewhere = {f.pattern for f in audit_settings([], ["security"]).missing_recommended}
    independent = {f.pattern for f in audit_settings([], ["security"], "independent").missing_recommended}
    asf = {f.pattern for f in audit_settings([], ["security"], "ASF").missing_recommended}
    assert not asf_only & elsewhere
    assert not asf_only & independent
    assert asf_only <= asf
    expected_generic = {
        "Bash(lychee *)",
        "mcp__claude_ai_Gmail__get_thread",
        "mcp__claude_ai_Gmail__get_message",
        "mcp__claude_ai_Gmail__list_drafts",
        "mcp__claude_ai_Gmail__get_draft",
        "mcp__gmail-plaintext__check_auth",
    }
    assert elsewhere == expected_generic
    assert independent == expected_generic
    assert asf == expected_generic | asf_only


def _find_family_mcp_allows() -> Path:
    current = Path(__file__).resolve().parent
    for p in [current, *current.parents]:
        target = p / "plugins" / "magpie-setup" / "skills" / "setup" / "family-mcp-allows.json"
        if target.exists():
            return target
    raise FileNotFoundError("Could not locate family-mcp-allows.json")


def test_audit_recommendations_match_family_mcp_allows_json():
    """Ensure every MCP pattern in audit.py is backed by family-mcp-allows.json.

    Validates per-family scoping and exact bidirectional parity between
    the canonical family-mcp-allows registry and permission-audit recommendation dictionaries.
    """
    path = _find_family_mcp_allows()
    registry = json.loads(path.read_text(encoding="utf-8"))

    # Map family -> set of allowed MCP patterns
    allowed_by_family: dict[str, set[str]] = {}
    for server, entry in registry.get("servers", {}).items():
        server_tools = {f"mcp__{server}__{t}" for t in entry.get("tools", [])}
        for fam in entry.get("families", []):
            allowed_by_family.setdefault(fam, set()).update(server_tools)

    # 1. Per-family check: every MCP pattern in RECOMMENDED_BY_FAMILY must be registered for that family
    for family, rec_patterns in RECOMMENDED_BY_FAMILY.items():
        if not family:
            continue
        mcp_patterns = {p for p in rec_patterns if p.startswith("mcp__")}
        fam_allowed = allowed_by_family.get(family, set())
        assert mcp_patterns <= fam_allowed, (
            f"Family '{family}' has MCP recommendations not registered for that family in family-mcp-allows.json: "
            f"{mcp_patterns - fam_allowed}"
        )

    # 2. Per-family check: every MCP pattern in RECOMMENDED_BY_ORGANIZATION must be registered for that family
    for org, fam_map in RECOMMENDED_BY_ORGANIZATION.items():
        for family, org_patterns in fam_map.items():
            mcp_patterns = {p for p in org_patterns if p.startswith("mcp__")}
            fam_allowed = allowed_by_family.get(family, set())
            assert mcp_patterns <= fam_allowed, (
                f"Org '{org}' family '{family}' has MCP recommendations not registered for that family: "
                f"{mcp_patterns - fam_allowed}"
            )

    # 3. Exact bidirectional parity check for both release-management and security
    for fam in ("release-management", "security"):
        actual = {
            p
            for p in (
                RECOMMENDED_BY_FAMILY.get(fam, frozenset())
                | RECOMMENDED_BY_ORGANIZATION.get("ASF", {}).get(fam, frozenset())
            )
            if p.startswith("mcp__")
        }
        assert actual == allowed_by_family[fam], (
            f"Family '{fam}' recommendations in audit.py do not exactly match family-mcp-allows.json: "
            f"missing={allowed_by_family[fam] - actual}, extra={actual - allowed_by_family[fam]}"
        )
