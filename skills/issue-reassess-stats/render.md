<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Render — emit the dashboard

Companion to [`SKILL.md`](SKILL.md). Procedural detail for Step 4:
turning the aggregate payload into HTML (default), markdown, or
terminal-tables output.

The dashboard is a **single self-contained HTML file** — inline
CSS, no JS, no external images. A maintainer opens it in any
browser without setup; a CI job can publish it as a build
artefact.

## HTML layout

Sections in order (top of page first):

### 1. Hero cards (always visible at the top)

Five inline cards with colour-coded backgrounds:

```text
+------------+------------+------------+------------+------------+
| Candidates | Still      | Fixed on   | Partial    | Unrun      |
|    N       | failing M  | master P   | fix Q      | R          |
|            | [red/amber]| [green]    | [amber]    | [amber/red]|
+------------+------------+------------+------------+------------+
```

The colour-coding follows the thresholds in
[`aggregate.md`](aggregate.md). Each card is a link that scrolls
to the relevant section below.

### 2. Health rating banner

A wide banner below the hero cards with the project-level rating:

```text
+--------------------------------------------------------------+
| HEALTH: NEEDS ATTENTION                                       |
| 2 still-failing bugs require action; 1 partial-fix surface    |
+--------------------------------------------------------------+
```

Colour matches the rating (green / amber / red).

### 3. Action panel

The dashboard's most important section. List ordered by priority
(from [`aggregate.md`](aggregate.md)'s `action_candidates`):

```text
## Action candidates

1. [<KEY>-9999] One-line title here
   - Type: Direct fix (still-failing × bug-as-advertised)
   - Age: 4 years
   - Reproducer: present at <path>
   - Next: issue-fix-workflow <KEY>-9999

2. [<KEY>-8888] Another one
   - Type: Partial fix (8/10 cases pass)
   - Age: 6 years
   - Next: issue-fix-workflow <KEY>-8888

...
```

Each candidate has a clickable tracker link via the project's
`issue_url_template`.

### 4. Closure candidates

```text
## Closure candidates

These appear safe to close:

- [<KEY>-7777] One-line title
  - fixed-on-master since <commit-sha>
  - Action: confirm + close as "Cannot reproduce" / "Fixed"

...
```

### 5. New-issue candidates (clustered)

```text
## New-issue candidates

Surfaced by cross-family probes:

### Family: range/index across type backings

- Probe surfaced: primitive-array `[0..-2]` returns [0,0] (should match List behaviour)
- Source probes: <KEY>-3974
- Action: file new issue

### Family: safe-navigation operator variants

- Probe surfaced: ?[..] vs ?. asymmetry on Maps
- Source probes: <KEY>-4674
- Action: file new issue
```

### 6. Tracker-hygiene candidates

```text
## Tracker hygiene

These warrant a metadata change rather than a fix:

- [<KEY>-2994] one-line — re-type as Improvement (feature-request-disguised-as-bug)
- ...
```

### 7. Per-component breakdown (when component data is present)

Table:

```text
| Component    | Total | Fixed | Still-failing | Unrun | Rating          |
|--------------|-------|-------|---------------|-------|-----------------|
| core         | 12    | 8     | 2             | 2     | Needs attention |
| xml          | 5     | 1     | 3             | 1     | Action needed   |
```

### 8. Oldest unresolved (top-5)

```text
## Oldest unresolved

The 5 longest-running still-failing issues:

1. [<KEY>-1234] (15 years) — one-line title
2. [<KEY>-2345] (12 years) — one-line title
...
```

### 9. Per-issue table (collapsible)

The full data, in a sortable table:

```text
| Key | Title | Class | Nature | Age | Rev | Notes |
```

Wrap in a `<details>` block (closed by default) — the dashboard's
top is for at-a-glance; the table is for the detail pass.

### 10. Methodology footer

```text
## About this campaign

- Pool: open-eol
- Run on: <default-branch> @ <short-sha>, <runtime-version>
- Run window: 2026-05-13 09:14 — 2026-05-13 10:42
- Limitations:
  - 3 of 30 verdicts marked cannot-run-extraction (Shape D / E-vague)
  - 1 verdict failed to parse (path: ...); not aggregated
```

## CSS

Inline `<style>` at the top of the HTML. Conventions:

- Sans-serif system font stack (no web fonts).
- Hero cards: flex layout, equal widths, padding 16px, rounded
  corners 8px.
- Colour palette (with light + dark theme via
  `prefers-color-scheme`):
  - Green: `#2da44e` light / `#3fb950` dark
  - Amber: `#bf8700` light / `#d29922` dark
  - Red: `#cf222e` light / `#f85149` dark
  - Background: `#ffffff` / `#0d1117`
  - Text: `#1f2328` / `#e6edf3`
- Tables: zebra striping; sortable headers (use `<details>`
  + `<summary>` for collapsibility, no JS).

The complete inline-stylesheet block lives in the reference
generator (see
[`tools/dashboard-generator/`](../../tools/dashboard-generator/));
this file specifies the contract, not the exact CSS bytes.

## Markdown fallback (`--markdown`)

The same sections in markdown, without colour-coding. The hero
cards become a 5-cell table at the top. Hero-card colour-coding
is dropped (markdown has no colour); the health-rating banner is
a bold heading. The per-issue table is the same as in HTML.

Useful when piping into a dev-list email or a maintainer-private
markdown channel.

## Tables-only fallback (`--tables-only`)

For terminal pipelines: drop the hero cards, the action panel,
the closure / new-issue / hygiene sections, and the methodology.
Emit only the per-issue table and the per-component breakdown
in plain markdown. The user gets the underlying data without the
recommendation surface.

## Recommendation rules

The action panel applies these rules in order (first match wins
per candidate; one candidate appears once):

| Rule | Condition | Action prefix |
|---|---|---|
| 1 | still-fails-same × bug-as-advertised, has reproducer | "Direct fix:" + `issue-fix-workflow` |
| 2 | still-fails-same × bug-as-advertised-partial-fix | "Partial fix:" + `issue-fix-workflow` |
| 3 | still-fails-same × feature-request-disguised-as-bug | "Tracker hygiene:" + re-type to Improvement |
| 4 | new-issue candidate from probe | "New issue:" + file in tracker |
| 5 | fixed-on-master × bug-as-advertised, clean evidence | "Closure:" + confirm and close |
| 6 | duplicate-of-resolved, canonical issue named | "Closure:" + close as duplicate |
| 7 | intended-behaviour × intended-and-documented, reporter mis-read docs | "Docs gap:" + clarifying-paragraph PR |

Rules are not exhaustive; verdicts that don't match any rule land
in the per-issue table without a recommendation prefix.

## Cross-references

- [`SKILL.md`](SKILL.md) — orchestration; this file expands
  Steps 4 and 5.
- [`aggregate.md`](aggregate.md) — produces the dashboard
  payload this step renders.
- [`tools/dashboard-generator/`](../../tools/dashboard-generator/) —
  reference implementation producing the same output
  deterministically.
- [`<project-config>/issue-tracker-config.md`](../../projects/_template/issue-tracker-config.md) —
  `issue_url_template` for clickable issue links.
