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


def test_separating_metric_gets_three_quarters_of_the_elected_p25_by_default():
    rows = [row("committer", "elected", p, i) for p, i in [(40, 3), (48, 2), (55, 4), (60, 3), (72, 5)]]
    rows += [row("committer", "deferred", p, i) for p, i in [(10, 0), (15, 1), (20, 1)]]
    out = propose_floors(rows, today=TODAY)
    assert out["floors"]["committer"] == {"prs_merged": 36, "issues_filed": 2}
    assert out["evidence_only"]["committer"] == []
    assert out["relaxation"] == 0.75


def test_relaxation_one_gives_the_unrelaxed_elected_p25():
    rows = [row("committer", "elected", p, i) for p, i in [(40, 3), (48, 2), (55, 4), (60, 3), (72, 5)]]
    rows += [row("committer", "deferred", p, i) for p, i in [(10, 0), (15, 1), (20, 1)]]
    out = propose_floors(rows, today=TODAY, relaxation=1.0)
    assert out["floors"]["committer"] == {"prs_merged": 48, "issues_filed": 3}


def test_separation_is_tested_on_the_unrelaxed_p25():
    # Relaxed, 48 becomes 36, which is at or below the deferred median of 40; unrelaxed, it separates.
    rows = [row("committer", "elected", p) for p in (40, 48, 55, 60, 72)]
    rows += [row("committer", "deferred", p) for p in (38, 40, 45)]
    out = propose_floors(rows, today=TODAY)
    assert out["floors"]["committer"]["prs_merged"] == 36
    assert "prs_merged" not in out["evidence_only"]["committer"]


def test_relaxation_outside_zero_to_one_is_rejected():
    rows = [row("committer", "elected", p) for p in (40, 48, 55, 60, 72)]
    for bad in (0.0, 1.5, -0.1):
        try:
            propose_floors(rows, today=TODAY, relaxation=bad)
        except ValueError:
            continue
        raise AssertionError(f"relaxation={bad} was accepted")


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
    assert out["floors"]["committer"]["prs_merged"] == 37


def test_capped_values_are_left_out_of_that_metric_only():
    rows = [row("committer", "elected", p) for p in (40, 48, 55, 60, 72)]
    rows.append(row("committer", "elected", 3, capped=["prs_merged"]))
    rows += [row("committer", "deferred", p) for p in (10, 15, 20)]
    out = propose_floors(rows, today=TODAY)
    assert out["floors"]["committer"]["prs_merged"] == 36
    assert out["distribution"]["committer"]["prs_merged"]["excluded_capped"] == 1


def test_withdrawn_rows_are_ignored():
    rows = [row("committer", "elected", p) for p in (40, 48, 55, 60, 72)] + [row("committer", "withdrawn", 1)]
    rows += [row("committer", "deferred", p) for p in (10, 15, 20)]
    assert propose_floors(rows, today=TODAY)["floors"]["committer"]["prs_merged"] == 36


def test_no_deferred_rows_keeps_the_floor_and_says_separation_was_not_tested():
    rows = [row("committer", "elected", p) for p in (40, 48, 55, 60, 72)]
    out = propose_floors(rows, today=TODAY)
    assert out["floors"]["committer"]["prs_merged"] == 36
    assert any("no deferred" in n for n in out["notes"])


def with_posts(r, posts):
    return {**r, "metrics": {**r["metrics"], "mailing_list_posts": posts}}


def test_mailing_list_metric_on_no_row_is_reported_as_not_collected():
    rows = [row("committer", "elected", p) for p in (40, 48, 55, 60, 72)]
    rows += [row("committer", "deferred", 10)]
    out = propose_floors(rows, today=TODAY)
    assert "committer: mailing_list_posts not collected; no floor proposed" in out["notes"]
    assert "mailing_list_posts" not in out["floors"]["committer"]
    assert "mailing_list_posts" not in out["evidence_only"]["committer"]


def test_mailing_list_metric_on_some_rows_counts_the_unknown_rows():
    rows = [with_posts(row("committer", "elected", p), 20) for p in (40, 48, 55, 60, 72)]
    rows += [row("committer", "elected", 80), with_posts(row("committer", "deferred", 10), 2)]
    out = propose_floors(rows, today=TODAY)
    assert "committer: mailing_list_posts unknown for 1 of 7 rows" in out["notes"]
    assert out["floors"]["committer"]["mailing_list_posts"] == 15


def test_mailing_list_metric_on_every_row_adds_no_note():
    rows = [with_posts(row("committer", "elected", p), 20) for p in (40, 48, 55, 60, 72)]
    rows += [with_posts(row("committer", "deferred", 10), 2)]
    out = propose_floors(rows, today=TODAY)
    assert out["notes"] == []


def test_mailing_list_metric_known_for_too_few_elected_rows_gets_no_floor():
    rows = [with_posts(row("committer", "elected", 40), 40)]
    rows += [row("committer", "elected", p) for p in (48, 55, 60, 72)]
    rows += [with_posts(row("committer", "deferred", 10), 2)]
    out = propose_floors(rows, today=TODAY)
    assert "mailing_list_posts" not in out["floors"]["committer"]
    assert (
        "committer: mailing_list_posts known for 1 elected rows, fewer than 5; no floor proposed"
        in out["notes"]
    )


def test_mailing_list_metric_unknown_for_every_deferred_row_says_separation_was_not_tested():
    rows = [with_posts(row("committer", "elected", p), 20) for p in (40, 48, 55, 60, 72)]
    rows += [row("committer", "deferred", 10)]
    out = propose_floors(rows, today=TODAY)
    assert (
        "committer: mailing_list_posts unknown for every deferred row; separation not tested" in out["notes"]
    )


def test_mailing_list_metric_on_one_target_only_gives_the_other_a_single_note():
    rows = [with_posts(row("committer", "elected", p), 20) for p in (40, 48, 55, 60, 72)]
    rows += [row("pmc", "elected", p) for p in (40, 48, 55, 60, 72)]
    rows += [with_posts(row("committer", "deferred", 10), 2), row("pmc", "deferred", 10)]
    out = propose_floors(rows, today=TODAY)
    assert [n for n in out["notes"] if n.startswith("pmc:")] == [
        "pmc: mailing_list_posts not collected; no floor proposed"
    ]
    assert "mailing_list_posts" not in out["distribution"]["pmc"]
