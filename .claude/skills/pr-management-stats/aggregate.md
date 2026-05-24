<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Aggregate

Turn the classified PR set into the two per-area stat objects that [`render.md`](render.md) prints. Pure function of the output of [`classify.md`](classify.md) — no network.

---

## Area grouping

Each PR can carry zero or more `area:*` labels (e.g. `area:UI`, `area:scheduler`, `area:db-migrations`). For stats purposes:

- Strip the `area:` prefix — display column shows `UI`, `scheduler`, etc.
- A PR with **multiple** `area:*` labels contributes to **every** matching area (a cross-cutting PR moves the needle in each area it touches).
- A PR with **no** `area:*` labels goes into a synthetic area named `(no area)`.
- Never expand to other label prefixes (`provider:*`, `kind:*`, `backport-to-*`) — those have their own grouping stories and would dilute the area view.

Order the areas for display by total-count descending, with `(no area)` always last regardless of count.

---

## Counters (per area)

One `_AreaStats` block per area. Only two counters (`total` and `contributors`) cover all PRs; every other counter is **contributor-only** (excludes `OWNER` / `MEMBER` / `COLLABORATOR` authors). The rationale is that collaborator PRs have a different lifecycle — they're not triaged by the pr-management-triage skill, they don't need "ready for maintainer review" to surface, and their drafts are the author's to manage. Mixing them into the draft / triaged / responded counts dilutes every percentage on the row.

