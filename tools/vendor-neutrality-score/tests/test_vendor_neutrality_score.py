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
from pathlib import Path

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
    tools = [_tool("gmail", "contract:mail-create", vns.IMPLEMENTATION, "Google")]
    r = _result(vns.score_contracts(tools), "contract:mail-create")
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
        _tool("gmail", "contract:mail-create", vns.IMPLEMENTATION, "Google"),
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


def test_change_request_green_with_three_backends() -> None:
    # #669: GitHub PR + JIRA-patch (Atlassian) + [PATCH]-mail (email) give the
    # change-request contract three distinct backend vendors, so it flips to
    # vendor neutral and a skill driving `gh pr` becomes portable — no longer
    # coupled the way test_skill_vendor_coupled_on_github_only_change_request
    # showed it was with GitHub as the sole backend.
    tools = [
        _tool("github", "contract:change-request", vns.IMPLEMENTATION, "GitHub"),
        _tool("jira-patch", "contract:change-request", vns.IMPLEMENTATION, "Atlassian"),
        _tool("mail-patch", "contract:change-request", vns.IMPLEMENTATION, "email"),
    ]
    contracts = vns.score_contracts(tools)
    r = _result(contracts, "contract:change-request")
    assert r.green is True
    assert r.vendors == ["Atlassian", "GitHub", "email"]
    skills = [("merge", "agnostic", "Run `gh pr merge --squash` after review.")]
    (s,) = vns.score_skills(skills, contracts)
    assert s.verdict == "portable"
    assert s.coupled == []


def test_skill_vendor_coupled_on_sole_backend_contract() -> None:
    skills = [("reply", "ASF", "Draft a courtesy reply with mcp__claude_ai_Gmail__create_draft.")]
    (s,) = vns.score_skills(skills, _contract_results_with_gap())
    assert s.verdict == "vendor-coupled"
    assert s.coupled == [("Google", "contract:mail-create")]


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
    assert any(c["contract"] == "contract:mail-create" and c["green"] is False for c in payload["contracts"])


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
    contract_results, skill_results, harness_results, llm_classes = vns.compute_all(root)
    expected = vns.render_markdown(contract_results, skill_results, harness_results, llm_classes).strip()
    assert block == expected, (
        "docs/vendor-neutrality.md is stale — regenerate with:\n"
        "  uv run --project tools/vendor-neutrality-score vendor-neutrality-score --markdown"
    )


# ---------------------------------------------------------------------------
# Agent-harness axis (Part A) + LLM-endpoint axis (Part B)
# ---------------------------------------------------------------------------


def _write_substrate(root, name: str, capability: str, harness: str) -> None:
    d = root / "tools" / name
    d.mkdir(parents=True)
    (d / "README.md").write_text(
        f"# {name}\n\n**Capability:** {capability}\n\n**Harness:** {harness}\n\nProse.\n",
        encoding="utf-8",
    )


def test_harness_verdicts(tmp_path) -> None:
    _write_substrate(tmp_path, "guard", "substrate:action-guard", "Claude Code")
    _write_substrate(tmp_path, "multi", "substrate:sandbox", "Claude Code, Codex")
    _write_substrate(tmp_path, "checker", "substrate:framework-dev", "agnostic")
    by_tool = {r.tool: r for r in vns.load_substrate_harnesses(tmp_path)}
    assert by_tool["guard"].verdict == "coupled"  # single harness
    assert by_tool["multi"].verdict == "portable"  # two harnesses
    assert by_tool["checker"].verdict == "agnostic"  # no harness dependency
    assert by_tool["multi"].harnesses == ("Claude Code", "Codex")


def test_harness_missing_field_raises(tmp_path) -> None:
    d = tmp_path / "tools" / "nope"
    d.mkdir(parents=True)
    (d / "README.md").write_text("# nope\n\n**Capability:** substrate:sandbox\n\nProse.\n", "utf-8")
    with pytest.raises(ValueError, match="Harness"):
        vns.load_substrate_harnesses(tmp_path)


def test_harness_unknown_value_raises(tmp_path) -> None:
    _write_substrate(tmp_path, "weird", "substrate:sandbox", "Emacs")
    with pytest.raises(ValueError, match="unknown harness"):
        vns.load_substrate_harnesses(tmp_path)


def test_contract_tools_are_not_scored_for_harness(tmp_path) -> None:
    # A tool that carries a contract:* is on the vendor axis, not the harness axis.
    d = tmp_path / "tools" / "gh"
    d.mkdir(parents=True)
    (d / "README.md").write_text(
        "# gh\n\n**Capability:** contract:tracker + substrate:analytics\n\nProse.\n", "utf-8"
    )
    assert vns.load_substrate_harnesses(tmp_path) == []


def test_harness_appears_in_renders(tmp_path) -> None:
    _write_substrate(tmp_path, "guard", "substrate:action-guard", "Claude Code")
    harness = vns.load_substrate_harnesses(tmp_path)
    md = vns.render_markdown([], [], harness, [])
    assert "Agent harness:" in md and "`guard`" in md and "coupled" in md
    payload = json.loads(vns.render_json([], [], harness, []))
    assert payload["harness"]["overall"]["total"] == 1
    assert payload["harness"]["matrix"]["Claude Code"] == ["guard"]


