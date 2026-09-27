# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
from contributor_metrics.model import Item, Weights
from contributor_metrics.score import score

SINCE, END = "2026-03-01", "2026-08-31"


def pr(
    n: int,
    *,
    merged: bool = True,
    closed: bool = False,
    areas: tuple[str, ...] = (),
    date: str = "2026-05-01",
) -> Item:
    url = f"https://github.com/o/r/pull/{n}"
    return Item(
        id=f"pr-{n}",
        kind="pr",
        url=url,
        thread=url,
        created_at=date,
        merged=merged,
        closed_unmerged=closed,
        areas=areas,
    )


def review(n: int, *, substantive: bool = True, areas: tuple[str, ...] = ()) -> Item:
    url = f"https://github.com/o/r/pull/{n}"
    return Item(
        id=f"review-{n}",
        kind="review",
        url=url,
        thread=url,
        created_at="2026-05-02",
        substantive=substantive,
        areas=areas,
    )


def run(items, classes=None, **w):
    weights, notes = Weights.from_mapping(w)
    return score(items, classes or {}, weights, since=SINCE, end=END, area_prefix="area:"), notes


def test_unflagged_items_count_fully():
    out, _ = run([pr(1), pr(2), review(3)])
    assert out["metrics"]["prs_merged"] == {"raw": 2, "discounted": 2.0, "penalty": 0.0, "adjusted": 2.0}
    assert out["metrics"]["reviews_substantive"]["adjusted"] == 1.0


def test_penalty_defaults():
    items = [pr(1), pr(2, merged=False, closed=True), pr(3), pr(4)]
    out, _ = run(items, {"pr-1": "P", "pr-2": "C"})
    m = out["metrics"]
    assert m["prs_merged"] == {"raw": 3, "discounted": 2.25, "penalty": 0.25, "adjusted": 2.0}
    assert m["prs_opened"] == {"raw": 4, "discounted": 2.25, "penalty": 0.5, "adjusted": 1.75}


def test_penalty_zero_reproduces_discount_only():
    out, _ = run([pr(1), pr(2)], {"pr-1": "P"}, automated_pushback_penalty=0)
    assert out["metrics"]["prs_merged"]["adjusted"] == out["metrics"]["prs_merged"]["discounted"] == 1.25


def test_adjusted_never_negative():
    items = [pr(n, merged=False, closed=True) for n in range(1, 5)]
    out, _ = run(items, {f"pr-{n}": "C" for n in range(1, 5)})
    assert out["metrics"]["prs_opened"]["adjusted"] == 0.0


def test_penalty_once_per_thread_within_a_count():
    url = "https://github.com/o/r/pull/9"
    items = [
        Item(
            id="review-9a",
            kind="review",
            url=url + "#a",
            thread=url,
            created_at="2026-05-02",
            substantive=True,
        ),
        Item(
            id="review-9b",
            kind="review",
            url=url + "#b",
            thread=url,
            created_at="2026-05-03",
            substantive=True,
        ),
    ]
    out, _ = run(items, {"review-9a": "P", "review-9b": "P"})
    assert out["metrics"]["reviews_total"]["penalty"] == 0.25


def test_restatement_not_penalised_and_never_substantive():
    out, _ = run([review(1)], {"review-1": "R"})
    m = out["metrics"]
    assert m["reviews_total"] == {"raw": 1, "discounted": 0.0, "penalty": 0.0, "adjusted": 0.0}
    assert m["reviews_substantive"]["raw"] == 0


def test_items_outside_window_ignored():
    out, _ = run([pr(1, date="2025-12-31"), pr(2, date="2026-09-01"), pr(3)])
    assert out["metrics"]["prs_merged"]["raw"] == 1


def test_area_shares_and_breadth():
    items = [
        pr(1, areas=("area:a",)),
        pr(2, areas=("area:a",)),
        pr(3, areas=("area:b",)),
        pr(4, areas=("area:b",)),
    ]
    out, _ = run(items, {"pr-3": "P", "pr-4": "P"})
    areas = {a["area"]: a for a in out["areas"]}
    assert areas["area:a"]["prs"] == {"raw": 2, "adjusted": 2.0, "share": 0.8}
    assert areas["area:b"]["prs"] == {"raw": 2, "adjusted": 0.5, "share": 0.2}
    assert out["area_breadth"] == {"raw": 2, "adjusted": 1}


def test_labels_without_the_area_prefix_are_not_areas():
    out, _ = run([pr(1, areas=("area:a", "kind:bug"))])
    assert [a["area"] for a in out["areas"]] == ["area:a"]


def test_merge_rate_excludes_zero_weight():
    items = [pr(1), pr(2, merged=False, closed=True), pr(3, merged=False)]
    out, _ = run(items, {"pr-2": "C"})
    assert out["merge_rate"] == {"raw": round(1 / 3, 3), "adjusted": 0.5}


def test_timeline_zero_filled_and_skips_zero_weight():
    out, _ = run(
        [pr(1, date="2026-03-05"), pr(2, merged=False, closed=True, date="2026-04-05")], {"pr-2": "C"}
    )
    assert out["timeline"]["2026-03"] == 1
    assert out["timeline"]["2026-04"] == 0
    assert list(out["timeline"]) == ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]


def test_score_ignores_unknown_class_ids():
    out, _ = run([pr(1)], {"pr-999": "P", "pr-1": "X"})
    assert out["metrics"]["prs_merged"]["adjusted"] == 1.0
    assert any("pr-999" in n for n in out["notes"])
    assert any("pr-1" in n and "X" in n for n in out["notes"])


def test_weights_out_of_range_fall_back():
    weights, notes = Weights.from_mapping(
        {"automated_pushback_penalty": 2, "automated_contribution_weight": "high"}
    )
    assert weights.penalty == 0.25 and weights.automated == 0.25
    assert len(notes) == 2


def test_flagged_lists_classified_items():
    out, _ = run([pr(1), pr(2)], {"pr-1": "P"})
    assert out["flagged"] == [
        {
            "id": "pr-1",
            "url": "https://github.com/o/r/pull/1",
            "class": "P",
            "weight": 0.25,
            "penalised": True,
        }
    ]


def test_area_shares_are_over_all_merged_prs_with_an_unlabelled_row():
    out, _ = run([pr(1, areas=("area:a",)), pr(2), pr(3), pr(4)])
    areas = {a["area"]: a for a in out["areas"]}
    assert areas["area:a"]["prs"]["share"] == 0.25
    assert areas["(unlabelled)"]["prs"] == {"raw": 3, "adjusted": 3.0, "share": 0.75}


def test_boolean_weight_is_rejected():
    weights, notes = Weights.from_mapping({"automated_pushback_penalty": True})
    assert weights.penalty == 0.25 and len(notes) == 1
