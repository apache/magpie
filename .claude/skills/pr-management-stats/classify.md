<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Classify

Per-PR state determination for the stats tables. Mirrors the triage-detection logic in the triage-marker rows in [`pr-management-triage/classify-and-act.md`](../pr-management-triage/classify-and-act.md) (rows 3–4 — `already_triaged`) — the two skills must agree on what "triaged" means. Any rule change here must ship simultaneously in `pr-management-triage`.

Classification is pure function of state from [`fetch.md`](fetch.md) — no network calls, no writes.

---

## Triage tiers — definitions

The dashboard surfaces four distinct triage-state categories side-by-side
because the strict marker-only definition under-counts actual triage activity
and conflates "no maintainer touched this" with "no maintainer left the
canonical template." All four predicates apply to a single PR; they overlap
deliberately (see the implication chains below).

### `is_triaged` — *Quality-Criteria-triaged*

```text
is_triaged(pr) :=
    EXISTS comment c IN pr.comments
      WHERE c.authorAssociation IN (OWNER, MEMBER, COLLABORATOR)
        AND c.body CONTAINS "Pull Request quality criteria"
        AND (c.createdAt > head_commit.committedDate
             OR head_commit.committedDate > c.createdAt)   # see [Triage marker](#triage-marker)
```

**What the literal marker is:** the **substring `Pull Request quality
criteria`** — this is the visible link text in the canonical triage-comment
template that every `pr-management-triage` action body carries (see
[`pr-management-triage/comment-templates.md`](../pr-management-triage/comment-templates.md)).
The classifier scans every comment's `body` (NOT `bodyText` — the latter
strips HTML comments, see [Both marker forms count](#both-marker-forms-count)
below) for the exact substring. The string is also accepted in an HTML-comment
form left by the legacy `breeze pr auto-triage` command.

The marker is a **single point of failure** — rename the link text in the
comment template and this detector silently stops counting. Adopters can
customise the URL the link points to via
[`<project-config>/pr-management-triage-comment-templates.md`](../../../projects/_template/pr-management-triage-comment-templates.md)'s
`quality_criteria_url`, but the link **text** must remain `Pull Request
quality criteria` verbatim.

### `is_engaged` — *de-facto triaged*

```text
is_engaged(pr) :=
    EXISTS comment c IN pr.comments
      WHERE c.authorAssociation IN (OWNER, MEMBER, COLLABORATOR)
        AND NOT is_bot(c.author.login)
```

Plus the same predicate applied to `pr.latestReviews` (any maintainer review)
and to `LabeledEvent` (any maintainer who added the `ready for maintainer
review` label).

The broader "a maintainer touched this PR at some point" definition. Catches
review-thread comments, design discussions, label-adds, hand-typed feedback,
and so on — all the engagement modes that don't include the literal marker
substring. **`is_engaged` is a superset of `is_triaged`**: every
Quality-Criteria-triaged PR is also engaged, but not vice-versa.

The terminology in the dashboard:

- **De-facto triaged** = engaged but not Quality-Criteria-triaged.
  Formally: `is_engaged(pr) AND NOT is_triaged(pr)` — the
  `defacto_triaged` counter aggregates this set.

### `is_ai_triaged` — *AI-assisted triage*

```text
is_ai_triaged(pr) :=
    EXISTS comment c IN pr.comments
      WHERE c.authorAssociation IN (OWNER, MEMBER, COLLABORATOR)
        AND c.body CONTAINS "AI-assisted triage tool"
```

A PR received at least one maintainer comment whose body contains the
**AI-attribution footer substring** (`AI-assisted triage tool`). Every
`pr-management-triage` comment template (draft / comment / ping /
request-author-confirmation / close-comment etc.) ends with this footer
verbatim — so the detector counts any PR whose triage included a skill-drafted
comment.

This predicate is **independent of** `is_triaged` and `is_engaged`:

- An AI-drafted draft+comment includes the `Pull Request quality criteria`
  link → both `is_triaged` and `is_ai_triaged` fire.
