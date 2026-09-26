<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Compute

## Step 5a — Compute health rating + action recommendations

Pure function of the classified open-PR set. No network.

1. Apply the **health rating** thresholds from [`aggregate.md#health-rating`](aggregate.md#health-rating): each fired threshold is a "issue point". Map total points → `✅ Healthy` / `⚠️ Needs attention` / `🔥 Action needed`.
2. Walk the **recommendation rules** from [`render.md#recommendation-rules`](render.md#recommendation-rules) in declared order. Each rule that fires produces one entry with `priority`, `icon`, `title`, `detail`, `action` (an exact slash command, or `—` when no paste-clean command applies), and a count. `action` and `detail` are kept in separate columns so prose / parentheticals stay out of the slash command.
3. The recommendation list is the input to the dashboard's "What needs attention" panel. If zero rules fire, surface the explicit "no urgent actions detected" panel — never leave the section empty.

---

## Step 5b — Compute weekly velocity buckets

Pure function of the closed/merged-since-cutoff PR set.

For each of the last 6 weeks (rolling, anchored on the fetch-start `<now>`), bucket PRs by `closedAt` and count `merged` and `closed` separately. Also count the triaged-then-merged / triaged-then-closed / triaged-then-responded subsets — those are what feed the trend mini-stats below the velocity bars.

See [`aggregate.md#weekly-velocity`](aggregate.md#weekly-velocity) for the exact bucket boundaries and the avg/peak summary computation.

---

## Step 5c — Compute opened-vs-closed weekly buckets

Pure function of *both* the open-PR set (Step 1) and the closed/merged-since-cutoff PR set (Step 3) — every PR's `createdAt` is checked against each weekly window regardless of current state.

For each of the same six rolling weekly windows, compute:

- `opened` — PR's `createdAt` falls in the window
- `closed_total` — PR was closed/merged in the window (reuses the velocity buckets from Step 5b)
- `net_delta = opened - closed_total`

These per-week numbers feed the dashboard's "Opened vs closed momentum" line chart and the two-line "Net delta" summary below it. See [`aggregate.md#opened-vs-closed-weekly-buckets`](aggregate.md#opened-vs-closed-weekly-buckets) for the exact spec.

---

## Step 5d — Compute ready-for-review trend by top areas

Needs one extra fetch (per [`fetch.md#ready-label-timeline`](fetch.md#ready-label-timeline)): for each currently-`ready for maintainer review` PR, the timestamp of its most recent `LabeledEvent` adding that label. Aliased GraphQL, ~30 PRs per call.

Then for each top-pressure area (top 5 by Step 5f's score, filtered to areas with ≥ 3 currently-ready PRs), compute a 6-bucket cumulative count: `ready_count[a][w] = count of currently-ready PRs in area a where labeled_at <= w.end`.

Feeds the dashboard's "Ready-for-review trend" multi-line chart. See [`aggregate.md#ready-for-review-trend-by-top-areas`](aggregate.md#ready-for-review-trend-by-top-areas) for the exact spec and rendering rules.

---

## Step 5e — Compute closed-by-triage-reason buckets

Pure function of the closed/merged-since-cutoff PR set (Step 3) — reuses the existing per-PR `is_triaged` / `responded_before_close` / `merged` flags.

For each weekly bucket, classify each closed PR into exactly one of four categories: `merged`, `closed-after-responded`, `closed-after-triage-no-response`, `closed-no-triage`. Sum per category per week.

Feeds the dashboard's "Closed-by-triage-reason per week" stacked bar chart. See [`aggregate.md#closed-by-triage-reason-per-week`](aggregate.md#closed-by-triage-reason-per-week) for the category definitions, colour map, and summary line.

---

## Step 5f — Compute area pressure scores

Pure function of the classified open-PR set.

Per area, compute a **pressure score** = weighted sum of urgent PR conditions. The weights are defined in [`aggregate.md#pressure-score`](aggregate.md#pressure-score):

- untriaged non-draft, > 4 weeks old → 5 pts
- untriaged non-draft, 1–4 weeks old → 3 pts
- untriaged non-draft, < 1 week old → 1 pt
- triaged-waiting, > 7 days old → 2 pts (author abandoned, sweep candidate)
- ready-for-review (label present) → 1 pt (queue waiting on maintainer review)
- everything else → 0 pts (drafts the maintainer can ignore until author engages)

Sort areas by score descending; render the top 8 (filtering areas with < 3 contributor PRs as noise) in the "Pressure by area" panel.

---

## Step 5g — Compute trend snapshots (backlog / inflow / triage velocity / coverage)

Pure function of the union of open + closed-since-cutoff PR sets. No additional network beyond what Steps 1, 3, and 5d already fetched.

For each of the same six weekly windows, compute (see [`aggregate.md`](aggregate.md) for each spec):

- **Open backlog** — count of PRs that were *open at end-of-week-`w`* (createdAt ≤ window.end AND (currently open OR closedAt > window.end)).
- **PRs opened by author class** — partition the `opened` per-week count by `authorAssociation` (FIRST_TIME / CONTRIBUTOR / MAINTAINER).
- **Triage velocity** — count of PRs whose *first* QC-marker comment fell in the window, split by AI-drafted vs manual.
- **Triage coverage rate** — for PRs opened in the window, percentage where `is_engaged` is true.
- **Ready-queue size cumulative** — count of currently-ready PRs whose `labeled_at` ≤ window.end (single line, all areas combined; the per-area version is from Step 5d).

These five series feed the dashboard's "Trends over time" section (panel 3b).

⚠ Triage velocity and triage coverage rate are limited by the `comments(last:N)` cap on the closed-PR fetch (N=25): older outstanding triage markers on chatty PRs are missed. Annotate the panels with the caveat.

---

## Step 5h — Compute CODEOWNERS responsibility (optional)

Skip if `.github/CODEOWNERS` (and the fallback locations described in
[`fetch.md#reading-githubcodeowners`](fetch.md#reading-githubcodeowners)) are absent.

Otherwise:

1. Parse the file into `(pattern, [owners])` rules in declaration order. Owner tokens are stripped of leading `@`.
2. For each currently-ready PR, fetch its changed file paths (
   [`fetch.md#pr-changed-files-codeowners-panel`](fetch.md#pr-changed-files-codeowners-panel)) — one extra GraphQL pass, ~8 calls for ~150 ready PRs.
3. For each file, apply the rules and take the **last** matching rule's owners. Union per PR.
4. Per owner, count distinct PRs in their union.
5. **Waiting subcount**: for each (owner, PR) pair, check whether the owner has posted any comment on the PR (from the comments fetched in Step 1) such that the author has not commented or pushed since. Count distinct PRs per owner.

Feeds the dashboard's "Ready-for-review queue by CODEOWNER" panel (8b). See [`aggregate.md#ready-for-review-queue-by-codeowner`](aggregate.md#ready-for-review-queue-by-codeowner).

---
