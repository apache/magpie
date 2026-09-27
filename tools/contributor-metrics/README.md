<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [contributor-metrics](#contributor-metrics)
  - [Prerequisites](#prerequisites)
  - [Invocation](#invocation)
    - [`fetch`](#fetch)
    - [`score`](#score)
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
contributor-metrics fetch --repo <upstream> --login <handle> --end YYYY-MM-DD --months 6 \
  [--review-depth 10] [--phrases-file <file>] [--maintainers-file <file>] --out items.json
```

- `--phrases-file` — one extra pushback phrase per line (the project's `automated_pushback_phrases`), added to the generic list.
- `--maintainers-file` — whitespace-separated handles treated as maintainers in addition to `OWNER` / `MEMBER` / `COLLABORATOR` authors.
- `--review-depth` — how many of the most recent reviewed PRs get the depth query that decides *substantive*; reviews beyond it count as reviews but not as substantive.

Five GitHub searches, at most 3 × 100 results each:

| Stream | Search | Item kind |
|---|---|---|
| PRs authored | `repo:<repo> type:pr author:<login> created:<since>..<end>` | `pr` |
| Issues filed | `repo:<repo> type:issue author:<login> created:<since>..<end>` | `issue` |
| Reviews | `repo:<repo> type:pr reviewed-by:<login> updated:>=<since>` | `review` |
| Threads commented | `repo:<repo> commenter:<login> updated:>=<since>` | `thread` |
| Issues triaged | `repo:<repo> type:issue commenter:<login> -author:<login> updated:>=<since>` | `triage` |

The search string is written to a tempfile and passed as `-F q=@<file>`, so a handle never reaches a shell argument.
The 50 most recent authored PRs and issues and the 50 most recent threads get a conversation fetch for pushback candidates.

### `score`

```bash
contributor-metrics score --items items.json [--classes classes.json] [--weights weights.json] \
  [--area-prefix area:] --out metrics.json
```

- `--classes` — `{"<item id>": "P" | "R" | "C"}`, as confirmed by the calling skill; unknown ids and other values are reported in `notes` and ignored.
- `--weights` — any of `automated_contribution_weight`, `restatement_comment_weight`, `closed_after_pushback_weight`, `automated_pushback_penalty`; a missing, non-numeric or out-of-range value falls back to its default with a note.
- `--area-prefix` — the label prefix that marks a PR's area (the project's `area_label_prefix`).

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
- `caps_hit` names every stream whose search returned more results than were fetched; its counts are floors.

## Failure modes

- Invalid handle → exit 2, no `gh` call.
- `gh` error → exit 1 with the `gh` stderr.
- A stream at its cap → listed in `caps_hit`; the counts it feeds are floors.
