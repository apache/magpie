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
Regenerate a tracker-stats dashboard. Reads cached issues+events+PR data
from `$TRACKER_STATS_CACHE` (default `/tmp/tracker-stats-cache`) and writes
a self-contained HTML page to `$TRACKER_STATS_OUT`.

Configuration is loaded from `scripts/default-config.yaml`, optionally
overlaid by a YAML file at `$TRACKER_STATS_CONFIG` (deep-merged; the
`milestones` and `categories` lists are REPLACED entirely, not
concatenated), then overlaid by these env-var quick overrides:

    TRACKER_STATS_BUCKETS         monthly | quarterly | weekly
    TRACKER_STATS_START           "YYYY-MM" (monthly), "YYYY-Qn" (quarterly)
                                  or "YYYY-Www" (weekly, ISO week)
    TRACKER_STATS_UPSTREAM_REPO   upstream repo slug (or "" / "none" to skip PR charts)
    TRACKER_STATS_REPO            tracker repo slug (operational)
    TRACKER_STATS_OUT             output path
    TRACKER_STATS_CACHE           cache dir
    TRACKER_STATS_CONFIG          path to a YAML overlay file

Defaults match the reference `airflow-s/airflow-s` dashboard byte-for-byte.

Mean-time charts (createdAt -> PR opened, PR opened -> PR merged, PR merged
-> advisory announced) use real PR timestamps from the configured upstream
repo, not the `pr created` / `pr merged` label-add events (which were only
adopted in late 2025 and erased pre-2026 history). When `upstream_repo` is
null, those three charts are omitted and the snapshot back-fill rule is
disabled.
"""

import datetime as dt
import json
import os
import re
import statistics
import sys
from collections import defaultdict

# Make the src/ package importable when render.py is run as a standalone script.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "src"))

from security_tracker_stats_dashboard.core import (  # noqa: E402
    _minimal_yaml_load,
    build_triage_regex,
    deep_merge,
    eval_predicate,
    is_bot_body,
    iter_months,
    iter_quarters,
    iter_weeks,
    js_array,
    js_quotes,
    mean_or_none,
    milestone_x,
    month_end,
    month_label,
    month_of,
    parse_dt,
    quarter_end,
    quarter_label,
    quarter_of,
    week_end,
    week_label,
    week_of,
)

# --- YAML loader ----------------------------------------------------
# Prefer pyyaml when available (handles every edge case). When it's not
# installed, fall back to the pure-Python subset parser from core.
try:
    import yaml  # type: ignore

    def yaml_load(text):
        return yaml.safe_load(text)

except ImportError:

    def yaml_load(text):
        return _minimal_yaml_load(text)


# --- Config loading -------------------------------------------------

ROOT = os.environ.get("TRACKER_STATS_CACHE", "/tmp/tracker-stats-cache")
OUT_PATH = os.environ.get("TRACKER_STATS_OUT", "/tmp/airflow_s_monthly.html")
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(HERE, "default-config.yaml")


def load_config():
    with open(DEFAULT_CONFIG_PATH) as f:
        cfg = yaml_load(f.read()) or {}
    overlay_path = os.environ.get("TRACKER_STATS_CONFIG")
    if overlay_path and os.path.exists(overlay_path):
        with open(overlay_path) as f:
            overlay = yaml_load(f.read()) or {}
        cfg = deep_merge(cfg, overlay)
    # Env-var quick overrides.
    if os.environ.get("TRACKER_STATS_BUCKETS"):
        cfg["buckets"] = os.environ["TRACKER_STATS_BUCKETS"]
    if "TRACKER_STATS_START" in os.environ:
        v = os.environ["TRACKER_STATS_START"]
        cfg["start"] = v if v else None
    if "TRACKER_STATS_UPSTREAM_REPO" in os.environ:
        v = os.environ["TRACKER_STATS_UPSTREAM_REPO"]
        cfg["upstream_repo"] = None if v in ("", "none", "null") else v
    return cfg


CONFIG = load_config()

BUCKETS_MODE = CONFIG.get("buckets", "monthly")
if BUCKETS_MODE not in ("monthly", "quarterly", "weekly"):
    raise SystemExit(f"buckets must be 'monthly', 'quarterly' or 'weekly', got {BUCKETS_MODE!r}")

START_OVERRIDE = CONFIG.get("start")
UPSTREAM_REPO = CONFIG.get("upstream_repo")
SCOPE_LABELS = set(CONFIG.get("scope_labels") or [])
MILESTONES = CONFIG.get("milestones") or []
CATEGORIES_CFG = CONFIG.get("categories") or []
TRIAGE_KW = CONFIG.get("triage", {}).get("keywords") or []
BOT_PREFIXES = tuple(CONFIG.get("triage", {}).get("bot_prefixes") or [])
# Label identifying the "rejected without tracker" ledger issue. When
# null (or no such issue exists) the rejection stat is omitted / shows 0.
REJECTIONS_LEDGER_LABEL = CONFIG.get("rejections_ledger_label")

# Distinct category names in the order they FIRST appear in CATEGORIES_CFG
# (multiple rules can share a name to express disjoint branches of the
# same final category).
_seen = set()
CATS_DEFAULT_ORDER = []
for c in CATEGORIES_CFG:
    if c["name"] not in _seen:
        _seen.add(c["name"])
        CATS_DEFAULT_ORDER.append(c["name"])
STACK_ORDER = CONFIG.get("stack_order") or CATS_DEFAULT_ORDER
# CATS used for snapshot counting is the distinct-name set. Plotting uses
# STACK_ORDER (which may re-order them for visual layering).
CATS = list(CATS_DEFAULT_ORDER)
CAT_COLORS = {}
for c in CATEGORIES_CFG:
    CAT_COLORS.setdefault(c["name"], c.get("color", "#888888"))


# --- Cache load -----------------------------------------------------

with open(f"{ROOT}/issues.json") as f:
    all_issues = json.load(f)
with open(f"{ROOT}/roster.txt") as f:
    roster = {ln.strip() for ln in f if ln.strip()}
with open(f"{ROOT}/issue_extra.json") as f:
    issue_extra = json.load(f)


def _issue_label_names(issue):
    return {(lbl.get("name") if isinstance(lbl, dict) else lbl) for lbl in (issue.get("labels") or [])}


# Partition out the "rejected without tracker" ledger issue(s). The ledger
# is NOT a security tracker (it carries the rejections-ledger label and not
# the security-marker label), so it must be excluded from every normal
# tracker classification / count / median below. We keep the full list
# (`all_issues`) only for the rejection-comment parse; `issues` is the
# tracker-only list every downstream loop iterates.
if REJECTIONS_LEDGER_LABEL:
    ledger_issues = [i for i in all_issues if REJECTIONS_LEDGER_LABEL in _issue_label_names(i)]
    issues = [i for i in all_issues if REJECTIONS_LEDGER_LABEL not in _issue_label_names(i)]
else:
    ledger_issues = []
    issues = list(all_issues)

prs_cache = {}
if UPSTREAM_REPO:
    prs_path = f"{ROOT}/prs.json"
    if os.path.exists(prs_path):
        with open(prs_path) as f:
            prs_cache = json.load(f)

NOW = dt.datetime.now(dt.timezone.utc)

if UPSTREAM_REPO:
    # Match the original literal in the body-parse regex so an upstream
    # of `apache/airflow` still matches the historical pre-existing
    # `apache/airflow#NNN` references byte-for-byte.
    repo_re = re.escape(UPSTREAM_REPO)
    PR_PAT = re.compile(rf"{repo_re}#(\d+)|https://github\.com/{repo_re}/pull/(\d+)", re.I)
else:
    PR_PAT = None


if BUCKETS_MODE == "monthly":
    bucket_of = month_of
    bucket_label = month_label
    bucket_end = month_end
    bucket_iter = iter_months
elif BUCKETS_MODE == "weekly":
    bucket_of = week_of
    bucket_label = week_label
    bucket_end = week_end
    bucket_iter = iter_weeks
else:
    bucket_of = quarter_of
    bucket_label = quarter_label
    bucket_end = quarter_end
    bucket_iter = iter_quarters


# --- index issues + buckets ----------------------------------------

issues_by_n = {i["number"]: i for i in issues}
earliest = min(parse_dt(i["createdAt"]) for i in issues)

if START_OVERRIDE:
    if BUCKETS_MODE == "monthly":
        y0, m0 = (int(x) for x in START_OVERRIDE.split("-"))
        start_key = (y0, m0)
    elif BUCKETS_MODE == "weekly":
        y_part, w_part = START_OVERRIDE.split("-W")
        start_key = (int(y_part), int(w_part))
    else:
        y_part, q_part = START_OVERRIDE.split("-Q")
        start_key = (int(y_part), int(q_part))
else:
    start_key = bucket_of(earliest)

end_key = bucket_of(NOW)
buckets = list(bucket_iter(start_key[0], start_key[1], end_key[0], end_key[1]))
bucket_labels = [bucket_label(*b) for b in buckets]
n_buckets = len(buckets)

print(f"earliest createdAt: {earliest.isoformat()} -> starts at {bucket_label(*start_key)}")
print(f"now: {NOW.isoformat()} -> ends at {bucket_label(*end_key)}")
print(f"buckets in range ({BUCKETS_MODE}): {n_buckets}")


# --- rejected-without-tracker ledger -------------------------------
#
# The skill records each report it rejects *without* creating a tracker
# as a comment on a dedicated ledger issue (labelled
# REJECTIONS_LEDGER_LABEL). Each rejection comment carries a
# machine-parseable block:
#
#     <!-- rejection v1 -->
#     date: YYYY-MM-DD
#     reporter: <email/name>
#     canned: <slug>
#     thread: <url-or-threadid>
#     summary: <one line>
#
# A one-time historical backfill is a single comment of the form:
#
#     <!-- rejection-backfill v1 count: N -->
#
# Dated rejections are bucketed by their `date:` into the same monthly /
# quarterly axis as the trackers. The backfill count is undated, so we
# keep it as a separate "historical (pre-ledger)" headline number rather
# than smearing it across buckets — that keeps the per-bucket series
# faithful (only real dated rejections appear in it) while still
# surfacing the historical lump in the summary / HTML header.
REJECTION_MARKER = "<!-- rejection v1 -->"
REJECTION_BACKFILL_RE = re.compile(r"<!--\s*rejection-backfill\s+v1\s+count:\s*(\d+)\s*-->", re.I)
REJECTION_DATE_RE = re.compile(r"^\s*date:\s*(\d{4})-(\d{2})-(\d{2})\s*$", re.M)

rejections_by_b = defaultdict(int)  # bucket label -> dated rejection count
rejections_dated = []  # every dated rejection datetime (in + out of range)
rejections_dated_total = 0
rejections_backfill_total = 0

for li in ledger_issues:
    for c in li.get("comments") or []:
        body = c.get("body") or ""
        # Historical backfill marker (undated lump).
        for m in REJECTION_BACKFILL_RE.finditer(body):
            try:
                rejections_backfill_total += int(m.group(1))
            except ValueError:
                continue
        # Per-entry rejection markers. A single comment may in principle
        # carry more than one block; count each marker that is followed
        # by a parseable date line.
        if REJECTION_MARKER not in body:
            continue
        # Split on the marker so a malformed block can't swallow the
        # date of the next one. The text before the first marker is
        # discarded (it belongs to no rejection block).
        for chunk in body.split(REJECTION_MARKER)[1:]:
            dm = REJECTION_DATE_RE.search(chunk)
            if not dm:
                # No / malformed date line — skip this entry defensively.
                continue
            try:
                d = dt.datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)), tzinfo=dt.timezone.utc)
            except ValueError:
                continue
            rejections_dated.append(d)
            cb = bucket_of(d)
            if cb < buckets[0] or cb > buckets[-1]:
                # Dated outside the chart range — still count in the
                # headline total, just not in any visible bucket.
                rejections_dated_total += 1
                continue
            rejections_by_b[bucket_label(*cb)] += 1
            rejections_dated_total += 1

rejected_series = [rejections_by_b.get(bucket_label(*b), 0) for b in buckets]
rejections_total = rejections_dated_total + rejections_backfill_total

# Per-issue events
events_by_n = {}
for n in issues_by_n:
    p = f"{ROOT}/events/{n}.json"
    if os.path.exists(p) and os.path.getsize(p) > 0:
        with open(p) as f:
            events_by_n[n] = json.load(f)
    else:
        events_by_n[n] = []


# --- tracker -> linked PR list (from body parse + closedBy) --------


def extract_prs_for_issue(n):
    if not UPSTREAM_REPO:
        return set()
    v = issue_extra.get(str(n)) or {}
    nums = set()
    for ref in v.get("closedByPullRequestsReferences") or []:
        if ref.get("repository", {}).get("nameWithOwner") == UPSTREAM_REPO:
            nums.add(ref["number"])
    body = v.get("body") or ""
    if PR_PAT is not None:
        for m in PR_PAT.findall(body):
            x = m[0] or m[1]
            if x:
                nums.add(int(x))
    return nums


issue_prs = {n: extract_prs_for_issue(n) for n in issues_by_n}


def pr_meta(num):
    """Return dict(createdAt=dt, mergedAt=dt|None, state=str) or None."""
    v = prs_cache.get(str(num))
    if not v or "error" in v:
        return None
    return {
        "createdAt": parse_dt(v.get("createdAt")),
        "mergedAt": parse_dt(v.get("mergedAt")),
        "state": v.get("state"),
    }


def tracker_pr_signals(n):
    earliest_created = None
    earliest_created_pr = None
    earliest_merged_ts = None
    earliest_merged_pr = None
    for prn in issue_prs.get(n, []):
        meta = pr_meta(prn)
        if meta is None:
            continue
        c = meta["createdAt"]
        if c is not None and (earliest_created is None or c < earliest_created):
            earliest_created = c
            earliest_created_pr = prn
        mt = meta["mergedAt"]
        if mt is not None and (earliest_merged_ts is None or mt < earliest_merged_ts):
            earliest_merged_ts = mt
            earliest_merged_pr = prn
    return {
        "first_pr_created": earliest_created,
        "first_pr_created_num": earliest_created_pr,
        "first_pr_merged": earliest_merged_ts,
        "first_pr_merged_num": earliest_merged_pr,
    }


tracker_signals = {n: tracker_pr_signals(n) for n in issues_by_n}


# --- label timeline replay ------------------------------------------


def labels_open_at(issue, ts):
    n = issue["number"]
    created = parse_dt(issue["createdAt"])
    if ts < created:
        return None, None
    labels = set()
    is_open = True
    for e in events_by_n.get(n, []):
        et = parse_dt(e["created_at"])
        if et > ts:
            break
        if e["event"] == "labeled" and e.get("label"):
            labels.add(e["label"])
        elif e["event"] == "unlabeled" and e.get("label"):
            labels.discard(e["label"])
        elif e["event"] == "closed":
            is_open = False
        elif e["event"] == "reopened":
            is_open = True
    # The issue-events API can omit the 'closed' event for some (often
    # older) issues, which would leave is_open stuck True and miscount a
    # closed issue as open. Trust the authoritative closedAt from the
    # issue payload as a backstop (the cum_closed series already does).
    closed_at = parse_dt(issue.get("closedAt"))
    if issue.get("state") == "CLOSED" and closed_at and closed_at <= ts:
        is_open = False
    return labels, is_open


def classify_per_config(labels, is_open, ts, n):
    issue = issues_by_n[n]
    state_reason = issue.get("stateReason")
    sig = tracker_signals.get(n, {})
    fm = sig.get("first_pr_merged")
    pr_merged_by_snapshot = bool(UPSTREAM_REPO and fm is not None and fm <= ts)
    ctx = {
        "labels": labels,
        "is_open": is_open,
        "state_reason": state_reason,
        "pr_merged_by_snapshot": pr_merged_by_snapshot,
        "scope_labels": SCOPE_LABELS,
    }
    for cat in CATEGORIES_CFG:
        if eval_predicate(cat["predicate"], ctx):
            return cat["name"]
    return None


# --- snapshot counts ------------------------------------------------

counts = {cat: [0] * n_buckets for cat in CATS}
backfill_trackers = set()

for bi, b in enumerate(buckets):
    be = bucket_end(*b)
    ts = NOW if be > NOW else be
    for i in issues:
        labels, is_open = labels_open_at(i, ts)
        if labels is None:
            continue
        cat = classify_per_config(labels, is_open, ts, i["number"])
        if cat is None:
            continue
        counts[cat][bi] += 1

        if cat == "open_pr_merged" and is_open and "pr merged" not in labels:
            backfill_trackers.add(i["number"])

# --- cumulative opened / closed ------------------------------------

cum_opened = [0] * n_buckets
cum_closed = [0] * n_buckets
for bi, b in enumerate(buckets):
    be = bucket_end(*b)
    ts = NOW if be > NOW else be
    op = 0
    cl = 0
    for i in issues:
        ca = parse_dt(i["createdAt"])
        if ca and ca <= ts:
            op += 1
        cz = parse_dt(i.get("closedAt"))
        if cz and cz <= ts:
            cl += 1
    cum_opened[bi] = op
    cum_closed[bi] = cl

# --- cumulative rejected + reported (opened + rejected) ------------
# Mirror the cumulative-opened computation exactly: at each bucket end,
# count every rejection dated on or before it (so rejections that predate
# the chart window are baselined in, just as pre-window trackers are in
# cum_opened). rejections_dated / rejections_backfill_total come from the
# ledger parse above; both are empty/0 when the stat is disabled, so
# cum_reported degrades to exactly cum_opened. Any legacy undated backfill
# lump still seeds a flat baseline. "reported" = trackers opened + rejected.
cum_rejected = []
for b in buckets:
    be = bucket_end(*b)
    ts = NOW if be > NOW else be
    cum_rejected.append(rejections_backfill_total + sum(1 for rd in rejections_dated if rd <= ts))
cum_reported = [o + r for o, r in zip(cum_opened, cum_rejected)]

# --- Opened-in-bucket vs untriaged-at-bucket-end ------------------

opened_in_b = [0] * n_buckets
untriaged_at_bend = counts.get("open_untriaged", [0] * n_buckets)

for i in issues:
    ca = parse_dt(i["createdAt"])
    if ca is None:
        continue
    cb = bucket_of(ca)
    if cb < buckets[0] or cb > buckets[-1]:
        continue
    bi = buckets.index(cb)
    opened_in_b[bi] += 1

# Per-bucket reported = trackers opened in the bucket + reports rejected in
# the same bucket (rejected_series). Equals opened_in_b when the rejections
# stat is disabled, so the trace is only drawn when the stat is active.
reported_in_b = [o + r for o, r in zip(opened_in_b, rejected_series)]

# --- triage / response ---------------------------------------------

TRIAGE_RE = build_triage_regex(TRIAGE_KW)


triage_hours_by_b = defaultdict(list)
resp_hours_by_b = defaultdict(list)
n_fallback_triage = 0
n_no_triage = 0
all_triage_hours = []

for i in issues:
    created = parse_dt(i["createdAt"])
    blbl = bucket_label(*bucket_of(created))
    comments = i.get("comments", []) or []

    first_roster = None
    first_roster_keyword = None
    for c in comments:
        author = (c.get("author") or {}).get("login")
        if not author or author not in roster:
            continue
        if is_bot_body(c.get("body") or "", BOT_PREFIXES):
            continue
        ct = parse_dt(c["createdAt"])
        if first_roster is None:
            first_roster = ct
        if first_roster_keyword is None and TRIAGE_RE is not None and TRIAGE_RE.search(c.get("body") or ""):
            first_roster_keyword = ct
        if first_roster is not None and first_roster_keyword is not None:
            break

    if first_roster is not None:
        hours = (first_roster - created).total_seconds() / 3600
        resp_hours_by_b[blbl].append(hours)

    triage_ts = first_roster_keyword if first_roster_keyword is not None else first_roster
    if triage_ts is None:
        n_no_triage += 1
        continue
    if first_roster_keyword is None:
        n_fallback_triage += 1
    hours = (triage_ts - created).total_seconds() / 3600
    triage_hours_by_b[blbl].append(hours)
    all_triage_hours.append(hours)


def per_b_series(by_b):
    ys = []
    ns = []
    for b in buckets:
        lbl = bucket_label(*b)
        xs = by_b.get(lbl, [])
        ys.append(mean_or_none(xs))
        ns.append(len(xs))
    return ys, ns


triage_ys, triage_ns = per_b_series(triage_hours_by_b)
resp_ys, resp_ns = per_b_series(resp_hours_by_b)

triage_median = round(statistics.median(all_triage_hours), 2) if all_triage_hours else None
triage_mean = round(statistics.mean(all_triage_hours), 2) if all_triage_hours else None
triage_n = len(all_triage_hours)


# --- PR-driven mean-time metrics -----------------------------------

prc_by_b = defaultdict(list)
prm_by_b = defaultdict(list)
rel_by_b = defaultdict(list)


def first_label_time(n, label):
    for e in events_by_n.get(n, []):
        if e["event"] == "labeled" and e.get("label") == label:
            return parse_dt(e["created_at"])
    return None


if UPSTREAM_REPO:
    for i in issues:
        n = i["number"]
        created = parse_dt(i["createdAt"])
        sig = tracker_signals.get(n, {})

        first_pr_c = sig.get("first_pr_created")
        first_pr_m = sig.get("first_pr_merged")

        if first_pr_c and created and first_pr_c >= created:
            days = (first_pr_c - created).total_seconds() / 86400
            prc_by_b[bucket_label(*bucket_of(created))].append(days)

        if first_pr_m is not None:
            prn = sig.get("first_pr_merged_num")
            meta = pr_meta(prn) if prn else None
            if meta and meta["createdAt"] and meta["mergedAt"] and meta["mergedAt"] >= meta["createdAt"]:
                days = (meta["mergedAt"] - meta["createdAt"]).total_seconds() / 86400
                prm_by_b[bucket_label(*bucket_of(meta["createdAt"]))].append(days)

        if first_pr_m is not None:
            announced = first_label_time(n, "announced - emails sent") or first_label_time(n, "announced")
            rel_ts = announced
            if rel_ts is None:
                ca = parse_dt(i.get("closedAt"))
                state_reason = i.get("stateReason")
                cur_labels = {lb["name"] for lb in i.get("labels", [])}
                is_closed_completed = i.get("state") == "CLOSED" and state_reason == "COMPLETED"
                has_cve = "cve allocated" in cur_labels
                if ca and is_closed_completed and has_cve:
                    rel_ts = ca
            if rel_ts is not None and rel_ts > first_pr_m:
                days = (rel_ts - first_pr_m).total_seconds() / 86400
                rel_by_b[bucket_label(*bucket_of(first_pr_m))].append(days)


prc_ys, prc_ns = per_b_series(prc_by_b)
prm_ys, prm_ns = per_b_series(prm_by_b)
rel_ys, rel_ns = per_b_series(rel_by_b)


def n_buckets_with_data(by_b):
    return sum(1 for k, xs in by_b.items() if xs)


def overall_median(by_b):
    flat = [x for xs in by_b.values() for x in xs]
    return round(statistics.median(flat), 2) if flat else None


def overall_n(by_b):
    return sum(len(xs) for xs in by_b.values())


# --- KPIs ----------------------------------------------------------

total = len(issues)
open_now = sum(1 for i in issues if i.get("state") == "OPEN")
closed_now = total - open_now


def latest(cat):
    return counts[cat][-1] if cat in counts else 0


print(f"total trackers: {total}")
print(f"open: {open_now}, closed: {closed_now}")
print(f"fixed_released (latest bucket): {latest('fixed_released')}")
print(
    f"open_untriaged: {latest('open_untriaged')}, open_triaged: {latest('open_triaged')}, "
    f"open_pr_merged: {latest('open_pr_merged')}, closed_other: {latest('closed_other')}"
)
print(
    f"triage median {triage_median}h, mean {triage_mean}h, n={triage_n} "
    f"(fallback={n_fallback_triage}, none={n_no_triage})"
)
if REJECTIONS_LEDGER_LABEL:
    print(
        f"rejected without tracker: {rejections_dated_total} dated + "
        f"{rejections_backfill_total} historical = {rejections_total} "
        f"(ledger issues: {len(ledger_issues)})"
    )

if UPSTREAM_REPO:
    print()
    print("PR-driven mean-time series:")
    for name, by_b in [
        ("c_prc", prc_by_b),
        ("c_prm", prm_by_b),
        ("c_rel", rel_by_b),
    ]:
        print(
            f"  {name}: n={overall_n(by_b)} median={overall_median(by_b)} "
            f"buckets_with_data={n_buckets_with_data(by_b)}"
        )

print()
print(
    f"open_pr_merged back-fill: {len(backfill_trackers)} trackers were re-classified "
    f"from open_triaged -> open_pr_merged in at least one historical bucket "
    f"because of the PR-merge-date rule"
)
print()
print(
    f"Latest bucket ({bucket_labels[-1]}) opened-vs-untriaged: "
    f"opened_in_b={opened_in_b[-1]}, untriaged_at_bend={untriaged_at_bend[-1]}"
)


# --- Render HTML ---------------------------------------------------

# Title prefix differs between bucket modes for clarity.
bucket_word = {"monthly": "month", "weekly": "week"}.get(BUCKETS_MODE, "quarter")

# Build stacked-band traces in STACK_ORDER. With the default config that
# resolves to `fixed_released, open_pr_merged, open_triaged,
# open_untriaged, closed_other` — matching the reference dashboard.
stacked_traces = []
for cat in STACK_ORDER:
    if cat not in counts:
        continue
    color = CAT_COLORS.get(cat, "#888888")
    ys = js_array(counts[cat])
    stacked_traces.append(
        f"  {{x: buckets, y: {ys},  name: '{cat}',  stackgroup: 'one', "
        f"type: 'scatter', mode: 'lines', line: {{color: '{color}', width: 0}}, "
        f"fillcolor: '{color}', hoveron: 'points+fills'}}"
    )
stacked_block = ",\n".join(stacked_traces)

# Milestone shapes + annotations (multi-milestone capable).
ms_shapes = []
ms_annots = []
for ms in MILESTONES:
    ms_date = ms.get("date")
    ms_label = ms.get("label") or "milestone"
    if not ms_date:
        continue
    x_val = milestone_x(str(ms_date), BUCKETS_MODE)
    ms_shapes.append(
        "{type: 'line', xref: 'x', yref: 'paper', x0: '"
        + x_val
        + "', x1: '"
        + x_val
        + "', y0: 0, y1: 1, line: {color: '#888', width: 1.5, dash: 'dash'}}"
    )
    ms_annots.append(
        "{xref: 'x', yref: 'paper', x: '"
        + x_val
        + "', y: 1.04, xanchor: 'left', text: '↓ "
        + ms_label
        + " ("
        + str(ms_date)
        + ")', "
        + "showarrow: false, font: {size: 11, color: '#666'}}"
    )
shapes_js = "[" + ", ".join(ms_shapes) + "]"
annots_js = "[" + ", ".join(ms_annots) + "]"


# Build the optional PR-charts HTML and JS sections.
if UPSTREAM_REPO:
    pr_cards_html = (
        '<div class="card"><div id="c_prc"></div></div>\n'
        '<div class="card"><div id="c_prm"></div></div>\n'
        '<div class="card"><div id="c_rel"></div></div>\n'
    )
    pr_charts_js = (
        f"meanChart('c_prc',    'Mean time createdAt → PR opened (days)',  "
        f"{js_array(prc_ys)}, {js_array(prc_ns)}, 'd', '#16a085');\n"
        f"meanChart('c_prm',    'Mean time PR-open → PR-merged (days)',    "
        f"{js_array(prm_ys)}, {js_array(prm_ns)}, 'd', '#2980b9');\n"
        f"meanChart('c_rel',    'Mean time PR-merged → advisory announced (days)', "
        f"{js_array(rel_ys)}, {js_array(rel_ns)}, 'd', '#d35400');"
    )
else:
    pr_cards_html = ""
    pr_charts_js = ""


# Build the optional "rejected (no tracker)" header banner, chart card,
# and JS. Omitted entirely when the rejections-ledger stat is disabled
# (null label) or there is no ledger issue and nothing was parsed.
if REJECTIONS_LEDGER_LABEL and (rejections_total or ledger_issues):
    rej_header_html = (
        '<div class="banner">Reports rejected without a tracker: '
        f"<strong>{rejections_total}</strong> "
        f"({rejections_dated_total} dated + {rejections_backfill_total} historical)</div>\n"
    )
    rej_cards_html = '<div class="card full"><div id="c_rejected"></div></div>\n'
    rej_chart_js = (
        f"Plotly.newPlot('c_rejected', [\n"
        f"  {{x: buckets, y: {js_array(rejected_series)}, "
        f"name: 'rejected (no tracker)', type: 'scatter', "
        f"mode: 'lines+markers', connectgaps: true, line: {{color: '#7f8c8d'}}, "
        f"fill: 'tozeroy'}}\n"
        f"], {{\n"
        f"  ...MILESTONES_LAYOUT,\n"
        f"  title: 'Reports rejected without a tracker (per {bucket_word}, dated; "
        f"{rejections_backfill_total} historical pre-ledger not shown)',\n"
        f"  yaxis: {{title: 'count', rangemode: 'tozero'}},\n"
        f"  legend: {{orientation: 'h'}}\n"
        f"}});"
    )
else:
    rej_header_html = ""
    rej_cards_html = ""
    rej_chart_js = ""

# Extra cumulative traces (rejected + reported) appended to the c_cum
# chart. Only emitted when the rejections stat is active; otherwise an
# empty string leaves the cumulative chart with its original two lines
# for projects without a ledger. Plain single-brace JS — inserted
# verbatim into the HTML f-string via {cum_rej_traces}.
if REJECTIONS_LEDGER_LABEL and (rejections_total or ledger_issues):
    cum_rej_traces = (
        ",\n  {x: buckets, y: "
        + js_array(cum_rejected)
        + ", name: 'cumulative rejected (no tracker)', type: 'scatter', "
        "mode: 'lines+markers', connectgaps: true, "
        "line: {color: '#7f8c8d', dash: 'dot'}},\n"
        "  {x: buckets, y: "
        + js_array(cum_reported)
        + ", name: 'reported (opened + rejected)', type: 'scatter', "
        "mode: 'lines+markers', connectgaps: true, "
        "line: {color: '#9467bd', width: 3}}"
    )
else:
    cum_rej_traces = ""

# Extra "reported" trace (opened + rejected per bucket) appended to the
# opened-vs-untriaged chart. Same activation rule as cum_rej_traces so it
# is omitted (and the chart keeps its two original lines) when no ledger.
if REJECTIONS_LEDGER_LABEL and (rejections_total or ledger_issues):
    rep_ou_trace = (
        ",\n  {x: buckets, y: "
        + js_array(reported_in_b)
        + ", name: 'reported in "
        + bucket_word
        + " (opened + rejected)', "
        "type: 'scatter', mode: 'lines+markers', connectgaps: true, "
        "line: {color: '#9467bd', width: 3}}"
    )
else:
    rep_ou_trace = ""


HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>tracker {bucket_word}ly statistics</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0 auto; padding: 16px; color: #222; max-width: 1400px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.card {{ border: 1px solid #e0e0e0; border-radius: 8px; padding: 8px; background: #fafafa; }}
.card.full {{ grid-column: 1 / -1; }}
.banner {{ border: 1px solid #e0e0e0; border-radius: 8px; padding: 10px 14px; background: #f4f6f6; margin-bottom: 16px; color: #444; }}
</style>
</head>
<body>

{rej_header_html}
<div class="grid">

<div class="card full"><div id="c_states"></div></div>
<div class="card full"><div id="c_open_vs_untriaged"></div></div>
<div class="card full"><div id="c_cum"></div></div>
{rej_cards_html}<div class="card"><div id="c_triage"></div></div>
<div class="card"><div id="c_resp"></div></div>
{pr_cards_html}
</div>

<script>
const buckets = {js_quotes(bucket_labels)};

function lineOpts() {{ return {{ type: 'scatter', mode: 'lines+markers', connectgaps: true }}; }}

// Milestone markers (config-driven).
const milestoneShapes = {shapes_js};
const milestoneAnnotations = {annots_js};
const MILESTONES_LAYOUT = {{shapes: milestoneShapes, annotations: milestoneAnnotations}};

// Stacked-line lifecycle bands
Plotly.newPlot('c_states', [
{stacked_block}
], {{
  ...MILESTONES_LAYOUT,
  title: 'Issue lifecycle bands (stacked, end-of-{bucket_word} snapshots)',
  yaxis: {{title: 'tracker count'}},
  legend: {{orientation: 'h'}},
  hovermode: 'x unified'
}});

// Opened-in-bucket vs untriaged-at-bucket-end
Plotly.newPlot('c_open_vs_untriaged', [
  {{x: buckets, y: {js_array(opened_in_b)},        name: 'opened in {bucket_word}',
    type: 'scatter', mode: 'lines+markers', connectgaps: true,
    line: {{color: '#1f77b4'}}}},
  {{x: buckets, y: {js_array(untriaged_at_bend)},  name: 'untriaged at {bucket_word}-end',
    type: 'scatter', mode: 'lines+markers', connectgaps: true,
    line: {{color: '#d62728'}}}}{rep_ou_trace}
], {{
  ...MILESTONES_LAYOUT,
  title: 'Reported vs. opened vs. untriaged backlog (per {bucket_word})',
  yaxis: {{title: 'count'}},
  legend: {{orientation: 'h'}}
}});

Plotly.newPlot('c_cum', [
  {{x: buckets, y: {js_array(cum_opened)}, name: 'cumulative opened',
    type: 'scatter', mode: 'lines+markers', connectgaps: true,
    line: {{color: '#1f77b4'}}, fill: 'tozeroy'}},
  {{x: buckets, y: {js_array(cum_closed)}, name: 'cumulative closed',
    type: 'scatter', mode: 'lines+markers', connectgaps: true,
    line: {{color: '#2ca02c'}}, fill: 'tozeroy'}}{cum_rej_traces}
], {{
  ...MILESTONES_LAYOUT,
  title: 'Cumulative reported (opened + rejected) vs. opened vs. closed (gap = open backlog)',
  yaxis: {{title: 'count'}},
  legend: {{orientation: 'h'}}
}});

{rej_chart_js}

function meanChart(divId, title, ys, ns, unit, color) {{
  Plotly.newPlot(divId, [{{
    x: buckets, y: ys,
    type: 'scatter', mode: 'lines+markers', connectgaps: true,
    text: ns.map(n => 'n=' + n),
    hovertemplate: '%{{x}}<br>mean: %{{y:.2f}} ' + unit + '<br>%{{text}}<extra></extra>',
    line: {{color: color}}
  }}], {{
    ...MILESTONES_LAYOUT,
    title: title,
    yaxis: {{title: 'mean ' + unit, rangemode: 'tozero'}}
  }});
}}

meanChart('c_triage', 'Mean time to triage (hours)',          {js_array(triage_ys)}, {js_array(triage_ns)}, 'h', '#c0392b');
meanChart('c_resp',   'Mean time to first response (hours)',  {js_array(resp_ys)}, {js_array(resp_ns)}, 'h', '#8e44ad');
{pr_charts_js}
</script>
</body>
</html>
"""

with open(OUT_PATH, "w") as f:
    f.write(HTML)

print(f"\nWrote {OUT_PATH} ({len(HTML)} bytes)")
