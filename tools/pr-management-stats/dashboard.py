#!/usr/bin/env python3
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

"""
Full HTML-rendering extension on top of reference.py.

reference.py stops at fetch + classify + JSON sidecar; this script
reuses its primitives, then computes every aggregate from aggregate.md
and emits the 11-section dashboard from render.md.

Usage:
  dashboard.py --repo apache/airflow --viewer potiuk \\
      [--since 2026-04-12] [--out dashboard.html]

Output:
  - <out>            HTML dashboard (all 11 sections per render.md)
  - <out-stem>.json  Intermediate state (superset of reference.py's keys —
                     identical values on every shared key; see
                     tests/test_json_parity.py)

Design: directory-portable, not single-file. This script reuses
reference.py's fetch + classify primitives by importing them from the
sibling module, so the whole tools/pr-management-stats/ directory must
travel together. Run it as a script (`python3 dashboard.py ...`) — the
directory of the running script is on sys.path[0], so the sibling import
resolves regardless of the current working directory. It is NOT a package
(the directory name is not a valid module identifier) and cannot be run
with `python3 -m`. The JSON sidecar contract is preserved so existing
reference.py consumers don't break.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Sibling-module import — see the module docstring's "Design" note. Resolves
# because the running script's directory is sys.path[0]; the directory is not
# a Python package, so the tool is directory-portable rather than self-contained.
from reference import (
    CLOSED_PRS_QUERY,
    COLLAB_ASSOCIATIONS,
    DEFAULT_AI_FOOTER,
    DEFAULT_AREA_PREFIX,
    DEFAULT_READY_LABEL,
    DEFAULT_TRIAGE_MARKER,
    OPEN_PRS_QUERY,
    classify,
    compute_codeowners_panel,
    compute_weekly_velocity,
    fetch_codeowners,
    fetch_ready_pr_files,
    fold_triaged_at,
    is_backport,
    is_bot,
    paginated_search,
    parse_iso,
    triage_marker_events,
    weeks_buckets,
)

# ============================================================
# Colour palette (render.md#colour-scheme)
# ============================================================

C_GREEN = "#56d364"
C_AMBER = "#d29922"
C_RED = "#f85149"
C_CYAN = "#76e3ea"
C_AREA = "#56d4dd"
C_BLUE = "#58a6ff"
C_MAGENTA = "#db61a2"
C_GREY = "#6e7681"
C_DIM = "#8b949e"
C_BG = "#0d1117"
C_PANEL = "#161b22"
C_BORDER = "#30363d"
C_FG = "#c9d1d9"

# Ready-for-review split colours (render.md § Ready-for-review queue split).
# These are deliberately distinct from the generic palette so the four
# why-waiting sub-states keep the same hues across the hero cards and the
# age-timeline line chart.
C_SPLIT_NEVER = "#da3633"  # never reviewed (red)
C_SPLIT_DISCUSSED = "#388bfd"  # discussed, no decision (blue)
C_SPLIT_CHANGES = "#d29922"  # changes requested (amber)
C_SPLIT_APPROVED = "#2ea043"  # approved, awaiting merge (green)

# Age buckets for the ready-split timeline, newest → oldest. The timeline
# chart reverses these so the x-axis reads oldest-on-left (past → present).
READY_AGE_BUCKETS = ["0-2w", "2-4w", "4-8w", "8-12w", ">12w"]

# Distinct palette for multi-area line charts (top-areas). The pressure-band
# colours (red/amber/grey) repeat across areas and are visually
# indistinguishable; this palette gives each area its own hue.
AREA_PALETTE = [
    "#58a6ff",  # blue
    "#f85149",  # red
    "#56d364",  # green
    "#d29922",  # amber
    "#a371f7",  # purple
    "#e34c9e",  # pink
    "#39c5cf",  # cyan
    "#db6d28",  # orange
]


# ============================================================
# Tiny utilities
# ============================================================


def esc(s) -> str:
    if s is None:
        return ""
    return html.escape(str(s))


def pct(num: float, denom: float) -> float:
    if not denom:
        return 0.0
    return round(100.0 * num / denom, 1)


def colour_for_pct(p: float) -> str:
    """render.md: green ≥ 50, amber 20–49, red < 20."""
    if p >= 50:
        return C_GREEN
    if p >= 20:
        return C_AMBER
    return C_RED


def colour_for_pressure(score: int) -> str:
    """render.md#pressure-score band: red ≥30, amber 15-29, grey <15."""
    if score >= 30:
        return C_RED
    if score >= 15:
        return C_AMBER
    return C_GREY


def week_label(dt: datetime) -> str:
    return dt.strftime("%m-%d")


# ============================================================
# SVG render helpers
# ============================================================