| Field | Count rule | Scope |
|---|---|---|
| `total` | count of PRs in the area | **all** — reference only |
| `total_drafts` | `isDraft == true` | **all** — denominator for the dashboard draft/non-draft split |
| `total_non_drafts` | `isDraft == false` | **all** — paired with `total_drafts` |
| `contributors` | `authorAssociation NOT IN (OWNER, MEMBER, COLLABORATOR)` | **all** — denominator for the contributor-scoped counters below |
| `drafts` | `isDraft == true` | contributor-only |
| `non_drafts` | `isDraft == false` | contributor-only |
| `triaged_waiting` | classified `triaged_waiting` (see `classify.md`) | contributor-only |
| `triaged_responded` | classified `triaged_responded` | contributor-only |
| `ready_for_review` | label `ready for maintainer review` present | contributor-only |
| `engaged` | satisfies [`is_engaged`](classify.md#is_engaged--de-facto-triaged) (any maintainer touched it) | contributor-only |
| `defacto_triaged` | satisfies [`is_defacto_triaged`](classify.md#is_engaged--de-facto-triaged) (engaged but no marker) | contributor-only |
| `ai_triaged` | satisfies [`is_ai_triaged`](classify.md#is_ai_triaged--ai-assisted-triage) (received an AI-assisted triage comment) | contributor-only |
| `bot_authored` | [`is_bot`](classify.md#is_bot--author-is-a-recognised-bot)(pr.author.login) | **all** — its own category, NOT in `contributors` |
| `untriaged_nondraft` | satisfies [`is_untriaged`](classify.md#is_untriaged--broad-untriaged) AND `isDraft == false` | contributor-only |
| `untriaged_old` | `untriaged_nondraft` AND `age_bucket == ">4w"` | contributor-only |
| `untriaged_med` | `untriaged_nondraft` AND `age_bucket == "1-4w"` | contributor-only |
| `triager_drafted` | classified `drafted_by_triager` | contributor-only |
| `age_buckets` | histogram, key = bucket label from `classify.md#age-bucket` | contributor-only |
| `draft_age_buckets` | histogram over PRs where `drafted_at` is set, same bucket labels | contributor-only |

The three `untriaged_*` counters share the same predicate (see
[`classify.md#is_untriaged--broad-untriaged`](classify.md#is_untriaged--broad-untriaged))
— a PR carrying the `ready for maintainer review` label is **not** counted as
untriaged regardless of whether the literal triage marker is present, because
the label itself is evidence that the PR cleared the triage bar.

### Invariants

- `total == total_drafts + total_non_drafts` (every PR is exactly one)
- `contributors + collaborator_authored + bot_authored == total` (three disjoint author classes)
- `contributors == drafts + non_drafts` (each contributor PR is one or the other)
- `triaged_waiting + triaged_responded <= contributors`
- `triaged_waiting + triaged_responded <= engaged` (Quality-Criteria-triaged is a subset of engaged)
- `defacto_triaged + (triaged_waiting + triaged_responded) == engaged` (every engaged PR is either Quality-Criteria-triaged or de-facto-only)
- `ready_for_review <= non_drafts` (a ready PR shouldn't be draft — if the inequality fails, the label is stale; surface a one-line warning but don't correct the data)
- `untriaged_old + untriaged_med <= untriaged_nondraft <= non_drafts`
- `engaged + untriaged_nondraft + ready_for_review == non_drafts (contributor)` (the partition: every contributor non-draft is exactly one of `is_engaged` (strict OR de-facto), `is_untriaged` (no maintainer touched), or already-`ready` labelled — the three are mutually exclusive once the `is_untriaged` definition uses `NOT is_engaged` rather than `NOT is_triaged`)
- `sum(age_buckets.values()) == contributors`
- `contributors <= total`

Check the invariants at render time and print a one-line warning if any fails — it usually means the fetch shape dropped a field.

---

## TOTAL row

The TOTAL row is NOT the column-wise sum of per-area rows — a PR with two `area:*` labels appears in both area rows, so summing would double-count. Instead:

- Re-walk the classified PR set.
- For each PR, increment every counter exactly once (ignore its area labels entirely).
- Render as a final row, visually separated from the per-area rows.

The TOTAL row's `age_buckets` also re-buckets every PR once. The final TOTAL row is the authoritative "how big is the backlog" view.

---

## Percentage rules

The stats tables show percentages alongside counts for readability. Rules:

- Format: rounded integer with `%` suffix (e.g. `73%`). No decimals — table noise.
- If the denominator is 0, show `-`, not `0%`.
- `%Contrib.` denominator is `total` (how much of the area is contributor-authored).
- `%Draft` denominator is `contributors` (how much of the contributor work is still in draft).
- `%Ready` denominator is `contributors` (how much of the contributor work is at the review bar).
- `%Responded` denominator is `triaged_waiting + triaged_responded` (the triaged set). A PR that was never triaged can't have responded.

The only percentage whose denominator is `total` is `%Contrib.` — that's the one that describes the area composition. Every other percentage describes contributor activity and uses `contributors` as its denominator.

Table 1 has its own percentage set (`%Closed`, `%Merged`, `%Responded`) whose denominators are `triaged_total` for that area (not global, not contributor-scoped — Table 1's whole point is the triaged set).

---

## Closed-since counters (Table 1)

Parallel structure but different fields per area:

| Field | Count rule |
|---|---|
| `triaged_total` | count of closed/merged PRs in the area that were triaged |
| `closed` | `state == CLOSED AND NOT merged` |
| `merged` | `merged == true` |
| `responded_before_close` | triaged PRs whose author commented after the triage comment and before `closedAt` |

Derived:

- `pct_closed = closed / triaged_total`
- `pct_merged = merged / triaged_total`
- `pct_responded = responded_before_close / triaged_total`

Percentages can legitimately sum to > 100% when a PR was both merged and responded; don't force them to add up.

---

## Pressure score

Per area, the dashboard's "Pressure by area" ranking uses a weighted urgency score so areas with stale-and-untriaged contributor PRs surface above areas with healthy queues regardless of raw size.

For each contributor PR in an area, add the matching weight (first-match-wins, top to bottom):

| Condition | Weight | Rationale |
|---|---|---|
| ready-for-review label present | **1** | queue waiting on maintainer review — soft pressure |
| triaged-waiting AND triage comment age ≥ 7 days | **2** | author abandoned; stale-sweep candidate |
| draft (any age, any triage state) | **0** | author's court — not maintainer pressure |
| untriaged non-draft AND `last_author_at` ≥ 28 days | **5** | most urgent — slipped through triage |
| untriaged non-draft AND 7–28 days | **3** | author still likely active; needs triage soon |
| untriaged non-draft AND < 7 days | **1** | recent — give the next sweep a chance |

Collaborator-authored PRs (`OWNER`/`MEMBER`/`COLLABORATOR`) score **0** regardless of state — they have a different lifecycle (see [`#counters-per-area`](#counters-per-area)).

Sort areas by score descending. The dashboard renders the top 8 areas; areas with fewer than 3 contributor PRs are filtered as noise (a tiny area with one stale PR shouldn't dominate the ranking).

The score is also used to bucket the area into a severity colour for the dashboard:

| Score | Severity | Border colour |
|---|---|---|
| ≥ 30 | high | red |
| 15–29 | medium | amber |
| < 15 | low | grey |

Tune the weights here in lockstep with the recommendation rules in [`render.md#recommendation-rules`](render.md#recommendation-rules) — they share the same notion of "what's urgent" and drift between the two would produce contradictory dashboard sections.

---

## Weekly velocity

The dashboard's "Closure velocity" panel buckets the closed-since-cutoff PR set into the last 6 calendar-weeks (rolling, anchored on the fetch-start `<now>`).

For each `w` in `0..5`:

```text
window_end   = now - w * 7 days
window_start = window_end - 7 days
```

`w == 0` is the current week (oldest = `<now> - 7d`, newest = `<now>`). `w == 5` is the oldest week in the chart.

Per window, count three metrics:

| Field | Count rule |
|---|---|
| `merged` | PR has `merged == true` AND `closedAt` falls in the window |
| `closed` | PR has `merged == false` AND `closedAt` falls in the window |
| `triaged_then_responded` | PR is triaged (per [`classify.md#triage-marker`](classify.md#triage-marker)) AND `closedAt` falls in the window AND the author commented after the triage comment |

Render the bars oldest → newest (so the eye sweeps left-to-right matching natural time order). Each bar is a stacked `merged` (green) + `closed` (grey) segment, normalised to the maximum total in the 6-week window.

Below the bars, print three summary numbers:

- **6-week total** — sum of `merged + closed` across all six windows.
- **avg/wk** — `total / 6`, rounded.
- **peak** — `max(merged + closed)` across the six windows.

The avg and peak give the maintainer a quick sense of whether this week is normal, slow, or unusually busy.

---

## Opened-vs-closed weekly buckets

The dashboard's "Opened vs closed momentum" line chart needs a parallel bucket counting **PRs opened** per week (in addition to the closures already computed above).

For each of the same six rolling windows (`w` in `0..5`), count:

| Field | Count rule |
|---|---|
| `opened` | any PR (open or closed at fetch time) where `createdAt` falls in the window |
| `closed_total` | `merged + closed` from the velocity bucket above |
| `net_delta` | `opened - closed_total` (positive = backlog growing that week, negative = shrinking) |

`opened` requires combining the open-PR set (Step 1 fetch) and the closed-since-cutoff set (Step 3 fetch) into a single iteration — every PR's `createdAt` is checked against the window regardless of current state. PRs opened *before* the cutoff but closed *within* the window count for the closed bucket but not the opened bucket (their createdAt is out of window).

Below the chart, print two summary lines computed from these buckets:

```text
Net delta this week: ±<N> PRs (<opened> opened - <closed_total> closed)
6-week net: ±<N> PRs (<sum_opened> opened - <sum_closed> closed) — backlog <growing|shrinking|stable>
```

`stable` is used when `|6-week net| < 10`. Anything bigger reads as a real direction.

The line chart itself is rendered via inline SVG in [`render.md`](render.md). The aggregate layer just produces the per-week numbers — chart geometry (line interpolation, axes, gridlines) is purely a render concern.

### Why opened *and* closed (not just net)

Net alone hides activity. A week with 100 opened and 100 closed has the same net as a week with 0 opened and 0 closed, but the maintainer experience is wildly different — the first is a busy week, the second is dormant. Rendering both lines lets the maintainer see "we're keeping up" vs "nothing's happening" at a glance.

---

## Ready-for-review trend by top areas

The dashboard's "Ready-for-review trend" panel shows the cumulative count of currently-`ready for maintainer review` PRs over the last 6 weeks, broken down by the top-N highest-pressure areas (default N = 5; areas with fewer than 3 currently-ready PRs are excluded as noise).

For each PR currently carrying the label, the **labeled-at timestamp** is the `createdAt` of the most recent `LabeledEvent` where `label.name == "ready for maintainer review"` from the PR's timeline (see [`fetch.md#ready-label-timeline`](fetch.md#ready-label-timeline)).

For each top area `a` and each weekly bucket `w` in `0..5`:

```text
ready_count[a][w] = count of currently-ready PRs in area a where labeled_at <= w.end
```

This is a **cumulative** count, not a per-week delta — by construction it's monotonically non-decreasing because PRs that lose the label drop out of the *currently-ready* set entirely (they're not in this dataset).

Render the result as a multi-line chart, one line per area, with the area's pressure-band colour from [`#pressure-score`](#pressure-score) (red / amber / grey lines). Each line ends at the current count visible in the dashboard's hero card.

Below the chart, print a one-line per-area summary:

```text
providers: 46 ready (+8 in last 7d)
task-sdk: 40 ready (+5 in last 7d)
…
```

The "+N in last 7d" is the count of PRs labeled within the last week — surfaces whether the queue is growing faster than it can be reviewed.

### Why cumulative, not weekly-delta

A maintainer looking at the trend wants to see "how is the review backlog evolving" — a steadily-growing line means review velocity isn't keeping up with triage promotion. Per-week deltas would show only the additions and obscure that the queue keeps *being* big. The cumulative view answers the actual question.

---

## Closed by triage reason per week

The dashboard's "Closed-by-triage-reason" panel shows the per-week stacked breakdown of closed/merged PRs by triage outcome. Each closed PR falls into exactly one of four categories:

| Category | Definition | Colour |
|---|---|---|
| `merged` | `merged == true` (regardless of triage state) | green |
| `closed-after-responded` | `merged == false` AND `is_triaged` AND `responded_before_close == true` | amber |
| `closed-after-triage-no-response` | `merged == false` AND `is_triaged` AND `responded_before_close == false` | red |
| `closed-no-triage` | `merged == false` AND NOT `is_triaged` | grey |

For each weekly bucket, count PRs in each category. Render as a 6-row stacked horizontal bar (same layout as the velocity chart — newest at the bottom).

The four colours map directly to maintainer outcomes:

- **green** = success path (PR shipped)
- **amber** = engagement-but-no-merge (author responded but PR didn't make it — could be design rejection, scope change, etc.)
- **red** = stale-sweep / abandonment (triaged then ghosted; usually closed via sweep 1a)
- **grey** = no-triage closure (author closed it themselves, or maintainer closed without going through triage)

A healthy week has a tall green segment with thin amber/red/grey segments. A week dominated by red is a triage-followup pile-up; a week dominated by grey is contributors self-cleaning their own PRs (also fine).

Below the bars, print three summary numbers:

```text
6-week breakdown: <merged_total> merged · <closed_after_responded> engaged-then-closed · <closed_no_response> sweep-closed · <closed_no_triage> no-triage
```

This panel makes the *quality* of closures visible — the velocity panel says "how many", this panel says "of what type".

---

## Triager activity (per-triager, per-week)

The dashboard's "Triager activity" section ranks maintainers by how many
distinct PRs each one **engaged with** in each of the last 6 calendar weeks.
"Engaged" uses the same predicate as
[`is_engaged`](classify.md#is_engaged--de-facto-triaged)
(any maintainer comment / review).

For each open PR currently in the fetch set, walk
`pr.comments(last:25).nodes` and the parallel review-thread sub-comments:

```text
for each comment c by login L where authorAssociation IN
    (OWNER, MEMBER, COLLABORATOR) AND NOT is_bot(L):
    bucket = which_week(c.createdAt)   # see #weekly-velocity for bucket math
    if bucket is one of the 6 windows:
        kind = "ai" if "AI-assisted triage tool" in c.body else "manual"
        triager_weekly[L][bucket][kind] += (first-engagement-in-bucket counter)
```

Per-week counting rule: count **at most one PR per (login, week, kind)** even
when the same maintainer posts multiple comments in the same week of the same
kind. The intent is "how many distinct PRs did this maintainer touch each week,
split by AI-assisted vs manually-typed engagement" not "how many comments did
they post"; multiple comments by the same person in the same week on the same
PR of the same kind collapse to a single tally.

### AI vs manual split

Every triager's per-week count is further split into:

- **AI-assisted**: comments whose body contains the AI-attribution footer
  substring (`AI-assisted triage tool` — same detector as
  [`is_ai_triaged`](classify.md#is_ai_triaged--ai-assisted-triage)).
- **Manual**: comments without the footer.

Same PR can contribute to *both* sub-counts for the same maintainer-week if
they posted both an AI-drafted comment and a manually-typed comment in the
same window. The dashboard shows the two side-by-side so the maintainer team
can see how much of each person's throughput is coming through the skill
versus through direct review.

A maintainer's total for a week is `ai + manual`; both sub-counts use the
per-PR de-duplication rule (one PR per kind per week).

Counted as engagement:

- Issue-level comments (`pr.comments(last:25)` in the standard fetch).
- Review-thread comments — walk every
  `pr.reviewThreads.nodes.comments(first:5)` for the same maintainer test.
- `LabeledEvent` adding the `ready for maintainer review` label by a
  maintainer (counts the label-add as the engagement timestamp). This catches
  reviewers who applied the label without leaving a comment.

The fetch shape in [`fetch.md`](fetch.md) already populates issue-level
comments and review threads in the open-PR query. The label-add timestamp
needs the `ready-label-timeline` query
[(see `fetch.md#ready-label-timeline`)](fetch.md#ready-label-timeline) which
the dashboard's "Ready-for-review trend by top areas" panel already fires —
re-use that result.

### Top-N rendering rule

The "Triager activity" panel renders the top 15 maintainers by total PRs
engaged across the 6-week window. The table layout (one row per triager,
six week columns + a total column + a sparkline / mini-bars column) is
defined in [`render.md#triager-activity-panel`](render.md). Maintainers with
zero engagement in the window are excluded from the panel.

### Caveats

- Engagement is **at-most-one-PR-per-week-per-maintainer-per-PR**, not
  comment-count. The maintainer who triages 20 PRs in one week and the
  maintainer who comments 20 times on one PR show as 20 and 1 respectively.
- The same maintainer can show up in multiple weeks for the same PR if they
  engaged in each window — that is by design (re-engagement signals
  continued attention).
- Bot-account comments are excluded via the same
  [`is_bot`](classify.md#is_bot--author-is-a-recognised-bot) test used in the
  open-PR counters; copilot review-bots that post under a `CONTRIBUTOR`
  association are not counted anyway (the maintainer check filters them).

---

## Backlog over time (per-week snapshots)

The dashboard's "Open backlog over time" panel shows how the total open-PR count
moved at the end of each of the last 6 weeks.

For each weekly bucket `w` in `0..5`, count PRs that were *open at end-of-week-`w`*:

```text
open_count[w] = count of non-bot PRs P where:
                  P.createdAt <= w.end
                  AND (P is currently open
                       OR (P is closed AND P.closedAt > w.end))
```

PRs closed *before* the cutoff are absent from both datasets, so for `w` near the
cutoff edge the snapshot is a slight under-count. Note the caveat in the
dashboard.

Below the chart, print:

```text
6-week trend: <delta> open PRs (start: <open_count[0]>, end: <open_count[5]>)
```

Colour the delta red when growth is >10, green when shrinkage is >10, grey
otherwise.

---

## PRs opened by author class (per-week)

The "PRs opened by author class" panel splits the `opened` per-week count from
[`#opened-vs-closed-weekly-buckets`](#opened-vs-closed-weekly-buckets) by the PR
author's GitHub association:

| Bucket | `authorAssociation` |
|---|---|
| `first_time` | `FIRST_TIME_CONTRIBUTOR`, `FIRST_TIMER` |
| `contributor` | `CONTRIBUTOR`, `NONE`, anything else not below |
| `collab` (maintainer) | `OWNER`, `MEMBER`, `COLLABORATOR` |

Bot-authored PRs are excluded
(per [`classify.md#is_bot`](classify.md#is_bot--author-is-a-recognised-bot)).

For each `w` in `0..5`, count PRs whose `createdAt` falls in the window,
bucketed by association. Render as a multi-line chart with three lines (or
stacked-bar if multi-line is too crowded).

Surfaces shifts in inflow composition — a sudden rise in `first_time` is signal
for triage-attention demand; a drop in `contributor` may indicate community
drift.

---

## Triage velocity (per-week)

The "Triage velocity" panel counts PRs whose **first** Quality-Criteria marker
comment fell in each week. Distinct from the closure-by-reason chart (which
counts when PRs *closed*) — this counts when triage *happened*.

For each PR (open OR closed-since-cutoff), `triage_comment_ts` is the timestamp
of its *earliest* maintainer comment containing the `Pull Request quality
criteria` marker. Bucket by week of `triage_comment_ts` (skip PRs that were
never triaged).

Split each week's count by AI vs manual:

| Series | Definition |
|---|---|
| `ai` | The triage-comment also contains the [`is_ai_triaged`](classify.md#is_ai_triaged--ai-assisted-triage) footer substring |
| `non_ai_qc` | Triage comment present but no AI footer (a maintainer pasted the QC link manually) |

⚠ **Data caveat**: the closed-PR fetch caps comments at `last:25` per PR. PRs
whose first triage marker is older than the 25 most recent comments are
missed — so older weeks systematically under-count. Note this in the dashboard.

---

## Triage coverage rate by week opened

The "Triage coverage rate" panel shows the percentage of PRs opened in each
week that ever received any maintainer engagement (the broader
[`is_engaged`](classify.md#is_engaged--de-facto-triaged) predicate — includes
label-adds + comments + reviews).

For each `w` in `0..5`:

```text
opened[w]   = count of PRs created in window w (open or closed)
engaged[w]  = subset of opened[w] where is_engaged(p) is true
pct[w]      = round(100 * engaged[w] / opened[w])
```

Render as a single-line chart with y-axis capped at 100. Colour the line green
when ≥ 50%, amber for 25-49%, red below 25% (or colour each data point
individually).

A declining trend means triage capacity is falling behind inflow — usually a
precursor to backlog growth.

⚠ Same data caveat as triage velocity — `is_engaged` depends on the comment
fetch, so older weeks under-count.

---

## Ready-for-review queue size (cumulative over time)

A second view on the ready queue — the **total** queue size cumulatively at end
of each week, single line for all areas combined. (The per-area version is the
chart from [`#ready-for-review-trend-by-top-areas`](#ready-for-review-trend-by-top-areas).)

For each currently-`ready for maintainer review` PR, use its most recent
`LabeledEvent` timestamp (from the
[`ready-label-timeline`](fetch.md#ready-label-timeline) fetch). For each `w`
in `0..5`:

```text
ready_count[w] = count of currently-ready PRs whose labeled_at <= w.end
```

The line is monotonically non-decreasing by construction (PRs that lost the
label are not in this dataset).

Below the chart, print the per-week delta and a 6-week growth summary.
Surfaces whether code-review capacity is keeping up with mark-ready
throughput.

---

## Ready-for-review queue by CODEOWNER

The "Ready by CODEOWNER" panel surfaces how the maintainer-review queue is
distributed across the project's `.github/CODEOWNERS` entries.

### Computation

1. Parse `.github/CODEOWNERS` into a list of `(pattern, [owners])` rules in
   declaration order. Patterns follow GitHub's CODEOWNERS glob syntax:
   - Leading `/` anchors to repo root
   - Trailing `/` matches directory contents
   - `*` matches any character except `/`
   - `**` matches any character including `/`
   - No leading `/` matches anywhere in the tree
2. For each currently-ready PR, fetch its changed file paths (use
   `pullRequest.files(first:100)` — see
   [`fetch.md#pr-changed-files-codeowners-panel`](fetch.md#pr-changed-files-codeowners-panel)).
3. For each file, find the **LAST** matching rule (GitHub's last-match-wins
   semantics). The owners of that rule are responsible for that file.
4. Per ready PR, collect the union of owners across all its files.
5. Per owner, count the *distinct* PRs they own at least one file of.
   **A PR with N owners contributes to N owner rows** — counts can sum to
   more than the total ready-PR count.

### Waiting-for-author column

For each (owner X, ready PR Y) where X is among Y's codeowners:

```text
waiting[X][Y] := X has posted at least one comment on Y AND
                 the author has neither commented nor pushed a commit
                 since X's most recent comment
```

Per owner, count the distinct PRs in `waiting[X]`. This is the subset where
the author *currently owes that specific owner a response*.

⚠ The open-PR fetch caps issue-level comments at `last:10` per PR; older
outstanding comments are systematically missed. Treat the waiting count as a
lower bound.

### "No CODEOWNERS match" row

Render an additional row at the bottom of the table for ready PRs where **no
file** matches any CODEOWNERS rule (the union of file-owner sets is empty).
These PRs are not routed to any maintainer by the CODEOWNERS file — a signal
that the project might need to extend `.github/CODEOWNERS` to cover those
paths.

### Zero-count owners

Surface owners listed in `.github/CODEOWNERS` who have 0 ready PRs in the
queue as a collapsible footnote — useful for sanity-checking that no critical
owner has been accidentally underutilised.

### Adopters without `.github/CODEOWNERS`

If the file is absent, skip this panel entirely. The skill should detect its
absence at fetch time and degrade gracefully (no panel rendered, no warning
beyond the skipped step).

---

## Health rating

Top-of-dashboard hero card. Computed as a count of fired threshold conditions:

| Condition | Issue points |
|---|---|
| `untriaged_old > 0` — any contributor non-draft `is_untriaged` PR > 4 weeks old | **2** |
| `untriaged_med > 30` — > 30 contributor non-draft `is_untriaged` PRs in 1–4 weeks bucket | **1** |
| > 100 PRs labelled `ready for maintainer review` | **1** |
| > 20 stale-triaged drafts (drafts where triage comment ≥ 7 days old AND no author response) | **1** |

Each "untriaged" condition above uses the refined
[`is_untriaged`](classify.md#is_untriaged--broad-untriaged) predicate —
so a PR carrying the `ready for maintainer review` label does **not** trigger the
health-rating points even if it lacks the literal `Pull Request quality criteria`
marker (the label is itself evidence of triage).

Sum the points and map:

| Total points | Label | Colour |
|---|---|---|
| 0 | `✅ Healthy` | green |
| 1–2 | `⚠️ Needs attention` | amber |
| ≥ 3 | `🔥 Action needed` | red |

The `>4w untriaged` condition is weighted 2x because PRs that have slipped past the 4-week mark without triage are the highest-cost failure mode — they make the project look unresponsive even though everything else may be fine. A single `>4w` PR alone reaches "needs attention".

The thresholds are intentionally conservative — most well-tended repos sit at 0 or 1 issue point. If a maintainer sees the rating regularly hitting "Action needed", that's the signal to schedule a focused triage day.

---

## Cache

Persist `area_stats`, `totals`, the per-area pressure scores, the weekly velocity buckets, and the recommendation list into the scratch cache as JSON. The cache entry is keyed by `(fetch_timestamp, cutoff)` — if the maintainer re-invokes with the same cutoff inside the 15-minute freshness window, render from cache without re-fetching.

The cache is advisory for stats. If a consumer (e.g. a wrapping `loop` that re-runs every 30 minutes) wants live numbers, invalidate the cache explicitly with `clear-cache`.