- An AI-drafted **ping** or **request-author-confirmation** uses a different
  template that does NOT include the criteria link → `is_engaged` and
  `is_ai_triaged` fire but `is_triaged` does NOT.
- A maintainer's hand-typed comment in the criteria-template form (rare —
  this happens when a maintainer manually pastes the link text without the
  skill) → `is_triaged` and `is_engaged` fire but `is_ai_triaged` does NOT.

The implication chains:

```text
is_triaged(pr)    ⇒ is_engaged(pr)         # marker requires maintainer comment, which requires engagement
is_ai_triaged(pr) ⇒ is_engaged(pr)         # AI footer requires maintainer comment, which requires engagement
is_triaged(pr)    ⇎ is_ai_triaged(pr)      # independent — see cases above
```

### `is_untriaged` — *broad untriaged*

```text
is_untriaged(pr) :=
    NOT is_engaged(pr)                                # broadest — no maintainer touched it
    AND author_association NOT IN (OWNER, MEMBER, COLLABORATOR)
    AND NOT is_bot(pr.author.login)
    AND `ready for maintainer review` NOT IN labels(pr)
```

**Key change from earlier iterations:** uses `NOT is_engaged` (not `NOT
is_triaged`). Combining strict-untriaged with de-facto-triaged double-counted
PRs that maintainers had touched: a strict-only definition flags a PR as
untriaged even when a maintainer left detailed inline review feedback, just
because the feedback didn't include the canonical marker string. The broader
predicate correctly counts only PRs with **zero maintainer engagement**.

Concrete impact on a large `<upstream>` queue: the strict-only count gave
72 untriaged non-drafts; tightening to `NOT is_engaged` brings it to 47
(a 35% reduction). The 25 PRs that drop out had ≥1 maintainer comment but
no template marker — they're de-facto triaged.

The age-bucketed variants used by `aggregate.md`:

```text
is_untriaged_old(pr) := is_untriaged(pr) AND age_bucket(pr) == ">4w"
is_untriaged_med(pr) := is_untriaged(pr) AND age_bucket(pr) IN {"1-4w"}
```

The age uses the `last_author_interaction` defined in the
"Age bucket" section below.

### Side-by-side summary

| Tier | Predicate | Means | Dashboard card |
|---|---|---|---|
| Quality-Criteria-triaged | `is_triaged` | maintainer posted the literal `Pull Request quality criteria` link | **Quality Criteria triaged** (hero row 2, blue) |
| De-facto triaged | `is_engaged AND NOT is_triaged` | maintainer engaged but no marker | **De-facto triaged** (hero row 2, amber — the gap signal) |
| AI-triaged | `is_ai_triaged` | comment with the AI-attribution footer | **AI-triaged** (hero row 2, purple — accounting) |
| Engaged (overall) | `is_engaged` | union of the above two | not a card on its own; equals `triaged + defacto_triaged` |
| Untriaged | `is_untriaged` | NOT engaged + contributor + non-bot + not ready-labelled | **Untriaged non-drafts** (hero row 1) |

The number of PRs in each tier sums to a clean partition of the contributor
non-draft pool minus the ready-labelled set:

```text
contributor_nondraft_not_ready =
    triaged_nondraft +              # Quality-Criteria-triaged (`is_triaged`)
    defacto_triaged_nondraft +      # engaged but no marker
    untriaged_nondraft              # no maintainer engagement
```