def svg_line_chart(series, *, width=720, height=220, colours=None, y_max=None,
                    y_label="", x_labels=None):
    """Multi-series inline SVG line chart per render.md#inline-svg-line-chart-helper."""
    if not series:
        return f'<svg viewBox="0 0 {width} {height}"></svg>'
    colours = colours or [C_BLUE, C_GREEN, C_RED, C_AMBER, C_MAGENTA]
    pad_l, pad_r, pad_t, pad_b = 50, 110, 14, 30
    w_in = width - pad_l - pad_r
    h_in = height - pad_t - pad_b
    flat = [v for s in series for v in s["values"]]
    if not flat:
        return f'<svg viewBox="0 0 {width} {height}"></svg>'
    vmax = y_max if y_max is not None else (max(flat) or 1)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:{C_PANEL};border:1px solid {C_BORDER};border-radius:6px;">'
    ]
    for i in range(5):
        y = pad_t + i * h_in / 4
        v = vmax - i * vmax / 4
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
            f'stroke="{C_BORDER}" stroke-width="0.5"/>'
        )
        parts.append(
            f'<text x="{pad_l - 6}" y="{y + 3:.1f}" fill="{C_DIM}" '
            f'font-size="10" text-anchor="end">{v:.0f}</text>'
        )
    if x_labels:
        n = len(x_labels)
        for i, lbl in enumerate(x_labels):
            x = pad_l + i * w_in / max(n - 1, 1)
            parts.append(
                f'<text x="{x:.1f}" y="{height - 10}" fill="{C_DIM}" '
                f'font-size="10" text-anchor="middle">{esc(lbl)}</text>'
            )
    if y_label:
        parts.append(
            f'<text x="10" y="{pad_t + h_in / 2}" fill="{C_DIM}" font-size="10" '
            f'transform="rotate(-90 10 {pad_t + h_in / 2})" text-anchor="middle">{esc(y_label)}</text>'
        )
    for idx, s in enumerate(series):
        vals = s["values"]
        n = len(vals)
        c = s.get("colour") or colours[idx % len(colours)]
        pts = []
        for i, v in enumerate(vals):
            x = pad_l + i * w_in / max(n - 1, 1)
            y = pad_t + h_in - (v / vmax) * h_in if vmax else pad_t + h_in
            pts.append((x, y, v))
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts)
        parts.append(
            f'<polyline fill="none" stroke="{c}" stroke-width="2" points="{d}"/>'
        )
        for x, y, v in pts:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{c}"/>')
        parts.append(
            f'<rect x="{width - pad_r + 4}" y="{pad_t + idx * 18 - 6}" '
            f'width="10" height="10" fill="{c}"/>'
        )
        parts.append(
            f'<text x="{width - pad_r + 18}" y="{pad_t + idx * 18 + 3}" '
            f'fill="{C_FG}" font-size="11">{esc(s["label"])}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def svg_stacked_horizontal_bars(rows, *, width=720, height=None,
                                 segment_keys, segment_colours, row_height=30,
                                 row_labels=None):
    """N-row stacked horizontal bars (one per bucket)."""
    height = height or (row_height * len(rows) + 40)
    pad_l, pad_r, pad_t, pad_b = 70, 30, 10, 30
    w_in = width - pad_l - pad_r
    max_total = max(
        (sum(r.get(k, 0) for k in segment_keys) for r in rows), default=0
    )
    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:{C_PANEL};border:1px solid {C_BORDER};border-radius:6px;">'
    ]
    for i, row in enumerate(rows):
        y = pad_t + i * row_height
        total = sum(row.get(k, 0) for k in segment_keys)
        label = row_labels[i] if row_labels else ""
        parts.append(
            f'<text x="{pad_l - 6}" y="{y + row_height / 2 + 3:.1f}" '
            f'fill="{C_DIM}" font-size="10" text-anchor="end">{esc(label)}</text>'
        )
        if max_total == 0:
            continue
        bar_w = (total / max_total) * w_in
        offset = 0.0
        for key, colour in zip(segment_keys, segment_colours):
            v = row.get(key, 0)
            if v == 0:
                continue
            seg_w = (v / total) * bar_w if total else 0
            parts.append(
                f'<rect x="{pad_l + offset:.1f}" y="{y + 4:.1f}" '
                f'width="{seg_w:.1f}" height="{row_height - 8}" fill="{colour}"/>'
            )
            if seg_w > 24:
                parts.append(
                    f'<text x="{pad_l + offset + seg_w / 2:.1f}" '
                    f'y="{y + row_height / 2 + 3:.1f}" fill="{C_BG}" '
                    f'font-size="10" text-anchor="middle">{v}</text>'
                )
            offset += seg_w
        if total > 0:
            parts.append(
                f'<text x="{pad_l + bar_w + 6:.1f}" '
                f'y="{y + row_height / 2 + 3:.1f}" fill="{C_FG}" '
                f'font-size="10">{total}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


# ============================================================
# CSS  (inline so dashboard.py + reference.py are independently carry-over-able)
# ============================================================


CSS = f"""
<style>
* {{ box-sizing: border-box; }}
body {{
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: {C_BG};
  color: {C_FG};
  margin: 0;
  padding: 24px;
  max-width: 1240px;
  margin-left: auto;
  margin-right: auto;
}}
h1 {{ font-size: 22px; margin: 0 0 4px; }}
h2 {{ font-size: 16px; margin: 28px 0 12px; padding-bottom: 6px; border-bottom: 1px solid {C_BORDER}; }}
h3 {{ font-size: 13px; margin: 12px 0 6px; color: {C_DIM}; font-weight: 600; }}
.context {{ color: {C_DIM}; font-size: 12px; }}
.warn {{ background: rgba(248,81,73,0.1); border: 1px solid {C_RED}; padding: 10px 14px;
        border-radius: 6px; margin: 12px 0; color: {C_RED}; font-size: 12px; }}
.hero {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 12px 0; }}
.card {{ background: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 6px;
         padding: 16px; }}
.card .big {{ font-size: 28px; font-weight: 600; line-height: 1.1; }}
.card .sub {{ font-size: 12px; color: {C_DIM}; margin-top: 6px; line-height: 1.4; }}
.action {{ border-left: 4px solid {C_BORDER}; padding: 12px 16px; margin: 8px 0;
           background: {C_PANEL}; border-radius: 0 6px 6px 0; }}
.action.high {{ border-left-color: {C_RED}; }}
.action.medium {{ border-left-color: {C_AMBER}; }}
.action.low {{ border-left-color: {C_GREY}; }}
.action .title {{ font-weight: 600; margin-bottom: 4px; }}
.action .detail {{ font-size: 12px; color: {C_DIM}; }}
.action code {{ display: inline-block; background: {C_BG}; padding: 4px 8px;
                border-radius: 4px; margin-top: 8px; font-size: 12px;
                color: {C_CYAN}; user-select: all; }}
.panel {{ background: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 6px;
          padding: 16px; margin: 8px 0; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th, td {{ padding: 6px 8px; border-bottom: 1px solid {C_BORDER}; text-align: right; }}
th:first-child, td:first-child {{ text-align: left; }}
th {{ background: {C_PANEL}; font-weight: 600; color: {C_DIM}; }}
tr.total td {{ background: rgba(240,246,252,0.05); font-weight: 600;
               border-top: 2px solid {C_BORDER}; }}
.area {{ color: {C_AREA}; font-weight: 600; }}
.green {{ color: {C_GREEN}; }} .amber {{ color: {C_AMBER}; }}
.red {{ color: {C_RED}; }} .cyan {{ color: {C_CYAN}; }} .grey {{ color: {C_GREY}; }}
.blue {{ color: {C_BLUE}; }} .magenta {{ color: {C_MAGENTA}; }}
details {{ background: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 6px;
           padding: 12px 16px; margin: 12px 0; }}
details summary {{ cursor: pointer; font-weight: 600; }}
details[open] summary {{ margin-bottom: 12px; }}
.legend {{ background: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 6px;
           padding: 16px; margin: 16px 0; font-size: 12px; }}
.legend dt {{ font-weight: 600; margin-top: 8px; color: {C_FG}; }}
.legend dd {{ margin: 4px 0 0 0; color: {C_DIM}; }}
.footer {{ color: {C_DIM}; font-size: 11px; margin-top: 24px; padding-top: 12px;
           border-top: 1px solid {C_BORDER}; }}
.pressure-row {{ display: flex; justify-content: space-between; align-items: center;
                 gap: 12px; padding: 10px 14px; margin: 6px 0;
                 border-left: 4px solid {C_BORDER}; background: {C_PANEL};
                 border-radius: 0 6px 6px 0; }}
.pressure-row.high {{ border-left-color: {C_RED}; }}
.pressure-row.medium {{ border-left-color: {C_AMBER}; }}
.pressure-row.low {{ border-left-color: {C_GREY}; }}
.pressure-row .score {{ font-size: 18px; font-weight: 600; color: {C_FG}; }}
.pressure-row code {{ background: {C_BG}; padding: 2px 6px; border-radius: 4px;
                     font-size: 11px; color: {C_CYAN}; }}
.funnel {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }}
.caveat {{ font-size: 11px; color: {C_DIM}; font-style: italic; margin-top: 4px; }}
.sparkline {{ display: inline-flex; gap: 1px; height: 18px; align-items: flex-end; }}
.sparkline .bar {{ width: 6px; background: {C_BLUE}; }}
.sparkline .bar.ai {{ background: {C_MAGENTA}; }}
</style>
"""


# NOTE: paginated_search is imported from reference.py. The cursor-insertion
# bug that previously forced a local override here is now fixed at the source
# (reference.py), so every consumer — not just this script — paginates
# correctly. See tests/test_pagination.py.


# ============================================================
# Aggregation layer  (aggregate.md)
# ============================================================


def compute_hero_counts(open_prs):
    """Hero card data — 2 rows, 4 cards each."""
    h = {
        "open_total": 0,
        "non_drafts": 0,
        "drafts": 0,
        "contribs": 0,
        "collabs": 0,
        "ready": 0,
        "untriaged": 0,
        "untriaged_4w": 0,
        "qc_triaged": 0,
        "defacto": 0,
        "ai_triaged": 0,
        "bots": 0,
        "bots_dependabot": 0,
        "bots_other": 0,
        "contrib_nondraft_total": 0,
        "responded": 0,
        "waiting_ai": 0,
        "waiting_manual": 0,
    }
    for pr in open_prs:
        author = pr.get("_author")
        if is_bot(author):
            h["bots"] += 1
            if author == "dependabot" or (author and "dependabot" in author):
                h["bots_dependabot"] += 1
            else:
                h["bots_other"] += 1
            continue
        h["open_total"] += 1
        if pr["isDraft"]:
            h["drafts"] += 1
        else:
            h["non_drafts"] += 1
        if pr["_is_contrib"]:
            h["contribs"] += 1
            if not pr["isDraft"]:
                h["contrib_nondraft_total"] += 1
        if pr["_is_collab"]:
            h["collabs"] += 1
        if pr["_has_ready"]:
            h["ready"] += 1
        if pr["_is_untriaged"]:
            h["untriaged"] += 1
            if pr["_age_days"] > 28:
                h["untriaged_4w"] += 1
        if pr["_is_triaged"]:
            h["qc_triaged"] += 1
            if pr["_responded"]:
                h["responded"] += 1
        if pr["_is_engaged"] and not pr["_is_triaged"]:
            h["defacto"] += 1
        if pr["_has_ai_footer"]:
            h["ai_triaged"] += 1
        if pr.get("_waiting_ai"):
            h["waiting_ai"] += 1
        if pr.get("_waiting_manual"):
            h["waiting_manual"] += 1
    return h


def compute_health_rating(hero, recs):
    """aggregate.md#health-rating — issue-points map → label/colour."""
    pts = 0
    if hero["untriaged_4w"] > 0:
        pts += 2
    if hero["untriaged"] > 30:
        pts += 1
    if hero["ready"] >= 50:
        pts += 1
    if any(r["priority"] == "high" for r in recs):
        pts += 2
    if pts >= 4:
        return ("🔥 Action needed", C_RED)
    if pts >= 2:
        return ("⚠️ Needs attention", C_AMBER)
    return ("✅ Healthy", C_GREEN)


def compute_pressure_by_area(open_prs, area_prefix):
    """aggregate.md#pressure-score weighted sum per area."""
    scores = defaultdict(
        lambda: {
            "score": 0,
            "contribs": 0,
            # Age distribution of the area's open non-draft contributor PRs
            # (all of them) — this is what the panel displays, so the age
            # columns reflect real backlog age instead of the near-empty
            # untriaged-only counts. Each bucket tracks the ready subset too,
            # rendered as "ready/all".
            "age_4w": 0,
            "age_4w_ready": 0,
            "age_1to4w": 0,
            "age_1to4w_ready": 0,
            "age_rec": 0,
            "age_rec_ready": 0,
            # Untriaged-only age counts — drive the score and recommendations.
            "u4w": 0,
            "u14w": 0,
            "wait": 0,
            "ready": 0,
        }
    )
    for pr in open_prs:
        if not pr["_is_contrib"]:
            continue
        age = pr["_age_days"]
        areas = pr["_areas"] or ["(no area)"]
        for area in areas:
            a = scores[area]
            a["contribs"] += 1
            if not pr["isDraft"]:
                rdy = pr["_has_ready"]
                if age > 28:
                    a["age_4w"] += 1
                    a["age_4w_ready"] += rdy
                elif age > 7:
                    a["age_1to4w"] += 1
                    a["age_1to4w_ready"] += rdy
                else:
                    a["age_rec"] += 1
                    a["age_rec_ready"] += rdy
            if pr["_is_untriaged"]:
                if age > 28:
                    a["u4w"] += 1
                    a["score"] += 5
                elif age > 7:
                    a["u14w"] += 1
                    a["score"] += 3
                else:
                    a["score"] += 1
            elif pr["_is_triaged"] and not pr["_responded"] and age > 7:
                a["wait"] += 1
                a["score"] += 2
            if pr["_has_ready"]:
                a["ready"] += 1
                a["score"] += 1
    rows = [
        (area.replace(area_prefix, ""), v)
        for area, v in scores.items()
        if v["contribs"] >= 3
    ]
    rows.sort(key=lambda x: -x[1]["score"])
    return rows[:8]


def compute_recommendations(open_prs, weekly, pressure, hero, ready_trend_growth):
    """render.md#recommendation-rules — fixed table evaluated in order."""
    now = datetime.now(timezone.utc)
    untriaged_4w = [p for p in open_prs if p["_is_untriaged"] and p["_age_days"] > 28]
    untriaged_14 = [
        p for p in open_prs if p["_is_untriaged"] and 7 < p["_age_days"] <= 28
    ]
    stale_drafts = [
        p
        for p in open_prs
        if p["isDraft"]
        and p["_is_triaged"]
        and p["_triage_at"]
        and (now - p["_triage_at"]).days >= 7
        and not p["_responded"]
    ]
    responded_no_ready = [
        p for p in open_prs if p["_responded"] and not p["_has_ready"]
    ]

    recs = []
    if untriaged_4w:
        recs.append(
            {
                "priority": "high",
                "icon": "🔥",
                "title": f"Triage {len(untriaged_4w)} non-draft contributor PRs older than 4 weeks",
                "detail": "Focus on the >4w bucket — those are the ones rotting longest.",
                "action": "/pr-management-triage all PR issues",
                "count": len(untriaged_4w),
            }
        )
    elif untriaged_14:
        recs.append(
            {
                "priority": "medium",
                "icon": "👀",
                "title": f"Triage {len(untriaged_14)} non-draft PRs aged 1-4 weeks",
                "detail": "The 1-4w bucket is the queue's leading edge.",
                "action": "/pr-management-triage all PR issues",
                "count": len(untriaged_14),
            }
        )
    if stale_drafts:
        recs.append(
            {
                "priority": "medium",
                "icon": "🗑️",
                "title": f"Close {len(stale_drafts)} stale-triaged drafts (≥7d, no response)",
                "detail": "Closure path lives under the stale flow (sweep step 1a).",
                "action": "/pr-management-triage stale",
                "count": len(stale_drafts),
            }
        )
    if hero["ready"] >= 50:
        recs.append(
            {
                "priority": "high",
                "icon": "📥",
                "title": f"{hero['ready']} PRs labeled \"ready for maintainer review\"",
                "detail": "The queue is past triage — needs review attention.",
                "action": "/pr-management-code-review ready",
                "count": hero["ready"],
            }
        )
    elif 20 <= hero["ready"] < 50:
        recs.append(
            {
                "priority": "medium",
                "icon": "📥",
                "title": f"{hero['ready']} PRs in \"ready for maintainer review\" queue",
                "detail": "Same trigger family — banded by queue size.",
                "action": "/pr-management-code-review ready",
                "count": hero["ready"],
            }
        )
    if responded_no_ready:
        recs.append(
            {
                "priority": "medium",
                "icon": "🔄",
                "title": f"{len(responded_no_ready)} triaged PRs have author responses awaiting re-triage",
                "detail": "Surface as request-author-confirmation in next sweep.",
                "action": "/pr-management-triage all PR issues",
                "count": len(responded_no_ready),
            }
        )
    if pressure:
        area, v = pressure[0]
        if v["u4w"] + v["u14w"] >= 5:
            recs.append(
                {
                    "priority": "medium",
                    "icon": "📍",
                    "title": f"Area \"{area}\" has {v['contribs']} contributor PRs ({v['u4w']} untriaged >4w)",
                    "detail": "One area dominating the untriaged queue — scoped pass clears bulk.",
                    "action": f"/pr-management-triage label:area:{area}",
                    # urgency is driven by the untriaged pile (the rule's
                    # trigger), not by total contributor PRs in the area.
                    "count": v["u4w"],
                }
            )
    # Rule 8 — velocity drop
    if len(weekly) >= 2:
        last_total = weekly[-2]["merged"] + weekly[-2]["closed_not_merged"]
        cur_total = weekly[-1]["merged"] + weekly[-1]["closed_not_merged"]
        drop = last_total - cur_total
        if drop > 30:
            recs.append(
                {
                    "priority": "low",
                    "icon": "📉",
                    "title": f"PR closure velocity dropped {drop} this week",
                    "detail": "No immediate action — re-check next week.",
                    "action": "—",
                    "count": drop,
                }
            )
    # Rule 9 — ready trend growth
    if ready_trend_growth:
        top_area, growth = ready_trend_growth
        if growth >= 10:
            recs.append(
                {
                    "priority": "low",
                    "icon": "📈",
                    "title": f"Ready-for-review queue in \"{top_area}\" grew by {growth} this week",
                    "detail": "Growth concentrated in one area — focused review pass.",
                    "action": f"/pr-management-code-review label:area:{top_area}",
                    "count": growth,
                }
            )
    # Rule 10 — sweep-dominated weeks
    if len(weekly) >= 2:
        sweep_recent = sum(
            1 for w in weekly[-2:] if w["closed_after_triage"] > w["merged"]
        )
        if sweep_recent == 2:
            sweep_n = sum(w["closed_after_triage"] for w in weekly[-2:])
            merged_n = sum(w["merged"] for w in weekly[-2:])
            recs.append(
                {
                    "priority": "medium",
                    "icon": "🧹",
                    "title": f"Stale-sweep dominating closures ({sweep_n} sweep-close vs {merged_n} merged)",
                    "detail": "Too many PRs reaching the stale sweep — review earlier-stage interventions.",
                    "action": "—",
                    "count": sweep_n,
                }
            )

    # Sort: high → medium → low; within tier by count desc
    order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: (order[r["priority"]], -r["count"]))
    return recs


