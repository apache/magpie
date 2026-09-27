# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
from contributor_metrics.floors import propose_floors, weighted_percentile

TODAY = "2026-09-27"


def row(target, outcome, prs, issues=0, vote="2026-06-01", capped=()):
    return {
        "target": target,
        "outcome": outcome,
        "vote_date": vote,
        "metrics": {"prs_merged": prs, "issues_filed": issues},
        "capped": list(capped),
    }


def test_weighted_percentile_is_nearest_rank_by_cumulative_weight():
    values = [(40, 1.0), (48, 1.0), (55, 1.0), (60, 1.0), (72, 1.0)]
    assert weighted_percentile(values, 0.25) == 48
    assert weighted_percentile(values, 0.5) == 55


def test_separating_metric_gets_the_elected_p25_floor():
    rows = [row("committer", "elected", p, i) for p, i in [(40, 3), (48, 2), (55, 4), (60, 3), (72, 5)]]
    rows += [row("committer", "deferred", p, i) for p, i in [(10, 0), (15, 1), (20, 1)]]
    out = propose_floors(rows, today=TODAY)
    assert out["floors"]["committer"] == {"prs_merged": 48, "issues_filed": 3}
    assert out["evidence_only"]["committer"] == []


def test_non_separating_metric_is_evidence_only_with_floor_zero():
    rows = [row("committer", "elected", p, i) for p, i in [(40, 1), (48, 0), (55, 2), (60, 1), (72, 0)]]
    rows += [row("committer", "deferred", p, i) for p, i in [(10, 1), (15, 2), (20, 0)]]
    out = propose_floors(rows, today=TODAY)
    assert out["floors"]["committer"]["issues_filed"] == 0
    assert out["evidence_only"]["committer"] == ["issues_filed"]


def test_target_with_too_few_elected_rows_gets_no_floors():
    rows = [row("committer", "elected", p) for p in (40, 48, 55, 60, 72)] + [
        row("pmc", "elected", 45),
        row("pmc", "elected", 52),
    ]
    out = propose_floors(rows, today=TODAY)
    assert out["no_floors_for"] == ["pmc"]
    assert out["floors"]["pmc"] == {}


def test_recent_elected_rows_outweigh_old_ones():
    old = [row("committer", "elected", 10, vote="2016-06-01") for _ in range(3)]
    recent = [row("committer", "elected", 50, vote="2026-06-01") for _ in range(3)]
    out = propose_floors([*old, *recent, row("committer", "deferred", 5)], today=TODAY)
    assert out["floors"]["committer"]["prs_merged"] == 50


def test_capped_values_are_left_out_of_that_metric_only():
    rows = [row("committer", "elected", p) for p in (40, 48, 55, 60, 72)]
    rows.append(row("committer", "elected", 3, capped=["prs_merged"]))
    rows += [row("committer", "deferred", p) for p in (10, 15, 20)]
    out = propose_floors(rows, today=TODAY)
    assert out["floors"]["committer"]["prs_merged"] == 48
    assert out["distribution"]["committer"]["prs_merged"]["excluded_capped"] == 1


def test_withdrawn_rows_are_ignored():
    rows = [row("committer", "elected", p) for p in (40, 48, 55, 60, 72)] + [row("committer", "withdrawn", 1)]
    rows += [row("committer", "deferred", p) for p in (10, 15, 20)]
    assert propose_floors(rows, today=TODAY)["floors"]["committer"]["prs_merged"] == 48


def test_no_deferred_rows_keeps_the_floor_and_says_separation_was_not_tested():
    rows = [row("committer", "elected", p) for p in (40, 48, 55, 60, 72)]
    out = propose_floors(rows, today=TODAY)
    assert out["floors"]["committer"]["prs_merged"] == 48
    assert any("no deferred" in n for n in out["notes"])
