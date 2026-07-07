<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [pr-management-stats reference implementation](#pr-management-stats-reference-implementation)
  - [Prerequisites](#prerequisites)
  - [Layout](#layout)
  - [Invocation](#invocation)
  - [Configuration and vendor neutrality](#configuration-and-vendor-neutrality)
  - [Tests](#tests)
  - [Contract for the agent](#contract-for-the-agent)
  - [Parity implementations](#parity-implementations)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-management-stats reference implementation

**Capability:** substrate:analytics

**Harness:** agnostic

Deterministic reference implementation of the data-fetch +
classification contract that backs the
[`pr-management-stats`](../../skills/pr-management-stats/SKILL.md) skill.

The skill's agent-emitted render is the **default** — this script
exists for two reasons:

1. **Anti-skip insurance.** Agents under context pressure can be
   tempted to omit panels from the dashboard (line charts, CODEOWNERS
   table, triager-activity table). The skill specifies all 11 panels;
   agents must render them all. This script encodes the canonical
   data-fetch shape so the agent has a single source of truth to read
   the fields from — there is no "the skill says X, the agent guessed
   Y" drift.

2. **CI-renderable artefact.** Adopters who want a daily dashboard
   rendered by CI (rather than an interactive agent session) can run
   this script on a schedule, extend it with the full render per
   [`render.md`](../../skills/pr-management-stats/render.md),
   and publish the HTML as a build artefact or gist.

## Prerequisites

- **Runtime:** Python 3.11+, stdlib-only; run as
  `python3 reference.py` / `python3 dashboard.py`.
- **CLIs:** `gh` (GitHub CLI) for the GraphQL fetch; `bash` + `awk`
  for the optional `gen_charts.sh` SVG helper.
- **Credentials / auth:** an authenticated `gh` session
  (`gh auth status` must succeed for the viewer against `<upstream>`).
- **Network:** `api.github.com` via `gh` GraphQL. (The test suite
  stubs every `gh` call — no network.)
- **Optional:** `pytest` (dev-only) via `uv run pytest` or
  `python3 -m pytest`.

## Layout

```text
tools/pr-management-stats/
├── README.md       (this file)
├── pyproject.toml  (pins the pytest harness; the tool itself is stdlib-only)
├── reference.py    (Python implementation: fetch + classify + emit intermediates)
├── dashboard.py    (full HTML render extending reference.py — all 11 panels)
└── tests/          (pytest suite: pagination, aggregations, render, JSON parity)
```

The full HTML dashboard render (per `render.md`) lives in
[`dashboard.py`](dashboard.py); it imports the fetch + classify
primitives from `reference.py` and inlines its own SVG / CSS helpers.

The tool is **directory-portable**, not single-file or installable: the
two scripts plus their resources travel together as one directory, and
`dashboard.py` imports its sibling `reference.py` by name. Run it as a
script (`python3 dashboard.py …`) — the script's own directory is on
`sys.path[0]`, so the sibling import resolves from any working directory.
Because the directory name (`pr-management-stats`) is not a valid Python
module identifier, the tool is **not** a package and cannot be run with
`python3 -m`. The only third-party dependency is `pytest`, and that is
dev-only (for the test suite); the scripts themselves are stdlib-only.

## Invocation

```bash
# Reference (fetch + classify + JSON sidecar only)
python3 tools/pr-management-stats/reference.py \
    --repo <upstream> \
    --viewer <maintainer-handle> \
    --since 2026-04-12 \
    --out /tmp/dashboard.html

# Full dashboard (all 11 panels rendered as self-contained HTML)
python3 tools/pr-management-stats/dashboard.py \
    --repo <upstream> \
    --viewer <maintainer-handle> \
    --since 2026-04-12 \
    --out /tmp/dashboard.html
```

The script:

1. Fetches all open PRs with the **full engagement schema**
   (`comments`, `latestReviews`, `reviewThreads`, `timelineItems`
   with `LABELED_EVENT`/`READY_FOR_REVIEW_EVENT`/`CONVERT_TO_DRAFT_EVENT`).
2. Fetches closed/merged PRs since the cutoff.
3. Fetches `.github/CODEOWNERS` + changed-file paths for each
   currently-ready PR.
4. Classifies each PR per
   [`classify.md`](../../skills/pr-management-stats/classify.md) —
   `is_engaged` requires ANY maintainer touch (issue comment, review,
   review-thread comment, label add, draft conversion).
5. Writes a JSON sidecar with all the counts that feed the dashboard.

## Configuration and vendor neutrality

The default triage marker, AI footer, ready-label, and area-prefix are
example values for the reference instance these scripts were built
against — they are **not** vendor-neutral, and they do not need to be:
every one is a CLI override, so an adopter for another project supplies
their own without editing the tool. (The framework's placeholder
convention governs repo slugs and URLs in prose, not these runtime
config defaults.) Override per invocation:

```bash
python3 dashboard.py --repo <upstream> --viewer <handle> \
    --triage-marker "<your quality-criteria marker>" \
    --ai-footer "<your bot footer>" \
    --ready-label "<your ready label>" \
    --area-prefix "<your area label prefix>"
```

When pagination is cut short (a `gh` error, a rate limit, or the page
cap is reached), the run does not silently publish a truncated view: a
visible **INCOMPLETE DATA** banner is added to the HTML and `partial:
true` is written to the JSON sidecar. Transient `5xx` / `RATE_LIMITED`
failures are retried once with backoff before that happens.

## Tests

```bash
# from the tool directory
uv run pytest            # or: python3 -m pytest
```

The suite is stdlib + `pytest` only and stubs all `gh` calls — no
network access:

- `tests/test_pagination.py` — guards the cursor-pagination fix, the
  retry/backoff path, and the partial-fetch signal.
- `tests/test_aggregations.py` — pure aggregation functions
  (`compute_hero_counts`, `compute_pressure_by_area`,
  `compute_recommendations`, weekly velocity).
- `tests/test_classify_partial.py` — the explicit partial closed-PR
  classify contract.
- `tests/test_html_render.py` — render helpers, including the
  incomplete-data banner toggle and HTML escaping.
- `tests/test_json_parity.py` — runs both `reference.py` and
  `dashboard.py` over one fixture and asserts the dashboard sidecar is a
  superset of reference's with identical values on every shared key.

## Contract for the agent

When the agent invokes the skill, it MUST:

- Use the GraphQL templates from [`fetch.md`](../../skills/pr-management-stats/fetch.md) verbatim. **In particular, the open-PRs query MUST include `reviewThreads` and `latestReviews` and `timelineItems`** — without those, the `is_engaged` predicate is undercounted and untriaged numbers blow up artificially. (Earlier iterations of `fetch.md` claimed those fields were not needed for stats; that was a documentation bug and has been corrected.)
- Implement ALL 11 sections per [`render.md`](../../skills/pr-management-stats/render.md). Skipping panels (e.g. dropping the line charts, CODEOWNERS table, triager-activity table) is **not** an acceptable simplification.
- If panel data is unavailable, the panel renders a stub with a one-line explanation of WHY the data is missing — never omit a section silently.

## Parity implementations

`reference.py` provides fetch + classify only. `dashboard.py`
extends it with the aggregation + HTML emission for all 11 panels
declared in `render.md`, and is the recommended path for CI-rendered
dashboards. Adopters who want a different language target are
welcome to add additional parity implementations.

## Cross-references

- [`pr-management-stats/SKILL.md`](../../skills/pr-management-stats/SKILL.md) — skill entry point.
- [`pr-management-stats/classify.md`](../../skills/pr-management-stats/classify.md) — `is_engaged` / `is_triaged` / `is_untriaged` predicates.
- [`pr-management-stats/fetch.md`](../../skills/pr-management-stats/fetch.md) — GraphQL templates.
- [`pr-management-stats/aggregate.md`](../../skills/pr-management-stats/aggregate.md) — per-panel computations.
- [`pr-management-stats/render.md`](../../skills/pr-management-stats/render.md) — dashboard layout, recommendation rules.
- [`tools/dashboard-generator/`](../dashboard-generator/) — sibling reference implementation for `issue-reassess-stats`.