def _bucket_dates(weeks):
    return [(s, e) for s, e in weeks]


def compute_backlog_over_time(open_prs, closed_prs, weeks):
    """End-of-week open backlog snapshot, total and non-draft.

    Draft status is only known as of the snapshot (current isDraft for still-open
    PRs, draft-at-close for closed PRs); the non-draft series uses that as a proxy
    for historical draft state.
    """
    out = []
    for s, e in weeks:
        n = 0
        nondraft = 0
        for pr in open_prs + closed_prs:
            created = parse_iso(pr.get("createdAt"))
            if not created or created > e:
                continue
            closed_at = parse_iso(pr.get("closedAt"))
            if closed_at is None or closed_at > e:
                n += 1
                if not pr.get("isDraft"):
                    nondraft += 1
        out.append({"start": s, "end": e, "value": n, "nondraft": nondraft})
    return out


def compute_opened_by_author_class(all_prs, weeks):
    """3-line: FIRST_TIME, CONTRIBUTOR, MAINTAINER per week."""
    out = []
    for s, e in weeks:
        b = {"start": s, "end": e, "first_time": 0, "contributor": 0, "maintainer": 0}
        for pr in all_prs:
            ca = parse_iso(pr.get("createdAt"))
            if not ca or not (s <= ca < e):
                continue
            assoc = pr.get("authorAssociation", "")
            author = (pr.get("author") or {}).get("login")
            if is_bot(author):
                continue
            if assoc in COLLAB_ASSOCIATIONS:
                b["maintainer"] += 1
            elif assoc in ("FIRST_TIMER", "FIRST_TIME_CONTRIBUTOR", "NONE"):
                b["first_time"] += 1
            else:
                b["contributor"] += 1
        out.append(b)
    return out


def compute_maintainer_opened(open_prs, area_prefix):
    """Currently-open maintainer-authored PRs by author and by provider area.

    Pass only the currently-open PR set (not closed/merged): the panel reports
    the standing maintainer-authored queue, not historical throughput.
    "Maintainer-authored" = authorAssociation in COLLAB_ASSOCIATIONS (and not a
    bot). Returns two ranked lists:
      - by_author: [(login, count), ...] desc
      - by_provider: [(provider, count), ...] desc over labels starting
        "provider:" (the per-provider areas); PRs with no provider label are
        grouped under "(non-provider)".
    """
    by_author = defaultdict(int)
    by_provider = defaultdict(int)
    total = 0
    for pr in open_prs:
        if pr.get("authorAssociation", "") not in COLLAB_ASSOCIATIONS:
            continue
        author = (pr.get("author") or {}).get("login")
        if not author or is_bot(author):
            continue
        total += 1
        by_author[author] += 1
        provider_labels = [
            lbl for lbl in pr.get("_labels", []) if lbl.startswith("provider:")
        ]
        if not provider_labels:
            by_provider["(non-provider)"] += 1
        else:
            for lbl in provider_labels:
                by_provider[lbl.replace("provider:", "")] += 1
    return {
        "total": total,
        "by_author": sorted(by_author.items(), key=lambda x: -x[1])[:12],
        "by_provider": sorted(by_provider.items(), key=lambda x: -x[1])[:12],
    }


def compute_ready_queue_cumulative(open_prs, weeks):
    """Cumulative count of currently-ready PRs whose label_added_at <= week.end."""
    out = []
    for s, e in weeks:
        n = 0
        for pr in open_prs:
            if not pr["_has_ready"]:
                continue
            lab = pr.get("_label_added_at")
            if lab and lab <= e:
                n += 1
            elif not lab:
                created = parse_iso(pr.get("createdAt"))
                if created and created <= e:
                    n += 1
        out.append({"start": s, "end": e, "value": n})
    return out


def compute_triage_velocity(all_prs, weeks, ctx):
    """2-line: AI-drafted, manual — by first-triage week across BOTH channels
    (collaborator QC comments AND the pr-body fold block)."""
    out = []
    for s, e in weeks:
        b = {"start": s, "end": e, "ai": 0, "manual": 0}
        for pr in all_prs:
            events = triage_marker_events(pr, ctx)
            if not events:
                continue
            first_qc, is_ai = min(events, key=lambda ev: ev[0])
            if s <= first_qc < e:
                if is_ai:
                    b["ai"] += 1
                else:
                    b["manual"] += 1
        out.append(b)
    return out


def compute_triage_coverage_rate(all_prs, weeks):
    """% of PRs opened in window that are engaged (_is_engaged)."""
    out = []
    for s, e in weeks:
        opened = 0
        engaged = 0
        for pr in all_prs:
            ca = parse_iso(pr.get("createdAt"))
            if not ca or not (s <= ca < e):
                continue
            opened += 1
            if pr.get("_is_engaged"):
                engaged += 1
        out.append(
            {"start": s, "end": e, "opened": opened, "engaged": engaged,
             "rate": pct(engaged, opened)}
        )
    return out


def compute_opened_vs_closed(all_prs, weeks):
    """Per-week opened / closed_total / net_delta."""
    out = []
    for s, e in weeks:
        opened = 0
        closed = 0
        for pr in all_prs:
            ca = parse_iso(pr.get("createdAt"))
            if ca and s <= ca < e:
                opened += 1
            cl = parse_iso(pr.get("closedAt"))
            if cl and s <= cl < e:
                closed += 1
        out.append({"start": s, "end": e, "opened": opened, "closed": closed,
                    "net": opened - closed})
    return out


def compute_ready_trend_by_area(open_prs, weeks, pressure, area_prefix):
    """Top-5 pressure areas with ≥3 currently-ready PRs; cumulative line per area."""
    candidate_areas = [a for a, _ in pressure]
    series = {}
    for area in candidate_areas:
        full_label = f"{area_prefix}{area}"
        ready_in_area = [p for p in open_prs if p["_has_ready"] and full_label in p["_labels"]]
        if len(ready_in_area) < 3:
            continue
        per_week = []
        for s, e in weeks:
            n = 0
            for pr in ready_in_area:
                lab = pr.get("_label_added_at")
                if lab and lab <= e:
                    n += 1
                elif not lab:
                    created = parse_iso(pr.get("createdAt"))
                    if created and created <= e:
                        n += 1
            per_week.append(n)
        series[area] = per_week
        if len(series) >= 5:
            break
    # growth in last 7d for the top area
    growth_top = None
    if series:
        first_area = next(iter(series))
        cur = series[first_area][-1]
        prev = series[first_area][-2] if len(series[first_area]) >= 2 else 0
        growth_top = (first_area, cur - prev)
    return series, growth_top


def compute_triage_funnel(open_prs):
    """5 mutually-exclusive buckets — precedence per render.md."""
    funnel = {
        "ready": 0,
        "responded": 0,
        "waiting_manual": 0,
        "waiting_ai": 0,
        "untriaged": 0,
        "other": 0,
    }
    for pr in open_prs:
        if not pr["_is_contrib"]:
            continue
        if pr["isDraft"]:
            continue
        if pr["_has_ready"]:
            funnel["ready"] += 1
        elif pr["_is_triaged"] and pr["_responded"]:
            funnel["responded"] += 1
        elif pr.get("_waiting_manual"):
            funnel["waiting_manual"] += 1
        elif pr.get("_waiting_ai"):
            funnel["waiting_ai"] += 1
        elif pr["_is_untriaged"]:
            funnel["untriaged"] += 1
        else:
            funnel["other"] += 1
    return funnel


def compute_triager_activity(open_prs, closed_prs, weeks, ctx):
    """Per-maintainer per-week PR-engagement counts, AI vs manual."""
    # collab_login -> week_idx -> {ai: set(pr_num), manual: set(pr_num)}
    activity = defaultdict(
        lambda: [{"ai": set(), "manual": set()} for _ in weeks]
    )
    for pr in open_prs + closed_prs:
        pr_num = pr.get("number")
        for c in (pr.get("comments", {}) or {}).get("nodes", []) or []:
            if c.get("authorAssociation") not in COLLAB_ASSOCIATIONS:
                continue
            author = (c.get("author") or {}).get("login")
            if not author or is_bot(author):
                continue
            at = parse_iso(c.get("createdAt"))
            if not at:
                continue
            body = c.get("body") or ""
            is_ai = ctx["ai_footer"] in body
            for idx, (s, e) in enumerate(weeks):
                if s <= at < e:
                    if is_ai:
                        activity[author][idx]["ai"].add(pr_num)
                    else:
                        activity[author][idx]["manual"].add(pr_num)
                    break
        # pr-body fold channel: credit the folded triage note to its operator
        # (the `by @login` in the note header), always AI, at the fold time.
        fat = fold_triaged_at(pr)
        if fat:
            om = re.search(r"by `@([A-Za-z0-9-]+)`", pr.get("body") or "")
            operator = om.group(1) if om else None
            if operator and not is_bot(operator):
                for idx, (s, e) in enumerate(weeks):
                    if s <= fat < e:
                        activity[operator][idx]["ai"].add(pr_num)
                        break
    rows = []
    for login, per_week in activity.items():
        totals_ai = set().union(*[w["ai"] for w in per_week])
        totals_manual = set().union(*[w["manual"] for w in per_week])
        total_prs = totals_ai | totals_manual
        rows.append(
            {
                "login": login,
                "total": len(total_prs),
                "ai": len(totals_ai),
                "manual": len(totals_manual),
                "per_week": [
                    {"ai": len(w["ai"]), "manual": len(w["manual"])} for w in per_week
                ],
            }
        )
    rows.sort(key=lambda r: -r["total"])
    return rows[:15]


