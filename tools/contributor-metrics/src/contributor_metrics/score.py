# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Pure scoring: weights, pushback penalty, areas, timeline."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import date
from typing import Any

from contributor_metrics.model import CLASSES, Item, Weights

Select = Callable[[Item, "str | None"], bool]

METRICS: dict[str, Select] = {
    "prs_opened": lambda i, c: i.kind == "pr",
    "prs_merged": lambda i, c: i.kind == "pr" and i.merged,
    "reviews_total": lambda i, c: i.kind == "review",
    "reviews_substantive": lambda i, c: i.kind == "review" and i.substantive and c != "R",
    "issues_filed": lambda i, c: i.kind == "issue",
    "issues_triaged": lambda i, c: i.kind == "triage",
    "threads_commented": lambda i, c: i.kind == "thread",
}


def _months(since: str, end: str) -> list[str]:
    s, e = date.fromisoformat(since), date.fromisoformat(end)
    out: list[str] = []
    y, m = s.year, s.month
    while (y, m) <= (e.year, e.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _r(x: float) -> float:
    return round(x, 3)


def score(
    items: Iterable[Item],
    classes: Mapping[str, str],
    weights: Weights,
    *,
    since: str,
    end: str,
    area_prefix: str = "area:",
    caps_hit: Iterable[str] = (),
) -> dict[str, Any]:
    """Apply weights and the pushback penalty to the items inside [since, end]."""
    in_window = [i for i in items if since <= i.created_at[:10] <= end]
    known = {i.id for i in in_window}
    notes: list[str] = []
    cls: dict[str, str] = {}
    for item_id, c in classes.items():
        if item_id not in known:
            notes.append(f"class for unknown item {item_id} ignored")
        elif c not in CLASSES:
            notes.append(f"class {c!r} for {item_id} is not one of P/R/C; ignored")
        else:
            cls[item_id] = c

    def w(i: Item) -> float:
        return weights.weight_of(cls.get(i.id))

    metrics: dict[str, dict[str, float | int]] = {}
    for name, select in METRICS.items():
        chosen = [i for i in in_window if select(i, cls.get(i.id))]
        discounted = sum(w(i) for i in chosen)
        pushed_threads = {i.thread for i in chosen if cls.get(i.id) in ("P", "C")}
        penalty = weights.penalty * len(pushed_threads)
        metrics[name] = {
            "raw": len(chosen),
            "discounted": _r(discounted),
            "penalty": _r(penalty),
            "adjusted": _r(max(0.0, discounted - penalty)),
        }

    opened = [i for i in in_window if i.kind == "pr"]
    merged = [i for i in opened if i.merged]
    live_w = sum(w(i) for i in opened)
    merged_w = sum(w(i) for i in merged)
    merge_rate = {
        "raw": _r(len(merged) / len(opened)) if opened else None,
        "adjusted": _r(merged_w / live_w) if live_w else None,
    }

    per_area: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"prs": [], "reviews": []})
    for i in in_window:
        bucket = "prs" if (i.kind == "pr" and i.merged) else "reviews" if i.kind == "review" else None
        if bucket is None:
            continue
        for a in i.areas:
            if a.startswith(area_prefix):
                per_area[a][bucket].append(w(i))
    totals = {b: sum(sum(v[b]) for v in per_area.values()) for b in ("prs", "reviews")}
    areas = []
    for a in sorted(per_area):
        entry: dict[str, Any] = {"area": a}
        for b in ("prs", "reviews"):
            adj = sum(per_area[a][b])
            entry[b] = {
                "raw": len(per_area[a][b]),
                "adjusted": _r(adj),
                "share": _r(adj / totals[b]) if totals[b] else 0.0,
            }
        areas.append(entry)
    breadth = {
        "raw": sum(1 for v in per_area.values() if v["prs"]),
        "adjusted": sum(1 for v in per_area.values() if sum(v["prs"]) >= 1),
    }

    timeline = dict.fromkeys(_months(since, end), 0)
    for i in in_window:
        if w(i) > 0 and i.created_at[:7] in timeline:
            timeline[i.created_at[:7]] += 1

    flagged = [
        {"id": i.id, "url": i.url, "class": cls[i.id], "weight": w(i), "penalised": cls[i.id] in ("P", "C")}
        for i in in_window
        if i.id in cls
    ]
    return {
        "window": {"since": since, "end": end},
        "weights": weights.to_json(),
        "notes": notes,
        "metrics": metrics,
        "merge_rate": merge_rate,
        "areas": areas,
        "area_breadth": breadth,
        "timeline": timeline,
        "flagged": flagged,
        "caps_hit": list(caps_hit),
    }
