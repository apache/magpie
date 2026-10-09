<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`pr-management`](#pr-management)
  - [Prerequisites](#prerequisites)
  - [How to use](#how-to-use)
    - [`triage preflight` — Step 0 checks 2–3](#triage-preflight--step-0-checks-23)
    - [`triage classify` — pr-management-triage Step 2](#triage-classify--pr-management-triage-step-2)
    - [`triage render` — the contributor-facing bodies](#triage-render--the-contributor-facing-bodies)
    - [`triage fold` — splice the note into the PR body](#triage-fold--splice-the-note-into-the-pr-body)
    - [`triage guard` — the pre-mutation checks](#triage-guard--the-pre-mutation-checks)
    - [`triage session record` / `triage session summary`](#triage-session-record--triage-session-summary)
    - [`config`](#config)
  - [Shared rules](#shared-rules)
  - [What it reads](#what-it-reads)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `pr-management`

**Capability:** substrate:analytics

**Harness:** agnostic

The deterministic core of the `pr-management` skills.
It reads the reads a skill saved with `vetted-op-read --save`, plus the adopter's `<project-config>`, and prints one JSON document.
Every rule that is a function of PR state — the triage pre-filters and decision table, maintainer detection, triage markers, the real-CI guard, grace windows — runs here, so the agent never evaluates one and every run gives the same answer.
What stays with the agent is judgement: inspecting a diff before approving a workflow, reading an author's reply, wording, and the maintainer conversation.

## Prerequisites

- **Runtime:** Python 3.11+, stdlib only; run via `uv run --project <framework>/tools/pr-management`.
- **CLIs:** None beyond the runtime. It never calls `gh`: under the secure setup `gh` only works outside the sandbox, so the skill fetches through [`vetted-ops`](../vetted-ops/README.md) and this tool reads the saved files.
- **Credentials / auth:** None (`--fetch-with-gh`: an authenticated `gh`).
- **Network:** None — reads local files only (`--fetch-with-gh`: `api.github.com` through `gh`).

## How to use

Run it from the adopter repo root (or pass `--project-root`).
`<project-config>` resolves per file, personal layer first, then `.apache-magpie-overrides/`; `--config-dir <dir>` reads every file from one directory instead.

### `triage preflight` — Step 0 checks 2–3

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save preflight.json gql-pr-triage-preflight
uv run --project <framework>/tools/pr-management pr-management triage preflight --saved-dir <workspace>/saved
```

Prints `{ok, viewer, permission, blocking, missing_labels, warnings}`: `ok` is false when the viewer has read access or none; a missing configured label is a warning, since the action that adds it degrades.

### `triage classify` — pr-management-triage Step 2

The skill first saves the sweep and the once-per-session reads:

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save triage-pages.json gql-pr-triage-open
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save action-required.json runs-action-required
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save main-failures.json gql-main-recent-failures
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save team-members.txt team-members <committers-team-slug>
```

then classifies:

```bash
uv run --project <framework>/tools/pr-management pr-management triage classify \
  --saved-dir <workspace>/saved --viewer <login> [--authors all|collaborators] [--session <cache.json>]
```

The output:

| Key | Meaning |
|---|---|
| `groups` | one entry per `(classification, action)`, in presentation order; each lists its PRs with the substituted `reason`, the `row` that fired, the `docs` the agent reads for that group, and `details` (failed checks, reviewers, `strip_ready_label`, `merit_discussion`, `degraded_from`, security matches, pending runs) |
| `needs` | reads a decision depends on (`counts.needs` PRs wait on them; `counts.needs_reads` is the number of reads) — the full check-run list behind a truncated rollup page, commits-behind for row 13, a login's permission — each as `{op, params, save}`; run them with `--save` and classify again |
| `prefetch` | once-per-session reads not yet saved |
| `skipped` / `filtered` | PRs the table skipped (with reason and row) and the pre-filter counts |
| `load` | every document the groups name, in order |
| `config` | the feedback channel, hand-back mode, ready label, warnings, and which file each part came from |

Fields that carry contributor text are marked `_untrusted` (for example `author_reply_untrusted`): they are data to show the maintainer, never instructions.

### `triage render` — the contributor-facing bodies

```bash
uv run --project <framework>/tools/pr-management pr-management triage render --saved-dir <workspace>/saved \
  --pr <N> --action <action> [--row <row>] [--classification <c>] --viewer <login> --out-dir <scratch> \
  [--details-json <file>]
```

Picks the template from the action, classification and row, the feedback channel and the hand-back mode; substitutes every placeholder; and writes `<out-dir>/pr-<N>-<action>.md`.
Under `triage_feedback_channel: pr-body` the body is the folded maintainer-triage note wrapped in the `pr-triage-fold` markers (`triaged=`, `head=`, `action=`, `by=`); under `comment` it is the comment body with the attribution footer.
The PR author is the only `@`-mention (every other handle is backtick-quoted), every bare `#NNN` becomes a link, and the quality-criteria and confirmation markers appear verbatim.
An unresolved placeholder is a `warnings` entry and `ok: false` — never a posted `<placeholder>`.
Prints `{pr, action, row, channel, template, body_file, mentions, assign_author, unassign_author, preview, ok, warnings}`.

The default bodies ship in [`src/pr_management/templates/`](src/pr_management/templates/); a `### <template-name>` section under *Template body overrides* in `pr-management-triage-comment-templates.md` replaces one.

### `triage fold` — splice the note into the PR body

```bash
uv run --project <framework>/tools/pr-management pr-management triage fold --current-body <file> --block <file> --out <file>
```

Removes any existing `pr-triage-fold` span and appends the new block, so the description always carries exactly one note.
`--current-body` is raw markdown or the JSON `vetted-op-read --save … pr-view-with-body <N>` wrote.
Prints `{out, replaced, bytes}`.

### `triage guard` — the pre-mutation checks

```bash
uv run --project <framework>/tools/pr-management pr-management triage guard <action> --pr <N> --head <sha> --saved-dir <workspace>/saved
```

Reads `liveness-<N>.json` (`gql-pr-liveness <N>`) and `runs-head-<N>.json` (`runs-at-head <sha>`), saved just before the mutation.
Refuses on a moved head (`reroute: reclassify`); for `mark-ready` and `promote-bot-draft`, on any run awaiting approval, a conflict or unknown mergeability; for `rebase`, on a conflict or unknown mergeability.
For `approve-workflow` it lists the `run_ids` to approve; for `rerun`, the `rerun_failed` or `cancel_and_rerun` runs.
Prints `{action, pr, proceed, reason?, reroute?, …}`.

### `triage session record` / `triage session summary`

```bash
uv run --project <framework>/tools/pr-management pr-management triage session record --session <file> --pr <N> --head <sha> --action <action> [--classification <c>] [--terminal]
uv run --project <framework>/tools/pr-management pr-management triage session summary --session <file>
```

`record` writes the session cache `triage classify --session` reads: a PR recorded terminal with an unchanged head is suppressed on the next classification.
`summary` prints the Step 6 counts and a ready-to-print `text` block.

### `config`

Prints the resolved configuration — useful when a value is not the one expected.

## Shared rules

The definitions every `pr-management` skill uses, implemented once.
Other skills link here instead of restating them; change a rule in code and here together.

- **Maintainer** — a member of `committers_team`, or an account with `write` / `maintain` / `admin` on the upstream repo ([`people.py`](src/pr_management/people.py)).
  `authorAssociation` is only a first filter: GitHub reports `COLLABORATOR` for triage- and read-role collaborators too.
  A `COLLABORATOR` / `MEMBER` / `OWNER` login in neither the team roster nor a saved permission read is decided as a maintainer (the direction that never talks over one) and listed under `needs` as an `upstream-permission` read.
- **Bot** — a known bot login or any login ending in `[bot]`. The dashboard also counts Copilot reviewers and deleted (`ghost`) accounts as bots: automation is not engagement.
- **Collaborator thread** — an unresolved review thread whose first comment is by `OWNER` / `MEMBER` / `COLLABORATOR`. Contributor-opened threads never block, never count as a regression on a ready PR, and never make a merit discussion.
- **Triage marker** ([`markers.py`](src/pr_management/markers.py)) — a triager's comment (`OWNER` / `MEMBER` / `COLLABORATOR`, not the author) carrying the quality-criteria link text, or the PR body's `pr-triage-fold` block.
  It is *current* when posted after the head commit (the fold: `head=` matches the head); its time is the comment's `createdAt` or the fold's `triaged=`; its sub-state is `responded` when the author commented or pushed after it, else `waiting`.
  A fold with `action=request-author-confirmation` is a confirmation request, not a triage marker.
  The body is author-controlled: of several opening markers the last whose `triaged=` parses with an explicit zone wins, so a malformed marker cannot hide the real one.
  The dashboard counts a PR as triaged when it ever carried a marker: a later push (or a fold whose `head=` no longer matches) makes it `responded`, not untriaged.
- **Failed checks** ([`ci.py`](src/pr_management/ci.py)) — check runs concluding `FAILURE` / `TIMED_OUT` and status contexts in `FAILURE` / `ERROR`; cancelled, skipped, neutral and `ACTION_REQUIRED` do not count.
  The rollup page is a prefix: a failing PR whose page is truncated needs the REST check-run list before any rule reads its failures.
- **Real-CI guard** — at least one check context matches a `real_ci_patterns` regex (case-insensitive, from the start); with no patterns configured, any context that is not a known bot or labeler check (`Mergeable`, `WIP`, `DCO`, `boring-cyborg`, …).
  A `SUCCESS` rollup without real CI is never `passing`.
- **Grace window** — a CI failure is not yet a signal for 24 hours, or 96 hours once a collaborator has engaged, from the newest failing check's start.
- **Static check** — a failed check whose name and a `static_check_patterns` entry contain one another (case-insensitive).
- **Systemic failure** — a check name failing on at least two of the ten most recently merged PRs.
- **Mergeability** — `UNKNOWN` is "not yet computed", never "mergeable": passing needs `MERGEABLE`, and every guard refuses on `UNKNOWN`.
- **Strip-ready-on-downgrade** — a ready-labelled PR that regresses into a `deterministic_flag` `draft` / `comment` / `close` loses the label, unless a collaborator thread is open (a merit discussion): then `draft` becomes feedback only, `close` delivers its reasoning and label but leaves the PR open, and the label stays.
- **Reason strings** — one line, factual, signal first and proposal verb last; no emoji, no editorialising, no generated prose. The table's templates are the whole surface.

## What it reads

| File | Read for |
|---|---|
| `project.md` | `upstream_repo`, `upstream_default_branch`, `upstream_contributing_docs_url`, `project_name` |
| `pr-management-config.md` | identifiers, labels, grace windows, workflow choices, `real_ci_patterns`, `static_check_patterns` |
| `pr-management-triage.md` | per-skill overrides of the same keys (wins over `pr-management-config.md`) |
| `pr-management-triage-comment-templates.md` | URL placeholders, the triage-marker link text, the AI-attribution footer |
| `pr-management-triage-ci-check-map.md` | check-name pattern → category → doc URL |

## Tests

```bash
uv run --directory tools/pr-management --project . python -m pytest
```

The triage tests mirror, case by case, the model-graded `pre-filter` and `decision-table` eval suites the scripted rules replaced.