The `transitional` cases (e.g. a freshly-engaged PR whose triage marker
hasn't been posted yet) are not a separate category; they sit in
de-facto-triaged until they pick up the marker or the ready label.

---

## Triage marker

A PR is *triaged* when it has at least one comment that:

- is authored by `OWNER` / `MEMBER` / `COLLABORATOR` (`authorAssociation`)
- contains the literal string `Pull Request quality criteria` in the comment's **raw `body`** (NOT `bodyText` — see below)
- has `createdAt` **after** the PR's last commit's `committedDate` **at the time the comment was posted** (otherwise the triage pre-dates the current code and is stale). **Exception:** if the PR author subsequently pushes a commit *after* the triage comment (`last_commit.committedDate` > `triage_comment.createdAt`), do **not** treat the marker as stale — that commit is evidence the author responded to triage feedback. Classify as `triaged_responded` (see [Triaged sub-states](#triaged-sub-states) below) rather than reverting to `untriaged`.

### Both marker forms count

Two flavours of the marker circulate in `<upstream>` and both must be detected:

| Source | Form of marker in the comment body | Where it appears |
|---|---|---|
| `pr-management-triage` skill / removed `breeze pr auto-triage` — violations path | `[Pull Request quality criteria](https://github.com/…)` visible link | violations-style draft / comment / close bodies |
| Removed `breeze pr auto-triage` — staleness path (legacy comments only) | `<!-- Pull Request quality criteria -->` **HTML comment** appended to the body | staleness-close / stale-workflow / inactive-open comments posted before the command was removed |

The HTML-comment form is invisible in the GraphQL `bodyText` field (bodyText strips HTML comments). Fetching `body` preserves it, and a single substring match for `Pull Request quality criteria` catches both the visible link and the hidden HTML marker. The `pr-management-triage` skill currently only emits the visible-link form, but the HTML-comment form remains on PRs that were triaged before the breeze command was removed, so the detector must continue to handle both.

This is why [`fetch.md`](fetch.md) specifies `body` (not `bodyText`) in the comments subfield. A previous iteration of the skill used `bodyText` and missed ~10% of triaged PRs on `<upstream>` — specifically, the ones that had only the staleness-style legacy auto-triage comment.

### Rationale — "any maintainer", not "viewer only"

If another maintainer already triaged the PR, the stats should count it as triaged. Using `viewer` here would under-count triage coverage on a team with multiple active triagers. The same applies to legacy staleness comments left by the now-removed `breeze pr auto-triage` command: whoever ran the tool (the "actor") is the marker's author, and it's still a legitimate maintainer triage.

---

## Triaged sub-states

Once a PR is triaged, it's either *waiting* for the author or the author has *responded*:

### `triaged_waiting`

- PR is triaged (above)
- The PR's `author.login` has **not** commented after the triage comment's `createdAt`

### `triaged_responded`

- PR is triaged
- The PR's `author.login` has commented at least once after the triage comment's `createdAt`

A PR pushed a new commit after the triage counts as "responded" too — treat a post-triage commit the same as a post-triage comment for this test (the commit's `committedDate` serves as the author-activity timestamp).

---

## Waiting sub-states — AI-only vs maintainer-response

The dashboard's "Triage funnel" panel splits the broader notion of "waiting on the author" into two **mutually exclusive** buckets, because the priority differs: an unresponded *manual* maintainer comment is a higher-priority "the author owes a maintainer a reply" signal than an unresponded *AI-drafted* comment.

The split is computed over the same comment scan that produces `triaged_waiting` / `triaged_responded`, but extended to cover ALL maintainer comments (not just ones containing the QC marker) and partitioned by whether the comment contains the AI-attribution footer.

Define `last_author_activity` as the latest of:

- PR's last commit `committedDate`
- The most recent comment by `pr.author.login`

Then for each *maintainer* (`OWNER`/`MEMBER`/`COLLABORATOR`, not-`is_bot`) comment with `createdAt > last_author_activity`, classify the comment as AI vs manual:

- **AI-drafted** — body contains the [`is_ai_triaged`](#is_ai_triaged--ai-assisted-triage) footer substring
- **Manual** — body does not contain the footer

### `waiting_for_manual_response`

```text
waiting_for_manual_response := EXISTS comment c WHERE
    c is a maintainer comment AND
    c.createdAt > last_author_activity AND
    c is NOT AI-drafted
```

### `waiting_for_ai_only`

```text
waiting_for_ai_only := (NOT waiting_for_manual_response)
    AND EXISTS comment c WHERE
        c is a maintainer comment AND
        c.createdAt > last_author_activity AND
        c IS AI-drafted
```

The `NOT waiting_for_manual_response` clause makes these two predicates a clean partition over contributor non-draft PRs — a PR with both an AI-drafted and a manual unresponded comment counts only in the manual bucket (higher priority).

### Why this split matters

The `triaged_waiting` count alone conflates two very different states:

- **Author owes the maintainer a reply** (manual review feedback unanswered) — high priority, real review work blocked.
- **Author hasn't responded to an AI-drafted triage comment** (CI complaints, generic violations note) — lower priority, may not even merit a reply if the author is mid-fix.

Splitting them lets the maintainer focus stale-sweep / ping efforts on the high-priority subset.

### Caveats

- Both predicates rely on `pr.comments(last:10)` — older outstanding comments on chatty PRs may be missed. Lower-bound numbers.
- The footer-substring match (`AI-assisted triage tool`) is configurable per [`<project-config>/pr-management-config.md`](../../../projects/_template/pr-management-config.md)'s `ai_attribution_substring`. The default works as long as the project doesn't customise the footer text.

---

## Drafted by triager

A PR is *drafted by triager* when the viewer (or any maintainer) converted the PR to draft *after* having posted the triage comment. Two ways to detect this:

### Full signal — `ConvertToDraftEvent`

Query the PR's timeline and find the most recent `ConvertToDraftEvent`:

```graphql
pullRequest(number: $n) {
  timelineItems(last: 50, itemTypes: [CONVERT_TO_DRAFT_EVENT]) {
    nodes {
      ... on ConvertToDraftEvent {
        actor { login }
        createdAt
      }
    }
  }
}
```text

If `actor.login` is the viewer (or any maintainer login tracked in the session cache) and `createdAt >= triage_comment_createdAt`, mark the PR as `drafted_by_triager` with `drafted_at = createdAt`.

This is the accurate signal but it's a per-PR query. Run it only when the maintainer asks for the `draft_age_buckets` column (render it in Table 2 by default).

### Cheaper heuristic — "is draft + has triage marker"

If you want to skip the timeline query, approximate: treat the PR as `drafted_by_triager` when both `isDraft == true` and `is_triaged` are true. This misclassifies PRs that were already draft *before* triage (e.g. the author opened as draft and then got triaged for a quality issue), but those are rare enough that the approximation is usually fine for a quick stats run.

Mark which path the skill used in the legend output (`drafted by triager (heuristic)` vs `drafted by triager (timeline-confirmed)`) so the maintainer knows the cost/accuracy trade-off.

---

## Age bucket

The age of a PR for bucketing is the time since the author's *last interaction*:

```text
last_author_interaction = max(
    most_recent_comment.createdAt where comment.author.login == pr.author.login,
    last_commit.committedDate,
    pr.createdAt,
)
```text

Why `max`: a PR freshly opened without activity still needs *some* age signal — `createdAt` is the floor. A PR where the author commented after pushing a commit should be counted by the comment timestamp, not the commit.

Bucket boundaries (delta from `<now>`):

| Bucket label | Range | Meaning |
|---|---|---|
| `<1d` | 0–24h | fresh push / just active |
| `1-7d` | 24h–7 days | within the current review week |
| `1-4w` | 7–28 days | inside the triage-response window |
| `>4w` | over 28 days | stale; needs maintainer intervention |

Same boundaries are used for the `draft_age_buckets` column (time since the triager converted the PR to draft).

Four buckets is the deliberate minimum — each one maps to a distinct maintainer decision (don't bother / watch / nudge / act). Finer splits like `1-3d` vs `3-7d` crowd the table without changing what the maintainer does with the numbers. Keep the bucket labels and boundaries in sync with the column headers in [`render.md`](render.md) — the tables read the labels straight off this list.

---

## Contributor vs collaborator

A PR is by a *contributor* (for the `Contrib.` column) when:

```text
authorAssociation NOT IN (OWNER, MEMBER, COLLABORATOR)
```text

Everything else (including `FIRST_TIME_CONTRIBUTOR`, `FIRST_TIMER`, `CONTRIBUTOR`, `NONE`) counts as contributor. Bots (`[bot]`-suffixed logins or `dependabot` / `github-actions`) are NOT contributors — they're a separate class and should be excluded from the open-PR stats entirely. Filter bots at fetch time, not at classification time, so the denominator in every percentage excludes them.

---

## Ready for review

The `Ready` column counts PRs carrying the `ready for maintainer review` label. That's it — no state inference. The label is the signal.

---

## Stats-only vs action-only triage

The strict `is_triaged` definition (the literal marker scan, [Triage marker](#triage-marker)
above) remains the source of truth for the **action-related** flows
(`pr-management-triage` row 3-4 detection, sweep 1a's "stale triaged drafts"
threshold). The broader `is_engaged` definition is **stats-only** — it does
not gate any mutation. This keeps the action-flow conservatism while letting
the dashboard surface the fuller picture.

For the configurable AI-attribution detection substring, adopters can override
[`<project-config>/pr-management-config.md`](../../../projects/_template/pr-management-config.md)'s
`ai_attribution_substring` field; the framework defaults to
`AI-assisted triage tool`. The literal substring is a single point of failure
— keep it identical between the comment templates and this detector.

---

## `is_bot` — author is a recognised bot

```text
is_bot(login) :=
    login.lower() ends with "[bot]"
    OR login.lower() IN {dependabot, renovate, github-actions}
```

Bot PRs are a **separate dashboard category** counted as `bot_authored` —
they don't merge into `contributors` or `collaborators`, and they don't trip
the untriaged or engaged predicates. Their lifecycle is independent: they
follow automated update / review cycles and are reviewed-and-merged by
maintainers without going through the triage funnel. Surfacing them in their
own count keeps the contributor backlog signal clean.

Adopters with project-specific bots not on this list — e.g. a release-bot or
a CI-helper bot — should extend the `is_bot` match via
[`<project-config>/pr-management-config.md`](../../../projects/_template/pr-management-config.md)'s
`bot_logins` setting (a list of additional logins to recognise; the framework
defaults always apply).

---

## Responded before close (Table 1 only)

Table 1's `Responded` column measures, per area, how many triaged PRs got an author reply *before* they were closed or merged. For a PR in the closed-since set:

```text
responded_before_close =
    is_triaged AND
    exists(comment by pr.author where comment.createdAt > triage_comment.createdAt AND comment.createdAt <= pr.closedAt)
```text

Count the PR as responded if it has the marker AND an author comment between triage and close. `%Responded` = responded / triaged_total for that area.

---

## Pressure weight

Per-PR helper used by [`aggregate.md#pressure-score`](aggregate.md#pressure-score). Returns the integer weight a single contributor PR contributes to its area's pressure score. Pure function of fields already populated above; no extra fetches.

```text
def pressure_weight(pr) -> int:
    if pr.author_association in ("OWNER", "MEMBER", "COLLABORATOR"):
        return 0                       # collaborator PRs don't add maintainer pressure
    if pr.is_ready_for_review:
        return 1                       # waiting on maintainer review — soft pressure
    if pr.is_triaged_waiting and (now - pr.triage_ts) >= 7 days:
        return 2                       # stale triaged — sweep candidate
    if pr.is_draft:
        return 0                       # author's court
    # untriaged non-draft
    age = now - pr.last_author_at
    if age >= 28 days: return 5
    if age >= 7 days:  return 3
    return 1
```text

The first-match-wins ordering matters: a ready-for-review PR that's also a stale triaged draft scores 1 (ready takes precedence — once it has the label, the maintainer is the gate, not the author). Keep this function in lockstep with the table in [`aggregate.md#pressure-score`](aggregate.md#pressure-score).

---

## Re-classification stability

The stats run must produce the same numbers when invoked twice on the same cached state. Keep the classification pure (no time-dependent randomness) and anchor age-bucket cutoffs to `<now>` captured at fetch start, not at render time. Otherwise a slow run drifts PRs across buckets between fetch and render.

This applies to `pressure_weight` too — the `7d` / `28d` thresholds are computed from the same `<now>` as the age buckets, so a PR that's exactly on a bucket boundary scores deterministically across re-runs of the same fetch.
