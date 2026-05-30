---
name: security-tracker-stats-dashboard
description: Generate a self-contained HTML dashboard of `<tracker>` repository statistics for security-team review.
when_to_use: |
  Invoke when the user says "regenerate the tracker dashboard", "show
  monthly/quarterly stats", "tracker stats", "dashboard", or
  variations. Also when an existing dashboard at the configured output
  path is stale (older than ~24 h) and the user is reviewing tracker
  health. Read-only — the skill never modifies any tracker state.
capability: capability:stats
license: Apache-2.0
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> -> adopting project's `.apache-steward/` directory
     <framework>      -> framework root (the `.apache-steward/`
                         snapshot in an adopter repo, or `.` in the
                         framework standalone checkout)
     <tracker>        -> value of `tracker_repo:` in <project-config>/project.md
                         (example: airflow-s/airflow-s)
     <upstream>       -> value of `upstream_repo:` in <project-config>/project.md
                         (example: apache/airflow); may be null for
                         trackers whose fixes do not land in a
                         single upstream codebase.
     Before running any bash command below, substitute these with the
     concrete values from the adopting project's <project-config>/project.md. -->

# security-tracker-stats-dashboard

Read-only skill that renders a self-contained HTML page summarising
the state of `<tracker>` over time. The skill wraps the
[`tools/security-tracker-stats-dashboard/`](../../../tools/security-tracker-stats-dashboard/README.md)
runtime tool — both the slash-command path (this skill) and the
script path (`run.sh`) run the same fetch + render pipeline; the
skill adds invocation niceties (resolving cache paths, surfacing the
output URL, proposing a stale-cache refresh) but never mutates
anything.

The skill is **read-only on GitHub** — it does not create or modify
issues, comments, labels, or PRs. It only fetches data via `gh` and
renders an HTML file.

---

## Adopter overrides

Before running the default behaviour documented
below, this skill consults
[`.apache-steward-overrides/security-tracker-stats-dashboard.md`](../../../docs/setup/agentic-overrides.md)
in the adopter repo if it exists, and applies any
agent-readable overrides it finds. See
[`docs/setup/agentic-overrides.md`](../../../docs/setup/agentic-overrides.md)
for the contract — what overrides may contain, hard
rules, the reconciliation flow on framework upgrade,
upstreaming guidance.

Configuration for the *renderer* (bucket granularity, milestones,
categories, scope labels, triage keywords, …) lives in a separate
YAML file the adopter places at
`.apache-steward-overrides/security-tracker-stats.yaml` (path is
adopter-configurable via `tracker_stats_config:` in
[`<project-config>/security-tracker-stats.md`](../../../projects/_template/security-tracker-stats.md)).
The agentic override file above is reserved for *behavioural*
overrides of this skill (when to propose a refresh, where to write
the HTML, etc.); renderer knobs go in the YAML config.

**Hard rule**: agents NEVER modify the snapshot under
`<adopter-repo>/.apache-steward/`. Local modifications
go in the override file. Framework changes go via PR
to `apache/airflow-steward`.

---

## Snapshot drift

