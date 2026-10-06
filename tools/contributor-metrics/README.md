<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [contributor-metrics](#contributor-metrics)
  - [Prerequisites](#prerequisites)
  - [Invocation](#invocation)
    - [`fetch`](#fetch)
    - [`score`](#score)
    - [`floors`](#floors)
  - [Output schema](#output-schema)
  - [Failure modes](#failure-modes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# contributor-metrics

**Capability:** substrate:analytics

**Kind:** implementation

**Vendor:** GitHub

**Harness:** agnostic

Counts a contributor's activity on `<upstream>` over a window — PRs opened and merged, reviews, substantive reviews, issues filed, issues triaged, threads commented — splits it by area label, and applies the automated-work weights and pushback penalty defined in [`automated-contributions.md`](../../plugins/magpie-contributor-growth/skills/nomination/automated-contributions.md).

It is the deterministic half of the contributor-growth skills.
`fetch` flags pushback *candidates* — a maintainer comment that contains a known pushback phrase — but never decides: the calling skill reads each candidate, confirms or rejects it by the rules in `automated-contributions.md`, classifies restatements, and hands the classes back to `score`.
Comment bodies never leave `fetch`; its output holds links and flags only.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv` (`uv run --directory tools/contributor-metrics contributor-metrics …`); stdlib-only, no third-party dependencies.
- **CLIs:** `uv`; `gh` — the script shells out to it for all GitHub access.
- **Credentials / auth:** an authenticated `gh` session (`gh auth status` must pass).
- **Network:** `api.github.com` via `gh`.

## Invocation

### `fetch`

```bash
contributor-metrics fetch --repo <upstream> --login <handle> --end YYYY-MM-DD (--months 6 | --since YYYY-MM-DD) \
  [--substantive-body-chars 100] [--substantive-line-comments 1] \
  [--phrases-file <file>] [--maintainers-file <file>] [--cache-dir <dir>] --out items.json
```

- `--since` — the window start; it overrides `--months` for a window that is not a whole number of months, such as one trimmed to the repository's creation date.
  An invalid date, or one after `--end`, exits `2` before any `gh` call.
- `--substantive-body-chars` / `--substantive-line-comments` — a reviewed PR is *substantive* when one of the contributor's reviews on it has a body longer than the first or at least the second many line comments; defaults `100` and `1`.

- `--phrases-file` — one extra pushback phrase per line (the project's `automated_pushback_phrases`), added to the generic list.
- `--maintainers-file` — whitespace-separated handles treated as maintainers in addition to `OWNER` / `MEMBER` / `COLLABORATOR` authors.
- `--cache-dir` — where fetched items are cached per repository, handle, window, phrases, roster and substantive thresholds; default `$TMPDIR/contributor-metrics-cache`. A second fetch with the same key reads the cache and makes no `gh` call. The cache holds links and flags only, never comment bodies.
  Weights, penalty and area prefix are applied by `score`, not cached, so changing them needs no refetch; anything that changes on GitHub after a fetch (a new label, a late comment) is picked up only with `--refresh`, or by deleting the cache directory.
- `--refresh` — ignore any cached result for this key and fetch again.
- `--repo` must be `owner/name`; anything else exits `2` before any `gh` call.

Every item is dated by the contributor's own activity and must fall inside `[since, end]`:

| Stream | Source | Dated by | Item kind |
|---|---|---|---|
| PRs authored | search `repo:<repo> type:pr author:<login> created:<since>..<end>` | creation; *merged* only when `mergedAt` ≤ `end` | `pr` |
| Issues filed | search `repo:<repo> type:issue author:<login> created:<since>..<end>` | creation | `issue` |
| Reviews | `contributionsCollection` between `since` and `end`, one item per reviewed PR | the first review in the window; *substantive* when any of those reviews has a body over 100 characters or a line comment (or the configured thresholds) — every reviewed PR is checked | `review` |
| Threads commented | search `repo:<repo> commenter:<login> created:<=<end> updated:>=<since>` | the contributor's first comment in the window; a thread with none is dropped | `thread` |
| Issues triaged | search `repo:<repo> type:issue commenter:<login> -author:<login> created:<=<end> updated:>=<since>` | as threads | `triage` |

Searches fetch at most 3 × 100 results; a stream that returned more is listed in `caps_hit`.
The 100 most recent threads of each kind are dated from their conversation; older ones keep their last-update date and are reported in `notes`.
The 50 most recent authored PRs and issues and the 20 most recent reviewed PRs get a conversation fetch for pushback candidates; older items, and triage threads beyond the thread budget, get none and keep full weight — the budget errs toward the contributor, as `automated-contributions.md` requires.
Item ids are per kind: the same PR can appear as `pr-N`, `review-N`, `thread-N` and `triage-N`, and the calling skill classifies each id it means to discount.
The search string is written to a tempfile and passed as `-F q=@<file>`, so a handle never reaches a shell argument.
Rate-limit and transient `gh` errors are retried with exponential backoff (up to six attempts); any other error exits `1`.

### `score`

```bash
contributor-metrics score --items items.json [--classes classes.json] [--weights weights.json] \
  [--area-prefix area:] [--since YYYY-MM-DD] [--timeline-kinds pr,issue,review,thread] --out metrics.json
```

- `--classes` — `{"<item id>": "P" | "R" | "C"}`, as confirmed by the calling skill; unknown ids and other values are reported in `notes` and ignored.
- `--weights` — any of `automated_contribution_weight`, `restatement_comment_weight`, `closed_after_pushback_weight`, `automated_pushback_penalty`; a missing, non-numeric or out-of-range value falls back to its default with a note.
- `--area-prefix` — the label prefix that marks a PR's area (the project's `area_label_prefix`).
- `--since` — score only a sub-window of what was fetched, e.g. the 6-month window from a 12-month fetch.
- `--timeline-kinds` — the item kinds the monthly `timeline` counts, comma-separated; default every kind.

### `floors`

```bash
contributor-metrics floors --rows rows.json [--today YYYY-MM-DD] [--halflife 2] [--min-elected 5] [--relaxation 0.75] --out floors.json
```

Proposes threshold floors from measured past nominations, for `contributor-calibrate`.
`rows.json` is a list of `{"target": "committer" | "pmc", "outcome": "elected" | "deferred" | "withdrawn", "vote_date": "YYYY-MM-DD", "metrics": {"<metric>": <number>}, "capped": ["<metric>"]}`.

- Rows are weighted by recency, `0.5 ** (age_years / halflife)`; withdrawn rows are ignored.
- The weighted percentile is the smallest value whose cumulative weight reaches the percentile's share of the total weight.
- The floor is the weighted 25th percentile of elected rows multiplied by `--relaxation` (default `0.75`), rounded down.
  The relaxation is deliberate: the floors sit well below what the project has elected, so the lists built on them surface more people than the governing body would pick, and the decision stays with that body.
- When the unrelaxed weighted 25th percentile, rounded down, is at or below the weighted median of deferred rows, the metric is *evidence only* (floor `0`).
- A target with fewer than `--min-elected` elected rows gets no floors.
- A capped value is left out of that metric's distribution and counted in `excluded_capped`.

Output: `{"floors": {target: {metric: int}}, "evidence_only": {target: [metric]}, "no_floors_for": [target], "distribution": {...}, "relaxation": float, "notes": [...]}`.

## Output schema

`metrics.json`:

```json
{
  "window": {"since": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
  "weights": {"automated_contribution_weight": 0.25, "restatement_comment_weight": 0.0, "closed_after_pushback_weight": 0.0, "automated_pushback_penalty": 0.25},
  "notes": ["..."],
  "metrics": {
    "prs_opened": {"raw": 0, "discounted": 0.0, "penalty": 0.0, "adjusted": 0.0},
    "prs_merged": {"raw": 0, "discounted": 0.0, "penalty": 0.0, "adjusted": 0.0},
    "reviews_total": {"raw": 0, "discounted": 0.0, "penalty": 0.0, "adjusted": 0.0},
    "reviews_substantive": {"raw": 0, "discounted": 0.0, "penalty": 0.0, "adjusted": 0.0},
    "issues_filed": {"raw": 0, "discounted": 0.0, "penalty": 0.0, "adjusted": 0.0},
    "issues_triaged": {"raw": 0, "discounted": 0.0, "penalty": 0.0, "adjusted": 0.0},
    "threads_commented": {"raw": 0, "discounted": 0.0, "penalty": 0.0, "adjusted": 0.0}
  },
  "merge_rate": {"raw": null, "adjusted": null},
  "areas": [{"area": "area:x", "prs": {"raw": 0, "adjusted": 0.0, "share": 0.0}, "reviews": {"raw": 0, "adjusted": 0.0, "share": 0.0}}],
  "area_breadth": {"raw": 0, "adjusted": 0},
  "timeline": {"YYYY-MM": 0},
  "flagged": [{"id": "pr-1", "url": "...", "class": "P", "weight": 0.25, "penalised": true}],
  "caps_hit": []
}
```

- `discounted` is the sum of item weights; `penalty` is `automated_pushback_penalty` times the distinct threads classed `P` or `C` in that count; `adjusted` is `max(0, discounted − penalty)`.
- Area shares, area breadth and merge rate use item weights without the penalty.
- An area's share is its weight over **all** merged PRs (or reviews) in the window; work with no area label is reported as an `(unlabelled)` row, and a PR with two area labels counts toward both, so shares can add up to more than 100 %.
- The penalty is applied once per thread **in each count** the thread appears in — a pushed-back PR lowers opened, merged and threads-commented alike, because each count is compared with its own floor.
- `caps_hit` names every stream whose search returned more results than were fetched; its counts are floors.

## Failure modes

- Invalid handle → exit 2, no `gh` call.
- `gh` error → exit 1 with the `gh` stderr.
- A stream at its cap → listed in `caps_hit`; the counts it feeds are floors.