def _ready_age_bucket(age_days):
    """Map a PR age in days to one of the READY_AGE_BUCKETS labels."""
    if age_days <= 14:
        return "0-2w"
    if age_days <= 28:
        return "2-4w"
    if age_days <= 56:
        return "4-8w"
    if age_days <= 84:
        return "8-12w"
    return ">12w"


def _has_maintainer_discussion(pr, ctx):
    """True if a maintainer left a COMMENTED review OR a real (non-triage-marker)
    maintainer comment on the PR.

    The triage marker is excluded so the templated quality-criteria comment does
    not, on its own, count as a human "discussion" — that distinguishes
    `discussed-no-decision` from `never-reviewed`.
    """
    marker = ctx["triage_marker"]
    for c in (pr.get("comments", {}) or {}).get("nodes", []) or []:
        if c.get("authorAssociation") not in COLLAB_ASSOCIATIONS:
            continue
        login = (c.get("author") or {}).get("login")
        if is_bot(login):
            continue
        if marker in (c.get("body") or ""):
            continue
        return True
    for r in (pr.get("latestReviews", {}) or {}).get("nodes", []) or []:
        login = (r.get("author") or {}).get("login")
        if r.get("state") == "COMMENTED" and login and not is_bot(login):
            return True
    return False


def compute_ready_split(open_prs, ctx):
    """Ready-for-review queue split by why-waiting (render.md § Ready-for-review
    queue split).

    Scope: NON-maintainer ready PRs only (collaborator/maintainer-authored ready
    PRs self-manage and are excluded — their count is reported separately as
    ``excluded_maintainer``). Each ready contributor PR is classified into exactly
    one of four sub-states from ``reviewDecision`` plus maintainer engagement, and
    bucketed by age for the timeline.

    Returns a dict with per-sub-state counts, the per-bucket age timeline (one
    list per sub-state, ordered oldest→newest per READY_AGE_BUCKETS reversed at
    render time), the total scoped count, and the excluded maintainer count.
    """
    counts = {
        "never-reviewed": 0,
        "discussed-no-decision": 0,
        "changes-requested": 0,
        "approved": 0,
    }
    # bucket_label -> sub-state -> count
    timeline = {b: dict.fromkeys(counts, 0) for b in READY_AGE_BUCKETS}
    total = 0
    excluded_maintainer = 0
    for pr in open_prs:
        if not pr.get("_has_ready"):
            continue
        if pr.get("_is_collab") or is_bot(pr.get("_author")):
            excluded_maintainer += 1
            continue
        decision = pr.get("_review_decision")
        if decision == "CHANGES_REQUESTED":
            sub = "changes-requested"
        elif decision == "APPROVED":
            sub = "approved"
        elif _has_maintainer_discussion(pr, ctx):
            sub = "discussed-no-decision"
        else:
            sub = "never-reviewed"
        counts[sub] += 1
        total += 1
        bucket = _ready_age_bucket(pr.get("_age_days", 0))
        timeline[bucket][sub] += 1
    return {
        "counts": counts,
        "timeline": timeline,
        "total": total,
        "excluded_maintainer": excluded_maintainer,
    }


def _maintainer_logins(open_prs, closed_prs):
    """Derive the maintainer set from who commented as OWNER/MEMBER/COLLABORATOR
    in the fetched data (render.md: do not hardcode a committer list)."""
    maintainers = set()
    for pr in open_prs + closed_prs:
        for c in (pr.get("comments", {}) or {}).get("nodes", []) or []:
            if c.get("authorAssociation") not in COLLAB_ASSOCIATIONS:
                continue
            login = (c.get("author") or {}).get("login")
            if login and not is_bot(login):
                maintainers.add(login)
    return maintainers


def compute_attribution(open_prs, closed_prs, ctx):
    """Drafts & closes attribution by person (render.md § Drafts & closes
    attribution by person).

    Counts draft-conversions (from ``CONVERT_TO_DRAFT_EVENT`` timeline actors on
    open PRs) and closes (from ``CLOSED_EVENT`` actors on closed-unmerged PRs)
    over the cutoff window. Bot-authored and backport PRs are EXCLUDED before
    attributing. Each action is split into "triage" (actor != PR author) and
    "author self" (actor == author). Per-maintainer shares are computed over the
    maintainer set derived from the fetched comment data.

    Returns a dict keyed by action ("drafts", "closes") plus ``maintainers`` and
    ``excluded`` accounting.
    """
    maintainers = _maintainer_logins(open_prs, closed_prs)
    cutoff = ctx["cutoff"]

    def _new_action():
        return {
            "total": 0,
            "triage": 0,
            "author": 0,
            "by_person": defaultdict(int),
            "by_person_triage": defaultdict(int),
        }

    drafts = _new_action()
    closes = _new_action()
    excluded = {"bot": 0, "backport": 0}

    # Draft-conversions — CONVERT_TO_DRAFT_EVENT actors on the open-PR set.
    for pr in open_prs:
        author = pr.get("_author")
        if is_bot(author):
            excluded["bot"] += 1
            continue
        if pr.get("_is_backport"):
            excluded["backport"] += 1
            continue
        for ev in (pr.get("timelineItems", {}) or {}).get("nodes", []) or []:
            # Attribute only genuine draft-conversion events. The open-PR
            # timeline also returns LabeledEvent / ReadyForReviewEvent nodes
            # (same actor+createdAt shape), so gate strictly on __typename.
            if ev.get("__typename") != "ConvertToDraftEvent":
                continue
            actor = (ev.get("actor") or {}).get("login")
            at = parse_iso(ev.get("createdAt"))
            if not actor or not at or at < cutoff:
                continue
            drafts["total"] += 1
            if actor == author:
                drafts["author"] += 1
                drafts["by_person"][actor] += 1
            else:
                drafts["triage"] += 1
                drafts["by_person"][actor] += 1
                drafts["by_person_triage"][actor] += 1

    # Closes — CLOSED_EVENT actors on closed-unmerged PRs.
    for pr in closed_prs:
        if pr.get("merged"):
            continue
        author = pr.get("_author") or (pr.get("author") or {}).get("login")
        if is_bot(author):
            excluded["bot"] += 1
            continue
        if is_backport(pr):
            excluded["backport"] += 1
            continue
        ca = parse_iso(pr.get("closedAt"))
        if ca and ca < cutoff:
            continue
        actor = None
        for ev in (pr.get("timelineItems", {}) or {}).get("nodes", []) or []:
            a = (ev.get("actor") or {}).get("login")
            if a:
                actor = a
        if not actor:
            continue
        closes["total"] += 1
        if actor == author:
            closes["author"] += 1
            closes["by_person"][actor] += 1
        else:
            closes["triage"] += 1
            closes["by_person"][actor] += 1
            closes["by_person_triage"][actor] += 1

    def _finalise(action):
        action["by_person"] = dict(
            sorted(action["by_person"].items(), key=lambda x: -x[1])
        )
        action["by_person_triage"] = dict(
            sorted(action["by_person_triage"].items(), key=lambda x: -x[1])
        )
        return action

    return {
        "drafts": _finalise(drafts),
        "closes": _finalise(closes),
        "maintainers": sorted(maintainers),
        "excluded": excluded,
    }


def compute_table_final_state(closed_prs, area_prefix, ctx):
    """Table 1 — triaged closed PRs grouped by area, since cutoff."""
    by_area = defaultdict(
        lambda: {"triaged_total": 0, "closed": 0, "merged": 0, "responded": 0}
    )
    for pr in closed_prs:
        # Was this PR triaged?
        has_qc = False
        t_at = None
        for c in (pr.get("comments", {}) or {}).get("nodes", []) or []:
            if c.get("authorAssociation") in COLLAB_ASSOCIATIONS and ctx[
                "triage_marker"
            ] in (c.get("body") or ""):
                has_qc = True
                t_at = parse_iso(c["createdAt"])
                break
        if not has_qc:
            continue
        responded = False
        if t_at:
            for c in (pr.get("comments", {}) or {}).get("nodes", []) or []:
                ca = (c.get("author") or {}).get("login")
                pa = (pr.get("author") or {}).get("login")
                if ca and pa and ca == pa and parse_iso(c["createdAt"]) > t_at:
                    responded = True
                    break
        labels = [l["name"] for l in (pr.get("labels", {}) or {}).get("nodes", []) or []]
        areas = [l for l in labels if l.startswith(area_prefix)] or ["(no area)"]
        for area in areas:
            b = by_area[area]
            b["triaged_total"] += 1
            if pr.get("merged"):
                b["merged"] += 1
            else:
                b["closed"] += 1
            if responded:
                b["responded"] += 1
    rows = []
    for area, b in by_area.items():
        rows.append(
            {
                "area": area.replace(area_prefix, ""),
                **b,
                "pct_closed": pct(b["closed"], b["triaged_total"]),
                "pct_merged": pct(b["merged"], b["triaged_total"]),
                "pct_responded": pct(b["responded"], b["triaged_total"]),
            }
        )
    rows.sort(key=lambda r: -r["triaged_total"])
    # (no area) goes last
    rows.sort(key=lambda r: 1 if r["area"] == "(no area)" else 0)
    # TOTAL row (each PR counted once — recompute over closed_prs)
    totals = {"triaged_total": 0, "closed": 0, "merged": 0, "responded": 0}
    seen = set()
    for pr in closed_prs:
        if pr["number"] in seen:
            continue
        has_qc = False
        t_at = None
        for c in (pr.get("comments", {}) or {}).get("nodes", []) or []:
            if c.get("authorAssociation") in COLLAB_ASSOCIATIONS and ctx[
                "triage_marker"
            ] in (c.get("body") or ""):
                has_qc = True
                t_at = parse_iso(c["createdAt"])
                break
        if not has_qc:
            continue
        seen.add(pr["number"])
        totals["triaged_total"] += 1
        responded = False
        if t_at:
            for c in (pr.get("comments", {}) or {}).get("nodes", []) or []:
                ca = (c.get("author") or {}).get("login")
                pa = (pr.get("author") or {}).get("login")
                if ca and pa and ca == pa and parse_iso(c["createdAt"]) > t_at:
                    responded = True
                    break
        if pr.get("merged"):
            totals["merged"] += 1
        else:
            totals["closed"] += 1
        if responded:
            totals["responded"] += 1
    rows.append(
        {
            "area": "TOTAL",
            **totals,
            "pct_closed": pct(totals["closed"], totals["triaged_total"]),
            "pct_merged": pct(totals["merged"], totals["triaged_total"]),
            "pct_responded": pct(totals["responded"], totals["triaged_total"]),
            "_is_total": True,
        }
    )
    return rows


