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

from __future__ import annotations

import json

import pytest

import vendor_neutrality_score as vns

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool(name: str, contract: str, kind: str, vendor: str) -> vns.ToolMeta:
    return vns.ToolMeta(name=name, contracts=(contract,), kind=kind, vendor=vendor)


def _result(results: list[vns.ContractResult], contract: str) -> vns.ContractResult:
    return next(r for r in results if r.contract == contract)


# ---------------------------------------------------------------------------
# Per-contract scoring
# ---------------------------------------------------------------------------


def test_vendor_backed_needs_two_distinct_vendors() -> None:
    tools = [
        _tool("github", "contract:tracker", vns.IMPLEMENTATION, "GitHub"),
        _tool("jira", "contract:tracker", vns.IMPLEMENTATION, "Atlassian"),
    ]
    r = _result(vns.score_contracts(tools), "contract:tracker")
    assert r.green is True
    assert r.vendors == ["Atlassian", "GitHub"]


def test_vendor_backed_single_vendor_is_not_green() -> None:
    tools = [_tool("gmail", "contract:mail-draft", vns.IMPLEMENTATION, "Google")]
    r = _result(vns.score_contracts(tools), "contract:mail-draft")
    assert r.green is False
    assert "needs 1 more" in r.basis


def test_same_vendor_twice_counts_once() -> None:
    tools = [
        _tool("github", "contract:tracker", vns.IMPLEMENTATION, "GitHub"),
        _tool("github-rollup", "contract:tracker", vns.IMPLEMENTATION, "GitHub"),
    ]
    r = _result(vns.score_contracts(tools), "contract:tracker")
    assert r.green is False
    assert r.vendors == ["GitHub"]


def test_interface_tools_do_not_count_as_a_backend() -> None:
    tools = [
        _tool("cve-tool", "contract:cve-authority", vns.INTERFACE, "agnostic"),
        _tool("cve-org", "contract:cve-authority", vns.IMPLEMENTATION, "CVE.org"),
    ]
    r = _result(vns.score_contracts(tools), "contract:cve-authority")
    assert r.green is False  # one interface + one impl = one backend vendor
    assert r.interfaces == ["cve-tool"]
    assert r.vendors == ["CVE.org"]


def test_agnostic_contract_is_green_with_only_an_interface() -> None:
    tools = [_tool("scan-format", "contract:scan-format", vns.INTERFACE, "agnostic")]
    r = _result(vns.score_contracts(tools), "contract:scan-format")
    assert r.green is True
    assert "construction" in r.basis


def test_single_org_contract_is_green_by_exemption() -> None:
    tools = [_tool("apache-projects", "contract:project-metadata", vns.IMPLEMENTATION, "ASF")]
    r = _result(vns.score_contracts(tools), "contract:project-metadata")
    assert r.green is True
    assert "ASF" in r.basis


def test_unknown_contract_raises() -> None:
    tools = [_tool("mystery", "contract:does-not-exist", vns.IMPLEMENTATION, "X")]
    with pytest.raises(ValueError, match="does-not-exist"):
        vns.score_contracts(tools)


def test_all_policy_contracts_are_reported() -> None:
    results = vns.score_contracts([])
    assert {r.contract for r in results} == set(vns.CONTRACT_POLICY)


# ---------------------------------------------------------------------------
# Per-skill assessment
# ---------------------------------------------------------------------------


def _contract_results_with_gap() -> list[vns.ContractResult]:
    tools = [
        _tool("github", "contract:tracker", vns.IMPLEMENTATION, "GitHub"),
        _tool("jira", "contract:tracker", vns.IMPLEMENTATION, "Atlassian"),
        _tool("gmail", "contract:mail-draft", vns.IMPLEMENTATION, "Google"),
    ]
    return vns.score_contracts(tools)


def test_skill_capability_pure_when_no_backend_named() -> None:
    skills = [("greeter", "agnostic", "This skill just talks to the user. No tools.")]
    (s,) = vns.score_skills(skills, _contract_results_with_gap())
    assert s.verdict == "capability-pure"
    assert s.contracts == []


