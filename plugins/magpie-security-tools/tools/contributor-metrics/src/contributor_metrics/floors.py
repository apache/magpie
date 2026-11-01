# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Threshold floors from past nomination outcomes — the arithmetic `calibrate` proposes."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any

RECENT_YEARS = 3.0

# Floors are deliberately set below what the project has elected, so the lists built on them
# surface more people than the governing body would pick; the decision is always theirs.
DEFAULT_RELAXATION = 0.75


def weighted_percentile(values: Sequence[tuple[float, float]], q: float) -> float:
    """Smallest value whose cumulative weight reaches q times the total weight (nearest rank)."""
    ordered = sorted(values)
    total = sum(w for _, w in ordered)
    target = q * total
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= target - 1e-12:
            return value
    return ordered[-1][0]


def _age_years(vote_date: str, today: str) -> float:
    return max(0.0, (date.fromisoformat(today) - date.fromisoformat(vote_date)).days / 365.25)


def _stats(values: list[tuple[float, float]]) -> dict[str, float | None]:
    if not values:
        return {"p25": None, "median": None, "n": 0}
    return {
        "p25": weighted_percentile(values, 0.25),
        "median": weighted_percentile(values, 0.5),
        "n": len(values),
    }


def propose_floors(
    rows: Iterable[Mapping[str, Any]],
    *,
    today: str,
    halflife: float = 2.0,
    min_elected: int = 5,
    relaxation: float = DEFAULT_RELAXATION,
) -> dict[str, Any]:
    """Propose per-target floors: the recency-weighted p25 of elected rows, scaled down by `relaxation`.

    Separation is tested on the unrelaxed p25; a metric that does not separate is evidence-only.
    """
    if not 0.0 < relaxation <= 1.0:
        raise ValueError(f"relaxation must be in (0, 1], got {relaxation}")
    rows = [r for r in rows if r.get("outcome") in ("elected", "deferred")]
    targets = sorted({r["target"] for r in rows})
    metrics = sorted({m for r in rows for m in r.get("metrics", {})})
    out: dict[str, Any] = {
        "floors": {},
        "evidence_only": {},
        "no_floors_for": [],
        "distribution": {},
        "relaxation": relaxation,
        "notes": [],
    }
    for target in targets:
        mine = [r for r in rows if r["target"] == target]
        elected_n = sum(1 for r in mine if r["outcome"] == "elected")
        out["floors"][target] = {}
        out["evidence_only"][target] = []
        out["distribution"][target] = {}
        if elected_n < min_elected:
            out["no_floors_for"].append(target)
            out["notes"].append(
                f"{target}: {elected_n} elected rows, fewer than {min_elected}; no floors proposed"
            )
            continue
        deferred_n = sum(1 for r in mine if r["outcome"] == "deferred")
        if deferred_n == 0:
            out["notes"].append(f"{target}: no deferred rows, so separation was not tested")
        for metric in metrics:
            dist: dict[str, Any] = {"excluded_capped": 0}
            buckets: dict[str, list[tuple[float, float]]] = {
                k: [] for k in ("elected", "deferred", "elected_recent", "elected_older")
            }
            for r in mine:
                if metric not in r.get("metrics", {}):
                    continue
                if metric in r.get("capped", ()):
                    dist["excluded_capped"] += 1
                    continue
                age = _age_years(r["vote_date"], today)
                pair = (float(r["metrics"][metric]), 0.5 ** (age / halflife))
                buckets[r["outcome"]].append(pair)
                if r["outcome"] == "elected":
                    buckets["elected_recent" if age <= RECENT_YEARS else "elected_older"].append(pair)
            dist.update({k: _stats(v) for k, v in buckets.items()})
            out["distribution"][target][metric] = dist
            elected_p25 = dist["elected"]["p25"]
            if elected_p25 is None:
                continue
            deferred_median = dist["deferred"]["median"]
            if deferred_median is not None and math.floor(elected_p25) <= deferred_median:
                out["floors"][target][metric] = 0
                out["evidence_only"][target].append(metric)
            else:
                out["floors"][target][metric] = math.floor(relaxation * elected_p25)
    return out