def test_approved_llms_parsed_from_live_registry() -> None:
    classes = vns.load_approved_llms(vns.find_repo_root())
    names = [c.name for c in classes]
    assert "Claude Code itself" in names
    assert any("apache.org" in n for n in names)
    assert all(c.examples for c in classes)


def test_compute_all_covers_every_axis() -> None:
    contracts, skills, harness, llm = vns.compute_all(vns.find_repo_root())
    assert contracts and skills and harness and llm
    assert all(r.verdict in {"agnostic", "portable", "coupled"} for r in harness)


def test_main_json_exits_zero() -> None:
    assert vns.main(["--json"]) == 0


def test_fail_under_gate() -> None:
    # Far above any achievable score → non-zero exit.
    assert vns.main(["--fail-under", "101"]) == 1


# ---------------------------------------------------------------------------
# In-place doc regeneration (the pre-commit hook)
# ---------------------------------------------------------------------------


def _mirror_repo(root: Path, live: Path) -> None:
    """Build a repo_root whose inputs symlink the live tree but whose
    docs/vendor-neutrality.md is a real, mutable copy."""
    (root / "tools").symlink_to(live / "tools")
    (root / "skills").symlink_to(live / "skills")
    docs = root / "docs"
    docs.mkdir()
    (docs / "labels-and-capabilities.md").symlink_to(live / "docs" / "labels-and-capabilities.md")
    (docs / "vendor-neutrality.md").write_text(
        (live / "docs" / "vendor-neutrality.md").read_text(encoding="utf-8"), encoding="utf-8"
    )


def test_render_doc_matches_live_file_when_in_sync() -> None:
    root = vns.find_repo_root()
    rendered = vns.render_doc(root)
    assert rendered == (root / vns.DOC_RELPATH).read_text(encoding="utf-8")


def test_write_doc_block_is_noop_when_in_sync() -> None:
    assert vns.write_doc_block(vns.find_repo_root()) is False


def test_in_sync_content_with_non_normalized_whitespace_is_a_noop(tmp_path) -> None:
    """A block whose content matches but whose surrounding whitespace is not the
    normalised single blank line must be left untouched — the hook keys on
    content, not byte-exact spacing, so it never churns the file (this is the
    scenario that made the byte-exact comparison fail on CI)."""
    _mirror_repo(tmp_path, vns.find_repo_root())
    doc = tmp_path / vns.DOC_RELPATH
    text = doc.read_text(encoding="utf-8")
    marker_end = text.index("-->", text.index(vns.DOC_BEGIN)) + len("-->")
    end = text.index(vns.DOC_END)
    block = text[marker_end:end].strip()
    # Extra blank lines around the (unchanged) block content.
    doc.write_text(text[:marker_end] + "\n\n\n" + block + "\n\n\n" + text[end:], encoding="utf-8")

    before = doc.read_text(encoding="utf-8")
    assert vns.write_doc_block(tmp_path) is False
    assert doc.read_text(encoding="utf-8") == before  # bytes untouched
    assert vns.render_doc(tmp_path) == before


def test_write_doc_block_regenerates_stale_block(tmp_path) -> None:
    _mirror_repo(tmp_path, vns.find_repo_root())
    doc = tmp_path / vns.DOC_RELPATH
    # Corrupt the generated block so it goes stale.
    text = doc.read_text(encoding="utf-8")
    marker_end = text.index("-->", text.index(vns.DOC_BEGIN)) + len("-->")
    end = text.index(vns.DOC_END)
    doc.write_text(text[:marker_end] + "\n\nSTALE\n\n" + text[end:], encoding="utf-8")

    assert vns.write_doc_block(tmp_path) is True
    assert vns.write_doc_block(tmp_path) is False  # idempotent second run
    refreshed = doc.read_text(encoding="utf-8")
    assert "STALE" not in refreshed
    block = refreshed.split(vns.DOC_BEGIN, 1)[1].split("-->", 1)[1].split(vns.DOC_END, 1)[0].strip()
    assert block == vns.render_markdown(*vns.compute_all(tmp_path)).strip()


def test_in_place_cli_exit_codes(tmp_path) -> None:
    _mirror_repo(tmp_path, vns.find_repo_root())
    doc = tmp_path / vns.DOC_RELPATH
    text = doc.read_text(encoding="utf-8")
    marker_end = text.index("-->", text.index(vns.DOC_BEGIN)) + len("-->")
    end = text.index(vns.DOC_END)
    doc.write_text(text[:marker_end] + "\n\nSTALE\n\n" + text[end:], encoding="utf-8")

    # First run rewrites the file → exit 1; second run is already in sync → exit 0.
    assert vns.main(["--in-place", "--repo-root", str(tmp_path)]) == 1
    assert vns.main(["--in-place", "--repo-root", str(tmp_path)]) == 0


def test_render_doc_raises_without_markers(tmp_path) -> None:
    _mirror_repo(tmp_path, vns.find_repo_root())
    (tmp_path / vns.DOC_RELPATH).write_text("no markers here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="markers missing"):
        vns.render_doc(tmp_path)