def test_skill_portable_when_named_contract_is_green() -> None:
    skills = [("triage", "agnostic", "Run `gh issue list` then classify each issue.")]
    (s,) = vns.score_skills(skills, _contract_results_with_gap())
    assert s.verdict == "portable"
    assert s.contracts == ["contract:tracker"]
    assert s.coupled == []


def test_skill_vendor_coupled_on_github_only_change_request() -> None:
    # Driving pull requests (`gh pr`) is the change-request contract, which only
    # GitHub implements — so a skill that runs it is coupled to GitHub even
    # though the issue side of tracker is portable.
    tools = [
        _tool("github", "contract:change-request", vns.IMPLEMENTATION, "GitHub"),
    ]
    contracts = vns.score_contracts(tools)
    skills = [("merge", "agnostic", "Run `gh pr merge --squash` after review.")]
    (s,) = vns.score_skills(skills, contracts)
    assert s.verdict == "vendor-coupled"
    assert s.coupled == [("GitHub", "contract:change-request")]


def test_skill_vendor_coupled_on_sole_backend_contract() -> None:
    skills = [("reply", "ASF", "Draft a courtesy reply with mcp__claude_ai_Gmail__create_draft.")]
    (s,) = vns.score_skills(skills, _contract_results_with_gap())
    assert s.verdict == "vendor-coupled"
    assert s.coupled == [("Google", "contract:mail-draft")]


def test_prose_mention_is_not_usage() -> None:
    skills = [("docs", "agnostic", "Skills that read Gmail or GitHub archives are fine.")]
    (s,) = vns.score_skills(skills, _contract_results_with_gap())
    assert s.verdict == "capability-pure"


# ---------------------------------------------------------------------------
# Rendering + CLI + integration
# ---------------------------------------------------------------------------


def test_json_render_is_valid_and_complete() -> None:
    contracts = _contract_results_with_gap()
    skills = vns.score_skills([("t", "agnostic", "gh pr view")], contracts)
    payload = json.loads(vns.render_json(contracts, skills))
    assert payload["overall"]["total"] == len(vns.CONTRACT_POLICY)
    assert any(c["contract"] == "contract:mail-draft" and c["green"] is False for c in payload["contracts"])


def test_markdown_render_contains_score_and_table() -> None:
    contracts = _contract_results_with_gap()
    md = vns.render_markdown(contracts, [])
    assert "Overall vendor-neutrality score" in md
    assert "| `contract:tracker` |" in md


def test_compute_runs_against_the_live_repo() -> None:
    root = vns.find_repo_root()
    contract_results, skill_results = vns.compute(root)
    assert len(contract_results) == len(vns.CONTRACT_POLICY)
    assert len(skill_results) > 0
    # Every live contract carries a basis string.
    assert all(r.basis for r in contract_results)


def test_doc_block_is_in_sync() -> None:
    """The generated block in docs/vendor-neutrality.md must match the tool output."""
    root = vns.find_repo_root()
    doc = (root / "docs" / "vendor-neutrality.md").read_text(encoding="utf-8")
    begin = "<!-- BEGIN vendor-neutrality-score"
    end = "<!-- END vendor-neutrality-score -->"
    assert begin in doc and end in doc, "regen markers missing from docs/vendor-neutrality.md"
    block = doc.split(begin, 1)[1].split("-->", 1)[1].split(end, 1)[0].strip()
    contract_results, skill_results = vns.compute(root)
    expected = vns.render_markdown(contract_results, skill_results).strip()
    assert block == expected, (
        "docs/vendor-neutrality.md is stale — regenerate with:\n"
        "  uv run --project tools/vendor-neutrality-score vendor-neutrality-score --markdown"
    )


def test_main_json_exits_zero() -> None:
    assert vns.main(["--json"]) == 0


def test_fail_under_gate() -> None:
    # Far above any achievable score → non-zero exit.
    assert vns.main(["--fail-under", "101"]) == 1
