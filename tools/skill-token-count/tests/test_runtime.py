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

from pathlib import Path
from typing import Any

import pytest

from skill_token_count.runtime import extract_result, percentile, summarize, usage_totals


def test_percentile_matches_median_and_interpolates() -> None:
    assert percentile([10, 20, 30, 40], 0.5) == 25
    assert percentile([10, 20, 30, 40], 0.9) == 37
    assert percentile([8], 0.9) == 8


def test_empty_percentile_is_not_zero() -> None:
    with pytest.raises(ValueError):
        percentile([], 0.5)


def test_usage_includes_cache_and_auxiliary_models_without_double_counting_thinking() -> None:
    usage = {
        "inputTokens": 10,
        "cacheReadInputTokens": 100,
        "cacheCreationInputTokens": 50,
        "outputTokens": 20,
        "thinkingTokens": 12,
    }
    totals = usage_totals({"modelUsage": {"primary": usage, "auxiliary": usage}})
    assert totals["totalTokens"] == 360
    assert totals["outputTokens"] == 40


@pytest.mark.parametrize("bad", [{}, {"modelUsage": {}}, {"modelUsage": {"m": {"inputTokens": 1}}}])
def test_missing_usage_is_error(bad: dict) -> None:
    with pytest.raises(ValueError):
        usage_totals(bad)


def test_accepts_object_and_event_array() -> None:
    result = {"type": "result", "is_error": False}
    assert extract_result(result) == result
    assert extract_result([{"type": "system"}, result]) == result
    with pytest.raises(ValueError):
        extract_result([result, result])


def test_summary_reports_failures_and_counts_distinct_workloads() -> None:
    records: list[dict[str, Any]] = [
        {
            "mode": "Pairing",
            "skill": "pairing-self-review",
            "status": "success",
            "case": "a",
            "usage": {"totalTokens": 10},
        },
        {
            "mode": "Pairing",
            "skill": "pairing-self-review",
            "status": "success",
            "case": "a",
            "usage": {"totalTokens": 30},
        },
        {"mode": "Pairing", "skill": "pairing-self-review", "status": "error", "case": "b"},
        {"mode": "Drafting", "skill": "issue-fix-workflow", "status": "error", "case": "c"},
    ]
    summary = {row["mode"]: row for row in summarize(records)}
    assert summary["Pairing"]["p50_total_tokens"] == 20
    assert summary["Pairing"]["attempts"] == 3
    assert summary["Pairing"]["distinct_cases"] == 1
    assert summary["Pairing"]["failed"] == 1
    assert summary["Drafting"]["p50_total_tokens"] is None


@pytest.mark.parametrize("name", ["2026-09-11", "2026-09-11-drafting"])
def test_published_snapshot_matches_raw_usage_and_report(name: str) -> None:
    import hashlib
    import json
    import re

    from skill_token_count.runtime import markdown_report, validate_case_mode

    directory = Path(__file__).resolve().parents[1] / "benchmarks"
    document = json.loads((directory / f"{name}.json").read_text())
    assert (
        document["corpus_sha256"]
        == hashlib.sha256((directory / document["corpus_file"]).read_bytes()).hexdigest()
    )
    corpus = json.loads((directory / document["corpus_file"]).read_text())
    cases = {case["id"]: case for case in corpus["cases"]}
    root = directory.parents[2]
    for record in document["records"]:
        case = cases[record["case"]]
        assert record["mode"] == case["mode"]
        assert record["skill"] == case["skill"]
        validate_case_mode(root, case)
        assert record["usage"] == usage_totals({"modelUsage": record["model_usage"]})
        assert record["response"].strip()
    published = (directory / f"{name}.md").read_text()
    # doctoc is an independent generated navigation block.
    published = re.sub(
        r"<!-- START doctoc.*?<!-- END doctoc generated TOC please keep comment here to allow auto update -->",
        "",
        published,
        flags=re.DOTALL,
    )
    assert published.strip() == markdown_report(document).strip()


def test_rejects_wrong_mode_before_launch(tmp_path: Path) -> None:
    from skill_token_count.runtime import build_prompt

    skill = tmp_path / "skills" / "author"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nmode: Mentoring\n---\nAuthor an issue.")
    with pytest.raises(ValueError, match="Mode mismatch"):
        build_prompt(tmp_path, {}, {"skill": "author", "mode": "Drafting"})


def test_summary_does_not_pool_different_skills() -> None:
    records = [
        {
            "mode": "Mentoring",
            "skill": skill,
            "status": "success",
            "case": skill,
            "usage": {"totalTokens": tokens},
        }
        for skill, tokens in [("mentor", 10), ("author", 100)]
    ]
    rows = summarize(records)
    assert len(rows) == 2
    assert {row["skill"]: row["p50_total_tokens"] for row in rows} == {"mentor": 10, "author": 100}