Also at the top of every run, this skill compares the
gitignored `.apache-steward.local.lock` (per-machine
fetch) against the committed `.apache-steward.lock`
(the project pin). On mismatch the skill surfaces the
gap and proposes
[`/setup-steward upgrade`](../setup-steward/upgrade.md).
The proposal is non-blocking — the user may defer if
they want to run with the local snapshot for now. See
[`docs/setup/install-recipes.md` § Subsequent runs and drift detection](../../../docs/setup/install-recipes.md#subsequent-runs-and-drift-detection)
for the full flow.

Drift severity:

- **method or URL differ** -> ✗ full re-install needed.
- **ref differs** (project bumped tag, or `git-branch`
  local is behind upstream tip) -> ⚠ sync needed.
- **`svn-zip` SHA-512 mismatches the committed
  anchor** -> ✗ security-flagged; investigate before
  upgrading.

---

## Prerequisites

- `gh` authenticated with read access to `<tracker>` (and to
  `<upstream>` for PR metadata, when configured).
- `python3` (3.9+).
- `jq` (used by `fetch_events.py` via gh's `--jq` flag).
- Network access to `api.github.com` and (for *viewing* the output
  HTML) Plotly's CDN.
- Optional: PyYAML. When missing, the renderer falls back to a
  bundled minimal YAML subset parser sufficient for
  `default-config.yaml` and typical overlays.

---

## Inputs

The skill accepts up to three optional arguments:

| Selector | Meaning |
|---|---|
| *(no args)* | render with all defaults — monthly buckets, default categories, the adopter's milestones |
| `quarterly` / `monthly` | override the bucket granularity |
| `<output-path>` | write the HTML to a specific path |
| `clear-cache` | delete the fetch cache before fetching |
| `since:YYYY-MM` / `since:YYYY-Qn` | override the start bucket |

If the adopter passes nothing, surface the resolved output path and
cache state up front so they can interrupt before a 5-10 minute
fetch.

---

## How to invoke

1. **Resolve config.** Read
   [`<project-config>/security-tracker-stats.md`](../../../projects/_template/security-tracker-stats.md)
   for the project's per-renderer YAML config path (default:
   `<adopter-repo>/.apache-steward-overrides/security-tracker-stats.yaml`).
   Surface to the user *which* config file will be applied and
   *what bucket granularity* it resolves to. If the YAML file does
   not exist, fall back silently to the framework's
   `default-config.yaml`.

2. **Check cache freshness.** Inspect
   `${TRACKER_STATS_CACHE:-/tmp/tracker-stats-cache}/issues.json`
   mtime. If older than 24 h, propose a fresh fetch; if missing or
   the user passed `clear-cache`, do a fresh fetch unconditionally.

3. **Run the orchestrator.** Substitute placeholders and invoke:

   ```bash
   TRACKER_STATS_REPO=<tracker> \
   TRACKER_STATS_UPSTREAM_REPO=<upstream> \
   TRACKER_STATS_CONFIG=<adopter-repo>/.apache-steward-overrides/security-tracker-stats.yaml \
   bash <framework>/tools/security-tracker-stats-dashboard/run.sh <output-path>
   ```

   When the user passed `monthly` / `quarterly` or
   `since:<start>`, prepend the matching `TRACKER_STATS_BUCKETS=` /
   `TRACKER_STATS_START=` env vars.

4. **Report the result.** Print the final HTML path and a short
   summary (total trackers, open count, latest-bucket category
   breakdown, triage-median, PR-merge-median when configured). The
   pipeline already echoes most of this to stdout — pass it
   through verbatim and add the clickable
   `file://<output-path>` line at the end.

The full pipeline:

1. `fetch_issues.py` — `gh issue list --state all --limit 1000` ->
   `<cache>/issues.json`.
2. `fetch_roster.py` — `gh api repos/<tracker>/collaborators` ->
   `<cache>/roster.txt`.
3. `fetch_bodies.py` — per-issue `body` +
   `closedByPullRequestsReferences` -> `<cache>/issue_extra.json`.
4. `fetch_events.py` — per-issue label-history events ->
   `<cache>/events/<N>.json`.
5. `fetch_prs.py` — per-PR `createdAt` / `mergedAt` / `state` from
   `<upstream>` -> `<cache>/prs.json`. Silent no-op when
   `TRACKER_STATS_UPSTREAM_REPO` is empty or `none`.
6. `render.py` — reads cache + config, writes HTML to
   `$TRACKER_STATS_OUT`.

Each fetch script resumes from cache, so re-running after a partial
failure (rate limit, transient HTTP error) only re-fetches what is
missing.

---

## Configuration overview

See
[`tools/security-tracker-stats-dashboard/default-config.yaml`](../../../tools/security-tracker-stats-dashboard/default-config.yaml)
for the schema with inline documentation, and
[`tools/security-tracker-stats-dashboard/README.md`](../../../tools/security-tracker-stats-dashboard/README.md)
for the load order, predicate keys, and snapshot replay semantics.

The most-overridden knobs by adopters tend to be:

- **`buckets:`** — monthly vs. quarterly. Smaller tracker repos
  (<50 issues / year) read better at quarterly granularity.
- **`milestones:`** — vertical annotations marking process
  changes the dashboard should highlight (skill adoption, team
  handover, policy update). Set to `[]` to remove them.
- **`scope_labels:`** — the project's primary "what does this
  affect" axis. Resolved from `scope_detection.labels` in
  [`<project-config>/project.md`](../../../projects/_template/project.md)
  (and the matching rows of
  [`<project-config>/scope-labels.md`](../../../projects/_template/scope-labels.md)).
  ASF/Airflow default is `[airflow, providers, chart]` —
  non-ASF adopters re-state this list in their overlay to
  match their own scope set.
- **`categories:`** — the lifecycle-band classification rules.
  Defaults match the airflow-s reference implementation
  byte-for-byte; adopters with different label conventions
  (e.g. `triaged` instead of *no `needs triage`*) re-state the
  whole list. The label literals used in predicates come from
  `tracker.labels` in
  [`<project-config>/project.md`](../../../projects/_template/project.md).
- **`triage.keywords:`** / **`triage.bot_prefixes:`** — the
  time-to-triage signal. Adopters whose security team uses
  different phrasing in triage-proposal comments override these.

---

## Hard rules

**Golden rule 1 — read only, never write.** The skill must not
post comments, add labels, close, edit, or otherwise mutate any
tracker, PR, or upstream resource. If the user asks for stats and
also wants an action, decline the mutation.

**Golden rule 2 — proposal-before-fetch on stale cache.** Before
running a fresh full fetch (which costs ~5-10 minutes of `gh` API
calls), surface the proposal and wait for explicit user
confirmation. Incremental re-renders against a warm cache (~30
seconds) can run without a prompt.

**Golden rule 3 — never edit the snapshot.** As with every other
skill, agentic overrides go in
`.apache-steward-overrides/security-tracker-stats-dashboard.md`; renderer
overrides go in the project's tracker-stats YAML config file. The
gitignored snapshot under `.apache-steward/` is never modified.

**Golden rule 4 — surface the config path on every run.** The
dashboard's output depends entirely on which YAML file the renderer
loaded. Print the resolved config path (or "default") as the first
line of skill output so the user can tell at a glance whether their
overlay is being picked up.

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `events/<N>.json` missing for some N | gh transient failure during paginate | Re-run; `fetch_events.py` resumes from cache |
| `prs.json` has `{"error": ...}` entries | False-positive body parse (PR# doesn't exist) | Silently filtered at render; safe to ignore |
| `c_rel` median jumps after re-fetch | New advisory shipped since last run | Expected — re-render is correct |
| Empty `c_prc` / `c_prm` / `c_rel` early buckets | No linked PR in those tracker buckets | Expected — not all early trackers had a fix PR |
| Three PR charts missing entirely | `upstream_repo: null` in config (or env override) | By design — set `upstream_repo:` if you want them |
| `ModuleNotFoundError: yaml` | PyYAML missing | Bundled fallback parser handles `default-config.yaml`; install pyyaml for richer overlays |
