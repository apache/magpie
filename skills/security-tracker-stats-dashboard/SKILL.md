---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-security-tracker-stats-dashboard
family: security
mode: Meta
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
     <project-config> -> adopting project's `.apache-magpie/` directory
     <framework>      -> framework root (the `.apache-magpie/`
                         snapshot in an adopter repo, or `.` in the
                         framework standalone checkout)
     <tracker>        -> value of `tracker_repo:` in <project-config>/project.md
                         (example: <tracker>)
     <upstream>       -> value of `upstream_repo:` in <project-config>/project.md
                         (example: <upstream>); may be null for
                         trackers whose fixes do not land in a
                         single upstream codebase.
     Before running any bash command below, substitute these with the
     concrete values from the adopting project's <project-config>/project.md. -->

# security-tracker-stats-dashboard

<!-- BEGIN MAGPIE PREFLIGHT — generated from tools/dev/preflight-block.md -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Pre-flight — is this project set up?](#pre-flight--is-this-project-set-up)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Pre-flight — is this project set up?

Do this **first, before anything else in this skill**, and do it silently: on
the happy path it costs three file checks and prints nothing.

A marketplace install delivers *skills only*. Nothing in it configures this
repository, and on most harnesses **no code runs at all** when a plugin is
installed or upgraded — there is no post-install step to rely on. Claude Code's
`SessionStart` hook covers only the all-in-one plugin, so for every other
install this check is the one thing standing between a stale or unadopted repo
and a skill that acts on wrong assumptions.

1. **Is a lock present?** If `.apache-magpie.lock` exists, this project uses the
   pinned-snapshot install. Compare it with `.apache-magpie.local.lock`:
   - local lock missing → the snapshot was never fetched on this machine;
   - `ref` / `commit` differ → this machine is on a different framework version
     than the project pins.
2. **No lock?** Then this is the marketplace install (or nothing at all). Look
   for a `<project-config>/` directory. If there is none, the project has not
   been adopted and every `<placeholder>` in this skill is unresolved.
3. **Anything unresolved above → stop and propose `/magpie-setup`** (or
   `/magpie-setup upgrade` for a version mismatch). Say which of the three
   checks failed and what you found. Do **not** run setup unattended and do
   **not** continue this skill on a guess: a skill that proceeds against an
   unadopted repo writes to the wrong tracker.

Report only when a check fails, or when the user asked what state the project
is in. `/magpie-setup verify` is the full diagnostic — this is deliberately the
cheap subset that is worth paying for on every invocation.

<!-- END MAGPIE PREFLIGHT -->

Read-only skill that renders a self-contained HTML page summarising
the state of `<tracker>` over time. The skill wraps the
[`tools/security-tracker-stats-dashboard/`](../../tools/security-tracker-stats-dashboard/README.md)
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
[`.apache-magpie-local/security-tracker-stats-dashboard.md`](../../docs/setup/agentic-overrides.md) (personal, gitignored) and [`.apache-magpie-overrides/security-tracker-stats-dashboard.md`](../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo if it exists, and applies any
agent-readable overrides it finds. See
[`docs/setup/agentic-overrides.md`](../../docs/setup/agentic-overrides.md)
for the contract — what overrides may contain, hard
rules, the reconciliation flow on framework upgrade,
upstreaming guidance.

Configuration for the *renderer* (bucket granularity, milestones,
categories, scope labels, triage keywords, …) lives in a separate
YAML file the adopter places at
`.apache-magpie-overrides/security-tracker-stats.yaml` (path is
adopter-configurable via `tracker_stats_config:` in
[`<project-config>/security-tracker-stats.md`](../../projects/_template/security-tracker-stats.md)).
The agentic override file above is reserved for *behavioural*
overrides of this skill (when to propose a refresh, where to write
the HTML, etc.); renderer knobs go in the YAML config.

**Hard rule**: agents NEVER modify the snapshot under
`<adopter-repo>/.apache-magpie/`. Local modifications
go in the override file. Framework changes go via PR
to `apache/magpie`.

---

## Snapshot drift

Also at the top of every run, this skill compares the
gitignored `.apache-magpie.local.lock` (per-machine
fetch) against the committed `.apache-magpie.lock`
(the project pin). On mismatch the skill surfaces the
gap and proposes
[`setup upgrade`](../setup/upgrade.md).
The proposal is non-blocking — the user may defer if
they want to run with the local snapshot for now. See
[`docs/setup/install-recipes.md` § Subsequent runs and drift detection](../../docs/setup/install-recipes.md#subsequent-runs-and-drift-detection)
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
   [`<project-config>/security-tracker-stats.md`](../../projects/_template/security-tracker-stats.md)
   for the project's per-renderer YAML config path (default:
   `<adopter-repo>/.apache-magpie-overrides/security-tracker-stats.yaml`).
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
   TRACKER_STATS_CONFIG=<adopter-repo>/.apache-magpie-overrides/security-tracker-stats.yaml \
   bash <framework>/tools/security-tracker-stats-dashboard/run.sh <output-path>
   ```

   When the user passed `monthly` / `quarterly` or
   `since:<start>`, prepend the matching `TRACKER_STATS_BUCKETS=` /
   `TRACKER_STATS_START=` env vars.

4. **Report the result.** Print the final HTML path and a short
   summary (total trackers, open count, latest-bucket category
   breakdown, triage-median, PR-merge-median when configured, and the
   current-bucket projection). The pipeline already echoes most of
   this to stdout — pass it through verbatim and add the clickable
   `file://<output-path>` line at the end.

   The final bucket is always partial, so its counts are not
   comparable with the complete buckets before it. Quote the
   `Current-bucket projection` block as projections — never present a
   projected number as an observed count, and keep the elapsed
   percentage attached. Report the intake lines (`opened`,
   `reported`) and the untriaged-backlog band; the rest of the block
   is there for the charts and only needs quoting when the user asks
   about that series. When the block says *skipped*, say the
   projection was suppressed and why (too early in the bucket, a
   single-bucket axis, or disabled) rather than silently omitting it.

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
[`tools/security-tracker-stats-dashboard/default-config.yaml`](../../tools/security-tracker-stats-dashboard/default-config.yaml)
for the schema with inline documentation, and
[`tools/security-tracker-stats-dashboard/README.md`](../../tools/security-tracker-stats-dashboard/README.md)
for the load order, predicate keys, and snapshot replay semantics.

The most-overridden knobs by adopters tend to be:

- **`buckets:`** — monthly vs. quarterly. Smaller tracker repos
  (<50 issues / year) read better at quarterly granularity.
- **`milestones:`** — vertical annotations marking process
  changes the dashboard should highlight (skill adoption, team
  handover, policy update). Set to `[]` to remove them.
- **`scope_labels:`** — the project's primary "what does this
  affect" axis. Resolved from `scope_detection.labels` in
  [`<project-config>/project.md`](../../projects/_template/project.md)
  (and the matching rows of
  [`<project-config>/scope-labels.md`](../../projects/_template/scope-labels.md)).
  The framework default is `[<scope-a>, <scope-b>, <scope-c>]` —
  adopters re-state this list in their overlay to
  match their own scope set.
- **`categories:`** — the lifecycle-band classification rules.
  Defaults match the framework's reference implementation
  byte-for-byte; adopters with different label conventions
  (e.g. `triaged` instead of *no `needs triage`*) re-state the
  whole list. The label literals used in predicates come from
  `tracker.labels` in
  [`<project-config>/project.md`](../../projects/_template/project.md).
- **`triage.keywords:`** / **`triage.bot_prefixes:`** — the
  time-to-triage signal. Adopters whose security team uses
  different phrasing in triage-proposal comments override these.
- **`projection:`** — the end-of-bucket projection for the current
  (partial) bucket, drawn as a dotted continuation on every chart
  that carries a projectable series (lifecycle bands, opened /
  untriaged, cumulative, rejections) plus a header banner. Intake
  series scale whole (`observed / elapsed`); cumulative totals and
  snapshots scale only their movement inside the bucket; the
  mean-time charts are not projected. `enabled: false` switches it
  off; `min_elapsed_fraction:` (default `0.1`) suppresses it early
  in a bucket, where one report extrapolates to a dozen. Low-volume
  trackers may want a higher threshold.

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
`.apache-magpie-overrides/security-tracker-stats-dashboard.md`; renderer
overrides go in the project's tracker-stats YAML config file. The
gitignored snapshot under `.apache-magpie/` is never modified.

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
| No projection banner on the dashboard | Current bucket below `projection.min_elapsed_fraction`, or the stat is disabled | Expected — stdout prints the skip reason |
| Empty `c_prc` / `c_prm` / `c_rel` early buckets | No linked PR in those tracker buckets | Expected — not all early trackers had a fix PR |
| Three PR charts missing entirely | `upstream_repo: null` in config (or env override) | By design — set `upstream_repo:` if you want them |
| `ModuleNotFoundError: yaml` | PyYAML missing | Bundled fallback parser handles `default-config.yaml`; install pyyaml for richer overlays |