def compute_table_still_open(open_prs, area_prefix):
    """Table 2 — open PRs grouped by area with TOTAL row."""
    by_area = defaultdict(
        lambda: {
            "total": 0,
            "contribs": 0,
            "drafts": 0,
            "non_drafts": 0,
            "triaged": 0,
            "responded": 0,
            "ready": 0,
            "drafted_by_triager": 0,
        }
    )
    for pr in open_prs:
        if is_bot(pr.get("_author")):
            continue
        areas = pr["_areas"] or ["(no area)"]
        for area in areas:
            b = by_area[area]
            b["total"] += 1
            if pr["_is_contrib"]:
                b["contribs"] += 1
                if pr["isDraft"]:
                    b["drafts"] += 1
                    if pr["_is_triaged"]:
                        b["drafted_by_triager"] += 1
                else:
                    b["non_drafts"] += 1
                if pr["_is_triaged"]:
                    b["triaged"] += 1
                if pr["_responded"]:
                    b["responded"] += 1
                if pr["_has_ready"]:
                    b["ready"] += 1
    rows = []
    for area, b in by_area.items():
        rows.append(
            {
                "area": area.replace(area_prefix, ""),
                **b,
                "pct_contribs": pct(b["contribs"], b["total"]),
                "pct_drafts": pct(b["drafts"], b["contribs"]),
                "pct_responded": pct(b["responded"], b["triaged"]),
                "pct_ready": pct(b["ready"], b["contribs"]),
            }
        )
    rows.sort(key=lambda r: -r["total"])
    rows.sort(key=lambda r: 1 if r["area"] == "(no area)" else 0)
    # TOTAL — each PR once
    t = {"total": 0, "contribs": 0, "drafts": 0, "non_drafts": 0,
         "triaged": 0, "responded": 0, "ready": 0, "drafted_by_triager": 0}
    for pr in open_prs:
        if is_bot(pr.get("_author")):
            continue
        t["total"] += 1
        if pr["_is_contrib"]:
            t["contribs"] += 1
            if pr["isDraft"]:
                t["drafts"] += 1
                if pr["_is_triaged"]:
                    t["drafted_by_triager"] += 1
            else:
                t["non_drafts"] += 1
            if pr["_is_triaged"]:
                t["triaged"] += 1
            if pr["_responded"]:
                t["responded"] += 1
            if pr["_has_ready"]:
                t["ready"] += 1
    rows.append(
        {
            "area": "TOTAL",
            **t,
            "pct_contribs": pct(t["contribs"], t["total"]),
            "pct_drafts": pct(t["drafts"], t["contribs"]),
            "pct_responded": pct(t["responded"], t["triaged"]),
            "pct_ready": pct(t["ready"], t["contribs"]),
            "_is_total": True,
        }
    )
    return rows




# ============================================================
# Render — per panel
# ============================================================


def render_title(ctx, *, lag_warning=False, partial_fetch=False):
    out = []
    out.append(
        f'<h1>📊 {esc(ctx["repo"])} — Maintainer dashboard</h1>'
    )
    out.append(
        f'<div class="context">{ctx["now"].strftime("%A, %B %d, %Y · %H:%M UTC")} · '
        f'viewer @{esc(ctx["viewer"])} · 6-week window since {ctx["cutoff"].date()}</div>'
    )
    if partial_fetch:
        out.append(
            '<div class="warn">⚠ INCOMPLETE DATA — one or more PR pages failed '
            "to fetch (error, rate limit, or page cap reached). Counts and trends "
            "below undercount the real backlog; re-run before acting on them.</div>"
        )
    if lag_warning:
        out.append(
            '<div class="warn">⚠ Closed-PR table built from GitHub\'s '
            "free-text search of the quality-criteria marker. The index lags — "
            "older triaged+merged PRs are likely undercounted.</div>"
        )
    return "".join(out)


def render_hero_rows(hero, health):
    rating, rating_colour = health
    c1 = [
        {"big": rating, "sub": "based on triage backlog + queue size", "colour": rating_colour},
        {
            "big": str(hero["open_total"]),
            "sub": (
                f'<div>{hero["non_drafts"]} non-draft · {hero["drafts"]} draft</div>'
                f'<div>{hero["contribs"]} contributor · {hero["collabs"]} collaborator-authored</div>'
            ),
            "colour": C_CYAN,
        },
        {
            "big": str(hero["ready"]),
            "sub": f'{pct(hero["ready"], hero["contrib_nondraft_total"])}% of contributor queue',
            "colour": C_GREEN,
        },
        {
            "big": str(hero["untriaged"]),
            "sub": f'{hero["untriaged_4w"]} are &gt;4 weeks old',
            "colour": C_RED if hero["untriaged_4w"] > 0
            else (C_AMBER if hero["untriaged"] > 30 else C_GREEN),
        },
    ]
    c2 = [
        {
            "big": str(hero["qc_triaged"]),
            "sub": f'{pct(hero["qc_triaged"], hero["contrib_nondraft_total"])}% of contributor non-drafts (Quality Criteria marker)',
            "colour": C_BLUE,
        },
        {
            "big": str(hero["defacto"]),
            "sub": f'{pct(hero["defacto"], hero["contrib_nondraft_total"])}% of contributor non-drafts (engaged, no marker)',
            "colour": C_AMBER,
        },
        {
            "big": str(hero["ai_triaged"]),
            "sub": f'{pct(hero["ai_triaged"], hero["qc_triaged"])}% of Quality-Criteria-triaged',
            "colour": C_GREY,
        },
        {
            "big": str(hero["bots"]),
            "sub": f'{hero["bots_dependabot"]} dependabot · {hero["bots_other"]} other',
            "colour": C_GREY,
        },
    ]

    def card_html(c):
        return (
            f'<div class="card"><div class="big" style="color:{c["colour"]}">{c["big"]}</div>'
            f'<div class="sub">{c["sub"]}</div></div>'
        )

    return (
        '<h2>Backlog state</h2>'
        f'<div class="hero">{"".join(card_html(c) for c in c1)}</div>'
        '<h3>Triage coverage breakdown</h3>'
        f'<div class="hero">{"".join(card_html(c) for c in c2)}</div>'
    )


def render_recommendations(recs):
    if not recs:
        return (
            "<h2>What needs attention</h2>"
            f'<div class="action low"><div class="title">✨ No urgent actions detected</div>'
            f'<div class="detail">Queue is in healthy shape — periodic /pr-management-triage when convenient.</div></div>'
        )
    out = ["<h2>What needs attention</h2>"]
    for r in recs:
        code = (
            f'<code>{esc(r["action"])}</code>'
            if r["action"] and r["action"] != "—"
            else ""
        )
        out.append(
            f'<div class="action {r["priority"]}">'
            f'<div class="title">{esc(r["icon"])} {esc(r["title"])}</div>'
            f'<div class="detail">{esc(r["detail"])}</div>'
            f'{code}</div>'
        )
    return "".join(out)


def render_maintainer_opened(mo, ctx):
    """Two side-by-side tables: maintainer-opened PRs by author and by provider area."""
    total = mo.get("total", 0)
    if not total:
        return ("<h3>Maintainer-opened PRs (by author &amp; provider area)</h3>"
                '<div class="caveat">No maintainer-authored PRs in the window.</div>')

    def tbl(rows, head):
        body = "".join(
            f'<tr><td>{esc(k)}</td><td style="text-align:right">{n}</td>'
            f'<td style="text-align:right">{pct(n, total)}%</td></tr>'
            for k, n in rows
        )
        return (f'<table style="width:48%;display:inline-table;vertical-align:top;margin-right:2%">'
                f'<tr><th>{head}</th><th style="text-align:right">PRs</th>'
                f'<th style="text-align:right">%</th></tr>{body}</table>')

    return (
        "<h3>Maintainer-opened PRs — currently open (by author &amp; provider area)</h3>"
        f'<div class="caveat">{total} currently-open PRs authored by maintainers '
        "(authorAssociation OWNER/MEMBER/COLLABORATOR). Left: top authors. "
        "Right: distribution across <code>provider:*</code> areas.</div>"
        + tbl(mo["by_author"], "Maintainer (author)")
        + tbl(mo["by_provider"], "Provider area")
    )


def render_trends_over_time(*, backlog, by_author, maintainer_opened, ready_cum,
                              triage_velocity, coverage_rate, weeks, ctx):
    labels = [week_label(s) for s, _ in weeks]
    out = ["<h2>Trends over time</h2>"]

    # backlog (total + non-draft)
    out.append("<h3>Open backlog over time</h3>")
    out.append(
        svg_line_chart(
            [
                {"label": "open backlog", "values": [b["value"] for b in backlog], "colour": C_BLUE},
                {"label": "non-draft", "values": [b.get("nondraft", 0) for b in backlog], "colour": C_GREEN},
            ],
            x_labels=labels,
            y_label="open count",
        )
    )

    # by author class
    out.append("<h3>PRs opened by author class</h3>")
    out.append(
        svg_line_chart(
            [
                {"label": "FIRST_TIME", "values": [b["first_time"] for b in by_author], "colour": C_GREEN},
                {"label": "CONTRIBUTOR", "values": [b["contributor"] for b in by_author], "colour": C_BLUE},
                {"label": "MAINTAINER", "values": [b["maintainer"] for b in by_author], "colour": C_MAGENTA},
            ],
            x_labels=labels,
        )
    )

    # maintainer-opened breakdown (by author + by provider area)
    out.append(render_maintainer_opened(maintainer_opened, ctx))

    # ready queue cumulative
    out.append("<h3>Ready-for-review queue size (cumulative)</h3>")
    out.append(
        svg_line_chart(
            [{"label": "ready queue", "values": [b["value"] for b in ready_cum], "colour": C_GREEN}],
            x_labels=labels,
        )
    )

    # triage velocity
    out.append("<h3>Triage velocity (AI vs manual)</h3>")
    out.append(
        svg_line_chart(
            [
                {"label": "AI-drafted", "values": [b["ai"] for b in triage_velocity], "colour": C_MAGENTA},
                {"label": "manual QC", "values": [b["manual"] for b in triage_velocity], "colour": C_BLUE},
            ],
            x_labels=labels,
        )
    )
    out.append('<div class="caveat">comments(last:25) cap may under-count older weeks.</div>')

    # coverage rate
    out.append("<h3>Triage coverage rate by week opened (%)</h3>")
    out.append(
        svg_line_chart(
            [{"label": "%engaged", "values": [b["rate"] for b in coverage_rate], "colour": C_AMBER}],
            x_labels=labels,
            y_max=100,
        )
    )
    out.append('<div class="caveat">Same comment-cap caveat as triage velocity.</div>')
    return "".join(out)


def render_closure_velocity(weekly, weeks):
    rows = [{"merged": w["merged"], "closed": w["closed_not_merged"]} for w in weekly]
    labels = [week_label(s) for s, _ in weeks]
    total_merged = sum(r["merged"] for r in rows)
    total_closed = sum(r["closed"] for r in rows)
    total_total = total_merged + total_closed
    avg = round(total_total / len(rows), 1) if rows else 0
    peak = max((r["merged"] + r["closed"] for r in rows), default=0)
    return (
        '<h2>Closure velocity (oldest → newest)</h2>'
        + svg_stacked_horizontal_bars(
            rows,
            segment_keys=["merged", "closed"],
            segment_colours=[C_GREEN, C_GREY],
            row_labels=labels,
        )
        + f'<div class="caveat">6-week total: {total_total} · '
        f'avg {avg}/wk · peak {peak}/wk · '
        f'<span class="green">{total_merged} merged</span> + '
        f'<span class="grey">{total_closed} closed-without-merge</span></div>'
    )


