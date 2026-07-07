<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [security-tracker-stats-dashboard](#security-tracker-stats-dashboard)
  - [Layout](#layout)
  - [Invocation](#invocation)
    - [Resume behaviour](#resume-behaviour)
  - [Configuration](#configuration)
    - [Categories (lifecycle bands)](#categories-lifecycle-bands)
    - [Time-to-triage signal](#time-to-triage-signal)
    - [Milestones (vertical annotations)](#milestones-vertical-annotations)
    - [Rejected-without-tracker ledger (`rejections_ledger_label`)](#rejected-without-tracker-ledger-rejections_ledger_label)
    - [When `upstream_repo` is null](#when-upstream_repo-is-null)
  - [Prerequisites](#prerequisites)
  - [Failure modes](#failure-modes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-tracker-stats-dashboard

**Capability:** substrate:analytics

**Harness:** agnostic

Generate a self-contained HTML dashboard of `<tracker>` repository
statistics — issue-lifecycle bands (untriaged / triaged / PR-merged /
fixed-released / closed-other), opened-vs-untriaged backlog, cumulative
opened/closed, and mean-time-to-triage / first-response / PR-open /
PR-merge / advisory-announced.

All charts are line / area (no bars) with `connectgaps: true`. Plotly
loaded via CDN — the output HTML is self-contained but viewing it
requires network access for the chart library.

The tool is **read-only on GitHub** — it does not create or modify
issues, comments, labels, or PRs. It only fetches data via `gh` and
renders an HTML file.

The companion agentic skill at
[`.claude/skills/security-tracker-stats-dashboard/SKILL.md`](../../skills/security-tracker-stats-dashboard/SKILL.md)
wraps this tool and surfaces it through Claude Code's slash-command
interface; both routes (script-only and skill-driven) run the same
fetch + render pipeline.

## Layout

```text
tools/security-tracker-stats-dashboard/
├── README.md             (this file)
├── default-config.yaml   (config schema + adopter-overridable defaults)
├── render.py             (renders cached data to HTML; reads config)
├── fetch_issues.py       (gh issue list -> issues.json)
├── fetch_roster.py       (gh api collaborators -> roster.txt)
├── fetch_bodies.py       (per-issue body + closedByPRs -> issue_extra.json)
├── fetch_events.py       (per-issue label history -> events/<N>.json)
├── fetch_prs.py          (per-PR metadata from <upstream> -> prs.json)
└── run.sh                (orchestrator)
```

## Invocation

```bash
bash <framework>/tools/security-tracker-stats-dashboard/run.sh [<output-path>]
```

Env knobs (all optional):

| Var | Default | Notes |
|---|---|---|
| `TRACKER_STATS_REPO` | *(e.g. `airflow-s/airflow-s`)* | `<tracker>` repo slug |
| `TRACKER_STATS_OUT` | `/tmp/airflow_s_monthly.html` | output HTML path |
| `TRACKER_STATS_CACHE` | `/tmp/tracker-stats-cache` | fetch cache dir |
| `TRACKER_STATS_CONFIG` | *(unset)* | path to a YAML overlay file |
| `TRACKER_STATS_BUCKETS` | *(from config: `monthly`)* | `monthly` or `quarterly` |
| `TRACKER_STATS_START` | *(from config: `null`)* | `YYYY-MM` or `YYYY-Qn` |
| `TRACKER_STATS_UPSTREAM_REPO` | *(from config; e.g. `apache/airflow`)* | `<upstream>` repo slug; `none` skips PR charts |

### Resume behaviour

Each fetch script resumes from cache, so re-running after a partial
failure (rate limit, transient HTTP error) only re-fetches what is
missing. Delete the cache dir to force a fresh full fetch.

Fetches are parallelised (`ThreadPoolExecutor`, ~10 workers). A fresh
run is ~5–10 minutes on a 250-issue tracker; incremental re-renders
(cache warm) are ~30 seconds.

## Configuration

`render.py` loads configuration in this order, highest priority last:

1. `default-config.yaml` (in this directory).
2. `$TRACKER_STATS_CONFIG` overlay YAML, when set (typically
   `<adopter-repo>/.apache-magpie-overrides/security-tracker-stats.yaml`).
   Deep-merged with the default. **The `milestones` and `categories`
   lists are REPLACED entirely** (not concatenated) — overlaying a
   single category requires re-stating the whole list.
3. Env-var quick overrides for the most common knobs:
   `TRACKER_STATS_BUCKETS`, `TRACKER_STATS_START`,
   `TRACKER_STATS_UPSTREAM_REPO`.

See [`default-config.yaml`](default-config.yaml) for the full schema
with inline documentation of every predicate key.

### Categories (lifecycle bands)

Mutually-exclusive states per tracker at each bucket-end snapshot,
evaluated **top-to-bottom** with first-match-wins. Multiple rules can
share a `name` to express disjoint branches of the same final
category — the default set uses this for the `open / closed`
fork on `fixed_released`. The set of distinct names defines the
stack order in the lifecycle chart (overridable via the
`stack_order:` config key).

Supported predicate keys:

| Key | Meaning |
|---|---|
| `state` | `open` / `closed` |
| `state_reason` | `COMPLETED` / `NOT_PLANNED` / `REOPENED` / `null` |
| `any_label` | at least one of the listed labels is present |
| `all_labels` | every label in the list is present |
| `not_label` | the named label must NOT be present |
| `not_any_label` | none of the listed labels present |
| `no_scope_label` (`true`/`false`) | tracker carries none of `scope_labels` |
| `has_scope_label` (`true`/`false`) | tracker carries at least one of `scope_labels` |
| `pr_merged_by_snapshot` (`true`/`false`) | a linked `<upstream>` PR is merged by the snapshot timestamp |
| `any_of` / `all_of` | logical combinators (nestable) |

Snapshot reconstruction replays each tracker's event stream
(labeled / unlabeled / closed / reopened) chronologically from
`{labels: [], state: OPEN}` at `createdAt`, evaluated at the
bucket-end timestamp (Mar 31 / Jun 30 / Sep 30 / Dec 31 at 23:59:59 UTC
for quarterly; calendar-month last day for monthly).

### Time-to-triage signal

First tracker comment whose author is on the roster (from
`fetch_roster.py`) AND whose body matches any
`triage.keywords[]` regex (case-insensitive). Falls back to
the **first non-bot roster comment** when no keyword matches
(useful for older trackers that predate the team's triage-comment
convention). The `triage.bot_prefixes[]` list skips automated
rollup / sync / import comments.

### Milestones (vertical annotations)

`milestones[]` produces a vertical dashed line + top-label annotation
on every time-axis chart. Each entry needs `date: YYYY-MM-DD` (mapped
onto the bucket axis) and `label`. Set `milestones: []` in an overlay
to remove them entirely.

### Rejected-without-tracker ledger (`rejections_ledger_label`)

```yaml
rejections_ledger_label: rejections-ledger   # null to disable
```

The `security-issue-import` skill sometimes rejects a report with a
canned reply **without creating a tracker** — the disposition lives
only on the mail thread, so it is invisible to every other stat on
this dashboard. To make those rejections countable the team records
each one as a comment on a single dedicated **ledger issue** in the
`<tracker>` repo: one open issue, labelled with
`rejections_ledger_label` (default `rejections-ledger`) and **not**
carrying the security-marker label.

`fetch_issues.py` already pulls every issue's `labels` + `comments`,
so the ledger and its comments arrive in `issues.json` with no extra
fetch. `render.py`:

- **identifies** any issue whose labels include
  `rejections_ledger_label` as a ledger issue;
- **excludes** the ledger issue from all tracker classification —
  it never appears in the lifecycle bands, open/closed KPIs, triage
  medians, or any per-bucket count;
- **parses** the ledger's comments for the rejection markers below
  and renders a *rejected (no tracker)* count.

Each per-rejection comment carries a machine-parseable block:

```text
<!-- rejection v1 -->
date: YYYY-MM-DD
reporter: <email/name>
canned: <canned-response-slug>
thread: <url-or-threadid>
summary: <one line>
```

A one-time historical backfill is recorded as a single comment
(count only, no per-entry dates):

```text
<!-- rejection-backfill v1 count: N -->
```

Dated rejections are bucketed by their `date:` into the same
monthly / quarterly axis as the trackers and rendered as a
*rejected (no tracker)* area series (`c_rejected`). The undated
backfill `count: N` is kept as a separate **historical (pre-ledger)**
headline number rather than smeared across buckets, so the per-bucket
series only ever shows real dated rejections. Both the stdout summary
and an HTML header banner print `<dated> + <historical> = <total>`.

The parse is defensive: comments without a marker are ignored,
malformed `date:` lines are skipped, and an absent ledger issue (or
`rejections_ledger_label: null`) simply omits the stat / shows 0.

### When `upstream_repo` is null

The `c_prc` / `c_prm` / `c_rel` PR-driven mean-time charts are
omitted, the `fetch_prs.py` stage is a silent no-op, and the
`pr_merged_by_snapshot` predicate is always false (so the
`open_pr_merged` snapshot back-fill rule is disabled). The
remaining charts still render.

## Prerequisites

- **Runtime:** Python 3.9+ (`python3`). Run each stage as `python3 fetch_events.py`, etc.
  Optional: `pyyaml` — when missing, `render.py` uses a bundled minimal YAML subset parser
  sufficient for `default-config.yaml` and typical overlays; set `TRACKER_STATS_PY=uv-yaml`
  to pin clean PyYAML invocations via `uv run --with pyyaml`.
- **CLIs:** `gh` (authenticated with read access to `<tracker>`, and to `<upstream>` when
  PR metadata is enabled); `jq` (used by fetch scripts via `gh --jq`).
- **Credentials / auth:** `gh auth status` must show a logged-in account with read access to
  `<tracker>`. `<upstream>` access is required only when `pr_repo` is configured.
- **Network:** `api.github.com` (REST) for event and PR fetch; Plotly CDN
  (`cdn.plot.ly`) when viewing the generated HTML dashboards in a browser.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `events/<N>.json` missing for some N | gh transient failure during paginate | Re-run `run.sh`; `fetch_events.py` resumes from cache |
| `prs.json` has `{"error": ...}` entries | False-positive body parse (PR# doesn't exist) | Silently filtered at render; safe to ignore |
| `c_rel` median jumps after re-fetch | New advisory shipped since last run | Expected — re-render is correct |
| Empty `c_prc` / `c_prm` / `c_rel` early buckets | No linked PR in those tracker buckets | Expected — not all early trackers had a fix PR |
| `ModuleNotFoundError: yaml` | PyYAML missing | The bundled fallback parser handles `default-config.yaml`; for richer overlays install pyyaml or use `TRACKER_STATS_PY=uv-yaml` |