def render_opened_vs_closed(buckets, weeks):
    labels = [week_label(s) for s, _ in weeks]
    chart = svg_line_chart(
        [
            {"label": "opened", "values": [b["opened"] for b in buckets], "colour": C_BLUE},
            {"label": "closed", "values": [b["closed"] for b in buckets], "colour": C_GREEN},
        ],
        x_labels=labels,
    )
    if not buckets:
        return "<h2>Opened vs closed momentum</h2>" + chart
    last = buckets[-1]
    six_open = sum(b["opened"] for b in buckets)
    six_close = sum(b["closed"] for b in buckets)
    six_net = six_open - six_close
    last_net = last["net"]
    direction_six = "backlog shrinking" if six_net < 0 else "backlog growing"
    return (
        '<h2>Opened vs closed momentum (last 6 weeks)</h2>'
        + chart
        + f'<div class="caveat">Net delta this week: '
        f'<strong>{last_net:+d}</strong> PRs ({last["opened"]} opened - {last["closed"]} closed).<br>'
        f'6-week net: <strong>{six_net:+d}</strong> ({six_open} opened - {six_close} closed) — {direction_six}.'
        "</div>"
    )


def render_ready_trend(ready_trend, weeks):
    series_data, growth = ready_trend
    labels = [week_label(s) for s, _ in weeks]
    if not series_data:
        return (
            "<h2>Ready-for-review trend by top areas</h2>"
            '<div class="caveat">No areas with ≥3 currently-ready PRs.</div>'
        )
    series = []
    for idx, (area, vals) in enumerate(series_data.items()):
        # One distinct hue per area (pressure-band colours repeat and are
        # indistinguishable when several areas share a band).
        series.append({"label": area, "values": vals,
                       "colour": AREA_PALETTE[idx % len(AREA_PALETTE)]})
    chart = svg_line_chart(series, x_labels=labels)
    growth_lines = []
    for area, vals in series_data.items():
        cur = vals[-1] if vals else 0
        prev = vals[-2] if len(vals) >= 2 else 0
        delta = cur - prev
        growth_lines.append(
            f'<div><strong class="area">{esc(area)}</strong>: {cur} ready (+{delta} in last 7d)</div>'
        )
    return (
        "<h2>Ready-for-review trend (top areas)</h2>"
        + chart
        + f'<div class="caveat">{"".join(growth_lines)}</div>'
    )


def render_closed_by_reason(weekly, weeks):
    labels = [week_label(s) for s, _ in weeks]
    rows = [
        {
            "merged": w["merged"],
            "responded": w["closed_after_responded"],
            "sweep": w["closed_after_triage"],
            "untriaged": w["closed_no_triage"],
        }
        for w in weekly
    ]
    tot_merged = sum(r["merged"] for r in rows)
    tot_resp = sum(r["responded"] for r in rows)
    tot_sweep = sum(r["sweep"] for r in rows)
    tot_untri = sum(r["untriaged"] for r in rows)
    return (
        "<h2>Closed by triage reason (last 6 weeks)</h2>"
        + svg_stacked_horizontal_bars(
            rows,
            segment_keys=["merged", "responded", "sweep", "untriaged"],
            segment_colours=[C_GREEN, C_AMBER, C_RED, C_GREY],
            row_labels=labels,
        )
        + f'<div class="caveat">6-week breakdown: '
        f'<span class="green">{tot_merged} merged</span> · '
        f'<span class="amber">{tot_resp} engaged-then-closed</span> · '
        f'<span class="red">{tot_sweep} sweep-closed</span> · '
        f'<span class="grey">{tot_untri} no-triage</span></div>'
    )


def render_pressure(pressure, area_prefix):
    if not pressure:
        return (
            "<h2>Pressure by area</h2>"
            '<div class="caveat">No areas with ≥3 contributor PRs.</div>'
        )
    out = [
        "<h2>Pressure by area</h2>",
        '<div class="caveat">Pressure score = weighted sum of urgent PR conditions per area '
        "(untriaged &gt;4w ×5, 1–4w ×3, &lt;1w ×1; triaged-waiting &gt;7d ×2; ready ×1). "
        "Age columns show the age distribution of the area's open non-draft contributor PRs "
        "as <strong>ready/all</strong> (PRs labelled ready-for-review / total in that age bucket).</div>",
    ]
    for area, v in pressure:
        band = "high" if v["score"] >= 30 else ("medium" if v["score"] >= 15 else "low")
        out.append(
            f'<div class="pressure-row {band}">'
            f'<div><strong class="area">{esc(area)}</strong> — '
            f'{v["contribs"]} contributor PRs · '
            f'<span class="red">{v["age_4w_ready"]}/{v["age_4w"]}</span> &gt;4w · '
            f'<span class="amber">{v["age_1to4w_ready"]}/{v["age_1to4w"]}</span> 1-4w · '
            f'<span class="grey">{v["age_rec_ready"]}/{v["age_rec"]}</span> recent · '
            f'<span class="green">{v["ready"]}</span> ready</div>'
            f'<div><span class="score">{v["score"]}</span> '
            f'<code>/pr-management-triage label:area:{esc(area)}</code></div>'
            "</div>"
        )
    return "".join(out)


def render_codeowners(rows, total_ready):
    if not rows:
        return (
            "<h2>Ready-for-review queue by CODEOWNER</h2>"
            '<div class="caveat">.github/CODEOWNERS not found — panel skipped per render.md.</div>'
        )
    out = [
        "<h2>Ready-for-review queue by CODEOWNER</h2>",
        '<div class="caveat">For each owner: count of currently-ready PRs touching files they own. A PR with multiple owners counts once per owner. Waiting = subset where this owner left a comment the author hasn\'t replied to. Comments capped at last:25 per PR.</div>',
        "<table>",
        '<tr><th>Owner</th><th>Ready PRs</th><th>(% of queue)</th><th>Waiting for author</th></tr>',
    ]
    for owner, ready, waiting in rows:
        ready_colour = (
            C_RED if ready >= 50 else (C_AMBER if ready >= 20 else (C_GREEN if ready >= 10 else C_GREY))
        )
        wait_html = (
            f'<span class="red">{waiting}</span>' if waiting > 0 else f'<span class="grey">0</span>'
        )
        out.append(
            f'<tr><td>@{esc(owner)}</td>'
            f'<td style="color:{ready_colour}">{ready}</td>'
            f'<td class="grey">{pct(ready, total_ready)}%</td>'
            f'<td>{wait_html}</td></tr>'
        )
    out.append("</table>")
    return "".join(out)


def render_funnel(funnel):
    cards = [
        {"big": funnel["ready"], "sub": "Ready for review", "colour": C_GREEN},
        {"big": funnel["responded"], "sub": "Responded (post-QC)", "colour": C_CYAN},
        {"big": funnel["waiting_ai"], "sub": "Waiting: AI-triage only", "colour": C_MAGENTA},
        {"big": funnel["waiting_manual"], "sub": "Waiting: author response to maintainer", "colour": C_RED},
        {"big": funnel["untriaged"], "sub": "Not yet triaged", "colour": C_BLUE},
    ]
    body = "".join(
        f'<div class="card"><div class="big" style="color:{c["colour"]}">{c["big"]}</div>'
        f'<div class="sub">{c["sub"]}</div></div>'
        for c in cards
    )
    return (
        '<h2>Triage funnel</h2>'
        f'<div class="funnel">{body}</div>'
        '<div class="caveat">The two waiting cards are mutually exclusive — a PR with both unresponded AI-drafted and manual maintainer comments counts only in "author response to maintainer". Excludes drafts and bots.</div>'
    )


def render_triager_activity(rows, weeks):
    if not rows:
        return (
            "<h2>Triager activity (6-week window)</h2>"
            '<div class="caveat">No triager activity in the last 6 weeks — quiet window or fetch shape missing comment data.</div>'
        )
    labels = [week_label(s) for s, _ in weeks]
    out = ["<h2>Triager activity (6-week window)</h2>", "<table>"]
    th_weeks = "".join(f"<th>{esc(l)}</th>" for l in labels)
    out.append(
        f"<tr><th>Triager</th><th>Total</th><th>AI</th><th>Manual</th>"
        f"{th_weeks}<th>Trend</th></tr>"
    )
    total_ai = sum(r["ai"] for r in rows)
    total_manual = sum(r["manual"] for r in rows)
    total_all = sum(r["total"] for r in rows)
    for r in rows:
        max_wk = max(((w["ai"] + w["manual"]) for w in r["per_week"]), default=1) or 1
        spark = '<span class="sparkline">' + "".join(
            (
                f'<span class="bar ai" style="height:{max(2, int(18 * w["ai"] / max_wk))}px"></span>'
                f'<span class="bar" style="height:{max(2, int(18 * w["manual"] / max_wk))}px"></span>'
            )
            for w in r["per_week"]
        ) + "</span>"
        wk_cells = "".join(
            f'<td><span class="magenta">{w["ai"]}</span>/<span class="blue">{w["manual"]}</span></td>'
            for w in r["per_week"]
        )
        out.append(
            f'<tr><td><a href="https://github.com/{esc(r["login"])}" '
            f'style="color:{C_CYAN}">@{esc(r["login"])}</a></td>'
            f'<td>{r["total"]}</td>'
            f'<td class="magenta">{r["ai"]}</td>'
            f'<td class="blue">{r["manual"]}</td>'
            f'{wk_cells}<td>{spark}</td></tr>'
        )
    out.append("</table>")
    out.append(
        f'<div class="caveat">6-week throughput: '
        f'<span class="magenta">{total_ai} AI-assisted</span> / '
        f'<span class="blue">{total_manual} manual</span> / '
        f'{total_all} total across {len(rows)} active maintainers.</div>'
    )
    return "".join(out)


def render_ready_split(split):
    """4 coloured hero cards + an age timeline line chart (x-axis oldest-LEFT).

    render.md § Ready-for-review queue split: cards in order never-reviewed (red)
    / discussed (blue) / changes-requested (amber) / approved (green); the
    timeline reverses READY_AGE_BUCKETS so the oldest bucket (>12w) is on the
    LEFT and the newest (0-2w) on the right, reading past → present.
    """
    counts = split["counts"]
    total = split["total"]
    excluded = split["excluded_maintainer"]
    if total == 0:
        return (
            "<h2>Ready-for-review queue split (by why-waiting)</h2>"
            f'<div class="caveat">No non-maintainer ready PRs to classify'
            f'{f" ({excluded} maintainer-authored ready PRs excluded)" if excluded else ""}.</div>'
        )
    cards = [
        {"big": counts["never-reviewed"], "sub": "Never reviewed", "colour": C_SPLIT_NEVER},
        {"big": counts["discussed-no-decision"], "sub": "Discussed, no decision", "colour": C_SPLIT_DISCUSSED},
        {"big": counts["changes-requested"], "sub": "Changes requested", "colour": C_SPLIT_CHANGES},
        {"big": counts["approved"], "sub": "Approved (awaiting merge)", "colour": C_SPLIT_APPROVED},
    ]
    cards_html = "".join(
        f'<div class="card"><div class="big" style="color:{c["colour"]}">{c["big"]}</div>'
        f'<div class="sub">{c["sub"]}</div></div>'
        for c in cards
    )

    # Timeline: reverse the newest→oldest buckets so oldest (>12w) is on the LEFT.
    ordered_buckets = list(reversed(READY_AGE_BUCKETS))
    timeline = split["timeline"]
    series = [
        {
            "label": "never-reviewed",
            "values": [timeline[b]["never-reviewed"] for b in ordered_buckets],
            "colour": C_SPLIT_NEVER,
        },
        {
            "label": "discussed",
            "values": [timeline[b]["discussed-no-decision"] for b in ordered_buckets],
            "colour": C_SPLIT_DISCUSSED,
        },
        {
            "label": "changes-req",
            "values": [timeline[b]["changes-requested"] for b in ordered_buckets],
            "colour": C_SPLIT_CHANGES,
        },
        {
            "label": "approved",
            "values": [timeline[b]["approved"] for b in ordered_buckets],
            "colour": C_SPLIT_APPROVED,
        },
    ]
    chart = svg_line_chart(series, x_labels=ordered_buckets, y_label="ready PRs")

    first_review_gap = counts["never-reviewed"]
    decision_gap = counts["discussed-no-decision"] + counts["approved"]
    excluded_note = (
        f" {excluded} maintainer-authored ready PRs excluded." if excluded else ""
    )
    return (
        "<h2>Ready-for-review queue split (by why-waiting)</h2>"
        f'<div class="funnel" style="grid-template-columns:repeat(4,1fr)">{cards_html}</div>'
        "<h3>Ready-for-review timeline (age, oldest → newest)</h3>"
        + chart
        + f'<div class="caveat">{total} non-maintainer ready PRs.{excluded_note} '
        f'<span style="color:{C_SPLIT_NEVER}">First-review gap</span> '
        f'(never reviewed): {first_review_gap}. '
        f'Decision/merge gap (discussed + approved): {decision_gap}. '
        "A red line climbing toward the newest (right) bucket means the ready "
        "label is applied faster than anyone reviews.</div>"
    )


def render_attribution(attribution):
    """Drafts & closes attribution table (render.md § Drafts & closes by person).

    Per action (drafts, closes): total / by-triage / by-author / each maintainer's
    share; plus a per-person closing-stats breakdown.
    """
    drafts = attribution["drafts"]
    closes = attribution["closes"]
    excluded = attribution["excluded"]
    maintainers = set(attribution["maintainers"])

    def _shares(action):
        """Per-maintainer triage share rows, sorted desc."""
        rows = []
        triage_total = action["triage"]
        for login, n in action["by_person_triage"].items():
            if login not in maintainers:
                continue
            rows.append((login, n, pct(n, triage_total)))
        return rows

    def _share_str(action):
        rows = _shares(action)
        if not rows:
            return '<span class="grey">—</span>'
        return ", ".join(
            f'@{esc(login)} {share}%' for login, _, share in rows[:5]
        )

    out = ["<h2>Drafts &amp; closes attribution by person</h2>"]
    out.append(
        '<div class="caveat">Draft-conversions from CONVERT_TO_DRAFT_EVENT actors; '
        "closes from CLOSED_EVENT actors on closed-unmerged PRs. "
        '<strong>Triage</strong> = actor &ne; PR author; '
        "<strong>author self</strong> = actor == author. "
        f'Excluded before attributing: {excluded["bot"]} bot-authored, '
        f'{excluded["backport"]} backport.</div>'
    )
    out.append("<table>")
    out.append(
        "<tr><th>Action</th><th>Total</th><th>By triage</th><th>By author</th>"
        "<th>Per-maintainer triage share</th></tr>"
    )
    for label, action in (("Drafts", drafts), ("Closes", closes)):
        out.append(
            f'<tr><td>{label}</td>'
            f'<td>{action["total"]}</td>'
            f'<td class="magenta">{action["triage"]}</td>'
            f'<td class="grey">{action["author"]}</td>'
            f'<td style="text-align:left">{_share_str(action)}</td></tr>'
        )
    out.append("</table>")

    # Per-person closing stats breakdown.
    out.append("<h3>Closing stats by person</h3>")
    if not closes["by_person"]:
        out.append('<div class="caveat">No closes attributed in the window.</div>')
    else:
        out.append("<table>")
        out.append(
            "<tr><th>Person</th><th>Closes (total)</th><th>As triage</th>"
            "<th>% of all closes</th></tr>"
        )
        for login, n in closes["by_person"].items():
            triage_n = closes["by_person_triage"].get(login, 0)
            out.append(
                f'<tr><td>@{esc(login)}</td>'
                f'<td>{n}</td>'
                f'<td class="magenta">{triage_n}</td>'
                f'<td class="grey">{pct(n, closes["total"])}%</td></tr>'
            )
        out.append("</table>")
    return "".join(out)


def render_detailed_tables(table1, table2, cutoff, repo):
    # Table 1
    t1 = [
        f"<details><summary>Triaged PRs — Final State since {cutoff.date()} ({esc(repo)})</summary><table>",
        "<tr><th>Area</th><th>Triaged Total</th><th>Closed</th><th>%Closed</th>"
        "<th>Merged</th><th>%Merged</th><th>Responded</th><th>%Responded</th></tr>",
    ]
    for r in table1:
        cls = "total" if r.get("_is_total") else ""
        pct_resp_colour = colour_for_pct(r["pct_responded"])
        t1.append(
            f'<tr class="{cls}"><td class="area">{esc(r["area"])}</td>'
            f'<td class="amber">{r["triaged_total"]}</td>'
            f'<td class="red">{r["closed"]}</td>'
            f'<td>{r["pct_closed"]}%</td>'
            f'<td class="green">{r["merged"]}</td>'
            f'<td>{r["pct_merged"]}%</td>'
            f'<td class="cyan">{r["responded"]}</td>'
            f'<td style="color:{pct_resp_colour}">{r["pct_responded"]}%</td></tr>'
        )
    t1.append("</table></details>")

    # Table 2
    t2 = [
        f"<details><summary>Triaged PRs — Still Open ({esc(repo)})</summary><table>",
        "<tr><th>Area</th><th>Total</th><th>Contrib</th><th>%Contrib</th>"
        "<th>Draft</th><th>%Draft</th><th>Non-Draft</th>"
        "<th>Triaged</th><th>Responded</th><th>%Resp</th>"
        "<th>Ready</th><th>%Ready</th><th>Drafted by triager</th></tr>",
    ]
    for r in table2:
        cls = "total" if r.get("_is_total") else ""
        pct_draft_colour = C_RED if r["pct_drafts"] > 60 else C_FG
        pct_resp_colour = colour_for_pct(r["pct_responded"])
        pct_ready_colour = colour_for_pct(r["pct_ready"])
        t2.append(
            f'<tr class="{cls}"><td class="area">{esc(r["area"])}</td>'
            f'<td class="grey">{r["total"]}</td>'
            f'<td class="cyan">{r["contribs"]}</td>'
            f'<td>{r["pct_contribs"]}%</td>'
            f'<td>{r["drafts"]}</td>'
            f'<td style="color:{pct_draft_colour}">{r["pct_drafts"]}%</td>'
            f'<td>{r["non_drafts"]}</td>'
            f'<td class="amber">{r["triaged"]}</td>'
            f'<td class="green">{r["responded"]}</td>'
            f'<td style="color:{pct_resp_colour}">{r["pct_responded"]}%</td>'
            f'<td class="green">{r["ready"]}</td>'
            f'<td style="color:{pct_ready_colour}">{r["pct_ready"]}%</td>'
            f'<td class="magenta">{r["drafted_by_triager"]}</td></tr>'
        )
    t2.append("</table></details>")
    return "".join(t1) + "".join(t2)


def render_summary(hero, recent_drafts):
    return (
        f'<div class="footer">Summary: {hero["open_total"]} open · '
        f'{hero["qc_triaged"]} triaged ({pct(hero["qc_triaged"], hero["contrib_nondraft_total"])}%) · '
        f'{hero["responded"]} responded · '
        f'{hero["ready"]} ready for review · '
        f'{recent_drafts} drafted by triager in last 7d.</div>'
    )


# ============================================================
# Dashboard composer
# ============================================================


def render_dashboard(
    ctx,
    *,
    hero,
    health,
    recs,
    weekly,
    pressure,
    ready_trend,
    codeowners_rows,
    funnel,
    backlog,
    by_author,
    maintainer_opened,
    ready_cum,
    triage_velocity,
    coverage_rate,
    opened_vs_closed,
    triager_activity,
    table_final,
    table_open,
    recent_drafts,
    ready_split,
    attribution,
    lag_warning=False,
    partial_fetch=False,
):
    sections = [
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<title>{esc(ctx['repo'])} — dashboard</title>{CSS}</head><body>",
        render_title(ctx, lag_warning=lag_warning, partial_fetch=partial_fetch),
        render_hero_rows(hero, health),
        render_recommendations(recs),
        render_trends_over_time(
            backlog=backlog,
            by_author=by_author,
            maintainer_opened=maintainer_opened,
            ready_cum=ready_cum,
            triage_velocity=triage_velocity,
            coverage_rate=coverage_rate,
            weeks=ctx["weeks"],
            ctx=ctx,
        ),
        render_attribution(attribution),
        render_closure_velocity(weekly, ctx["weeks"]),
        render_opened_vs_closed(opened_vs_closed, ctx["weeks"]),
        render_ready_trend(ready_trend, ctx["weeks"]),
        render_closed_by_reason(weekly, ctx["weeks"]),
        render_pressure(pressure, ctx["area_prefix"]),
        render_codeowners(codeowners_rows, hero["ready"]),
        render_funnel(funnel),
        render_ready_split(ready_split),
        render_triager_activity(triager_activity, ctx["weeks"]),
        render_detailed_tables(table_final, table_open, ctx["cutoff"], ctx["repo"]),
        render_summary(hero, recent_drafts),
        "</body></html>",
    ]
    return "\n".join(sections)


# ============================================================
# Gist publication (export.md — always-publish contract)
# ============================================================

SESSION_STATE_FILE = ".apache-magpie.session-state.json"


def _find_repo_root(start=None):
    """Walk up from ``start`` (default: cwd) to the nearest dir containing a
    ``.git`` entry; fall back to cwd if none is found. The session-state file
    lives at the adopter repo root per export.md."""
    cur = Path(start or Path.cwd()).resolve()
    for parent in (cur, *cur.parents):
        if (parent / ".git").exists():
            return parent
    return cur


def _session_state_path():
    return _find_repo_root() / SESSION_STATE_FILE


def read_stats_gist_id():
    """Return the stored ``stats_gist_id`` from the session-state file, or None."""
    path = _session_state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    gid = data.get("stats_gist_id")
    return gid or None


def store_stats_gist_id(gist_id):
    """Persist ``stats_gist_id`` into the session-state file (merging, not
    clobbering other keys)."""
    path = _session_state_path()
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    data["stats_gist_id"] = gist_id
    path.write_text(json.dumps(data, indent=2) + "\n")


def gist_scope_available():
    """True if `gh auth status` reports the `gist` token scope (export.md
    fallback: warn + skip publish when it is missing)."""
    r = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True
    )
    out = (r.stdout or "") + (r.stderr or "")
    return "gist" in out.lower()


def publish_gist(html_path, repo, *, gist_id=None):
    """Publish (or update) the dashboard as a SECRET gist; return the gist id.

    If ``gist_id`` is given, PATCH that gist's ``dashboard.html`` file in place
    (keeps the URL stable across runs — export.md "stable identity"). Otherwise
    create a new secret gist with ``gh gist create`` and return the new id.
    """
    html_path = Path(html_path)
    if gist_id:
        payload = json.dumps(
            {"files": {"dashboard.html": {"content": html_path.read_text()}}}
        )
        r = subprocess.run(
            ["gh", "api", "-X", "PATCH", f"gists/{gist_id}", "--input", "-"],
            input=payload,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print(f"  gist PATCH failed: {r.stderr[:200]}", file=sys.stderr)
            return None
        return gist_id
    # First run — create a new secret gist (gh gist create defaults to secret).
    r = subprocess.run(
        [
            "gh", "gist", "create", str(html_path),
            "--desc", f"{repo} — PR Backlog Dashboard ({date.today()})",
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f"  gist create failed: {r.stderr[:200]}", file=sys.stderr)
        return None
    m = re.search(r"[0-9a-f]{20,}", r.stdout)
    return m.group(0) if m else None


# ============================================================
# Main
# ============================================================


def main():
    ap = argparse.ArgumentParser(
        description="pr-management-stats full dashboard render (extends reference.py)"
    )
    ap.add_argument("--repo", required=True, help="owner/name, e.g. apache/airflow")
    ap.add_argument("--viewer", required=True, help="viewer GitHub login")
    ap.add_argument("--since", help="cutoff YYYY-MM-DD (default: 6 weeks ago)")
    ap.add_argument("--out", default="dashboard.html", help="output HTML path")
    ap.add_argument("--triage-marker", default=DEFAULT_TRIAGE_MARKER)
    ap.add_argument("--ai-footer", default=DEFAULT_AI_FOOTER)
    ap.add_argument("--ready-label", default=DEFAULT_READY_LABEL)
    ap.add_argument("--area-prefix", default=DEFAULT_AREA_PREFIX)
    ap.add_argument("--page-size", type=int, default=30)
    ap.add_argument(
        "--no-publish",
        action="store_true",
        help="write the HTML locally but skip publishing it to a gist "
        "(export.md: publishing is otherwise always-on).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="compute + render inline only; skip the gist publish (alias of "
        "--no-publish for the always-publish contract).",
    )
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    weeks = 6
    cutoff = now - timedelta(weeks=weeks)
    if args.since:
        cutoff = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    ctx = {
        "now": now,
        "cutoff": cutoff,
        "weeks": weeks_buckets(now, weeks),
        "triage_marker": args.triage_marker,
        "ai_footer": args.ai_footer,
        "ready_label": args.ready_label,
        "area_prefix": args.area_prefix,
        "repo": args.repo,
        "viewer": args.viewer,
    }

    print(f"== dashboard.py — pr-management-stats canonical render ==", file=sys.stderr)
    print(
        f"  repo={args.repo}  viewer={args.viewer}  cutoff={cutoff.date()}",
        file=sys.stderr,
    )

    # ---- Fetch (reuses reference.py primitives) ----
    # `fetch_status` collects partial-fetch signals from both paginated calls;
    # if either was cut short (error / rate-limit / max_pages) the dashboard is
    # flagged incomplete rather than silently published as if it were whole.
    fetch_status = {"partial": False}

    print("Fetching open PRs (full engagement schema) ...", file=sys.stderr)
    open_prs = paginated_search(
        OPEN_PRS_QUERY,
        f"is:pr is:open repo:{args.repo}",
        page_size=args.page_size,
        status=fetch_status,
    )
    print(f"  -> {len(open_prs)} open PRs", file=sys.stderr)
    for pr in open_prs:
        classify(pr, ctx)

    print(f"Fetching closed/merged PRs since {cutoff.date()} ...", file=sys.stderr)
    closed_prs = paginated_search(
        CLOSED_PRS_QUERY,
        f"is:pr is:closed repo:{args.repo} closed:>={cutoff.date()}",
        page_size=50,
        max_pages=20,
        status=fetch_status,
    )
    print(f"  -> {len(closed_prs)} closed PRs", file=sys.stderr)

    # Closed PRs come from the reduced CLOSED_PRS_QUERY (no engagement
    # collections). classify(partial=True) makes that contract explicit and
    # reads the heavy signals defensively; isDraft IS selected by the query.
    if closed_prs:
        print(
            f"  classifying {len(closed_prs)} closed PRs from the partial "
            "(closed-PR) schema — engagement signals limited to comments/labels",
            file=sys.stderr,
        )
    for pr in closed_prs:
        classify(pr, ctx, partial=True)

    if fetch_status["partial"]:
        print(
            "WARNING: pagination was cut short — dashboard is INCOMPLETE "
            "(partial banner added to HTML, partial=true in JSON sidecar).",
            file=sys.stderr,
        )

    print("Fetching CODEOWNERS + ready PR files ...", file=sys.stderr)
    codeowners = fetch_codeowners(args.repo)
    ready_nums = [pr["number"] for pr in open_prs if pr["_has_ready"]]
    files_per_pr = fetch_ready_pr_files(args.repo, ready_nums) if ready_nums else {}
    print(
        f"  -> CODEOWNERS={len(codeowners)} chars, ready files for {len(files_per_pr)} PRs",
        file=sys.stderr,
    )

    # ---- Aggregate ----
    print("Aggregating ...", file=sys.stderr)
    hero = compute_hero_counts(open_prs)
    weekly = compute_weekly_velocity(closed_prs, ctx["weeks"], ctx)
    pressure = compute_pressure_by_area(open_prs, args.area_prefix)
    ready_trend = compute_ready_trend_by_area(
        open_prs, ctx["weeks"], pressure, args.area_prefix
    )
    backlog = compute_backlog_over_time(open_prs, closed_prs, ctx["weeks"])
    by_author = compute_opened_by_author_class(open_prs + closed_prs, ctx["weeks"])
    maintainer_opened = compute_maintainer_opened(open_prs, args.area_prefix)
    ready_cum = compute_ready_queue_cumulative(open_prs, ctx["weeks"])
    triage_vel = compute_triage_velocity(open_prs + closed_prs, ctx["weeks"], ctx)
    coverage = compute_triage_coverage_rate(open_prs + closed_prs, ctx["weeks"])
    momentum = compute_opened_vs_closed(open_prs + closed_prs, ctx["weeks"])
    funnel = compute_triage_funnel(open_prs)
    triager_act = compute_triager_activity(
        open_prs, closed_prs, ctx["weeks"], ctx
    )
    table_final = compute_table_final_state(closed_prs, args.area_prefix, ctx)
    table_open = compute_table_still_open(open_prs, args.area_prefix)
    ready_split = compute_ready_split(open_prs, ctx)
    attribution = compute_attribution(open_prs, closed_prs, ctx)
    codeowners_rows = (
        compute_codeowners_panel(open_prs, files_per_pr, codeowners)
        if codeowners
        else []
    )
    recs = compute_recommendations(
        open_prs, weekly, pressure, hero, ready_trend[1]
    )
    health = compute_health_rating(hero, recs)

    recent_drafts = sum(
        1
        for pr in open_prs
        if pr["isDraft"]
        and pr["_is_triaged"]
        and pr["_triage_at"]
        and (now - pr["_triage_at"]).days <= 7
    )

    # ---- Render ----
    print("Rendering ...", file=sys.stderr)
    html_out = render_dashboard(
        ctx,
        hero=hero,
        health=health,
        recs=recs,
        weekly=weekly,
        pressure=pressure,
        ready_trend=ready_trend,
        codeowners_rows=codeowners_rows,
        funnel=funnel,
        backlog=backlog,
        by_author=by_author,
        maintainer_opened=maintainer_opened,
        ready_cum=ready_cum,
        triage_velocity=triage_vel,
        coverage_rate=coverage,
        opened_vs_closed=momentum,
        triager_activity=triager_act,
        table_final=table_final,
        table_open=table_open,
        recent_drafts=recent_drafts,
        ready_split=ready_split,
        attribution=attribution,
        partial_fetch=fetch_status["partial"],
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_out)

    # ---- JSON sidecar: superset of reference.py's keys ----
    # Every key reference.py emits is present here with an identically-computed
    # value; dashboard.py only ADDS keys. tests/test_json_parity.py asserts this
    # contract against a shared fixture so a refactor on either side can't drift
    # it unnoticed.
    intermediates = {
        # Keys shared with reference.py — same value on identical input.
        "fetched_at": now.isoformat(),
        "repo": args.repo,
        "viewer": args.viewer,
        "cutoff": cutoff.isoformat(),
        "open_count": len(open_prs),
        "closed_count": len(closed_prs),
        "ready_count": sum(1 for p in open_prs if p["_has_ready"]),
        "untriaged_count": sum(1 for p in open_prs if p["_is_untriaged"]),
        "untriaged_4w_count": sum(
            1 for p in open_prs if p["_is_untriaged"] and p["_age_days"] > 28
        ),
        "engaged_count": sum(1 for p in open_prs if p["_is_engaged"]),
        "ai_triaged_count": sum(1 for p in open_prs if p["_has_ai_footer"]),
        "files_per_ready_pr_count": len(files_per_pr),
        "codeowners_bytes": len(codeowners),
        # New keys (dashboard.py extras)
        "hero": hero,
        "health_rating": health[0],
        "recommendation_count": len(recs),
        "pressure_areas": [
            {"area": a, **v} for a, v in pressure
        ],
        "funnel": funnel,
        "weekly_velocity_totals": {
            "merged": sum(w["merged"] for w in weekly),
            "closed_not_merged": sum(w["closed_not_merged"] for w in weekly),
        },
        "partial": fetch_status["partial"],
    }
    side = out_path.with_suffix(".json")
    side.write_text(json.dumps(intermediates, indent=2, default=str))

    print(f"\nDashboard written to {out_path}", file=sys.stderr)
    print(f"Intermediate state written to {side}", file=sys.stderr)

    # ---- Always publish to a secret gist (export.md), unless opted out ----
    if args.no_publish or args.dry_run:
        print(
            "Publish skipped (--no-publish/--dry-run). Local HTML at "
            f"{out_path}.",
            file=sys.stderr,
        )
    elif not gist_scope_available():
        print(
            "WARNING: `gh auth status` token lacks the `gist` scope — skipping "
            f"gist publish. Open the local HTML at {out_path} instead, or run "
            "`gh auth refresh -s gist` and re-run.",
            file=sys.stderr,
        )
    else:
        gist_id = read_stats_gist_id()
        new_id = publish_gist(out_path, args.repo, gist_id=gist_id)
        if new_id:
            if new_id != gist_id:
                store_stats_gist_id(new_id)
            preview = f"https://gistpreview.github.io/?{new_id}"
            print(f"\nRendered (browser): {preview}", file=sys.stderr)
            print(f"Raw gist:           https://gist.github.com/{args.viewer}/{new_id}",
                  file=sys.stderr)
            print(preview)
        else:
            print(
                f"WARNING: gist publish failed — local HTML at {out_path}.",
                file=sys.stderr,
            )

    print(json.dumps({k: intermediates[k] for k in (
        "open_count", "closed_count", "ready_count",
        "untriaged_count", "untriaged_4w_count", "engaged_count",
        "ai_triaged_count", "health_rating", "recommendation_count",
    )}, indent=2))


if __name__ == "__main__":
    main()
