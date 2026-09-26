<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Verdict composition — `verdict.json` schema and hand-back

Companion to [`SKILL.md`](SKILL.md). Procedural detail for Step 10:
composing the structured verdict file that captures the run, and
the hand-back contract to the calling skill.

## `verdict.json` schema

The `key` field carries the tracker's native issue identifier:

- JIRA-based projects: `"<KEY>-9999"` (e.g., `"FOO-1234"`).
- GitHub-Issues-based projects: `"<owner>/<repo>#<N>"`
  (e.g., `"apache/airflow#12345"`) or, when the repo is implicit
  from `<project-config>`, just `"#12345"`.
- Other tracker types declare their key format in
  `<project-config>/issue-tracker-config.md`.

The rest of the schema is tracker-agnostic.

```json
{
  "key": "<TRACKER-KEY>",
  "shape": "A | B | C | D | E-vague | E-precise | F | G | H",
  "classification": "fixed-on-master | still-fails-same | still-fails-different | cannot-run-extraction | cannot-run-environment | cannot-run-dependency | timeout | intended-behaviour | duplicate-of-resolved | needs-separate-workspace",
  "nature": "bug-as-advertised | bug-as-advertised-partial-fix | feature-request | feature-request-disguised-as-bug | intended-and-documented",
  "rev": "<short-sha-of-default-branch>",
  "jdk": "<runtime + version>",
  "command": "<verbatim command line>",
  "runtime_ms": <int or null>,
  "exit_code": <int>,
  "matched_original_failure": <bool>,
  "cases": [
    {
      "expr": "<expression / sub-case>",
      "expected": "<expected outcome>",
      "actual_master": "<observed on current default-branch>",
      "match_on_master": <bool>,
      "history": [
        {
          "year": <int>,
          "status": "<observed at that time>",
          "source": "<comment-URL or report reference>"
        }
      ],
      "note": "<short>"
    }
  ],
  "cases_summary": "<one-line roll-up>",
  "cross_type_probe": {
    "file": "<filename in evidence package>",
    "log": "<filename in evidence package>",
    "summary": "<one-line>",
    "findings": "<optional longer prose>"
  },
  "operator_variants_probe": {
    "file": "<filename>",
    "log": "<filename>",
    "summary": "<one-line>",
    "findings": "<optional>"
  },
  "notes": "<long-form analysis, API-evolution adaptation citations, environment qualifications>"
}
```

Keys use **snake_case** (`runtime_ms`, not `runtime-ms`) so `jq`
queries don't need quoting.

## Required vs optional fields

**Always present:**

- `key`, `shape`, `classification`, `nature`, `rev`, `jdk`,
  `command`, `exit_code`, `matched_original_failure`, `notes`.

**Conditionally present:**

- `runtime_ms` — `null` when the classification is
  `cannot-run-*` (the run didn't happen).
- `cases` — only for multi-case reproducers (see
  [`verification.md` → *"Multi-case verification"*](verification.md#multi-case-verification)).
- `cases_summary` — present iff `cases` is present.
- `cross_type_probe` — present iff a type-family probe ran.
- `operator_variants_probe` — present iff an operator-variant
  probe ran.

## The `nature` field

`nature` is **orthogonal** to `classification`. Classification
answers *"what does the runtime do"*; nature answers *"how should
we read this issue"*. The same issue can be `still-fails-same` /
`feature-request-disguised-as-bug` (the reporter's expectation is
wrong; the runtime does what it should), OR `still-fails-same` /
`bug-as-advertised` (the reporter is right; this is a real bug).

The five nature labels:

- **`bug-as-advertised`** — the reporter is correct: this is a real
  bug; the runtime behaviour violates documented or expected
  semantics. Most reports fall here.
- **`bug-as-advertised-partial-fix`** — same as above, but some
  cases have been fixed since the report was filed (the multi-case
  reproducer has a mix of `match_on_master: true` and `false`).
  The `cases_summary` describes the split.
- **`feature-request`** — the report frames itself as a feature
  request from the start. Correctly typed as Improvement / New
  Feature, not Bug.
- **`feature-request-disguised-as-bug`** — the report frames a
  behaviour as a bug, but the behaviour is intended per project
  docs. The reporter is asking for a change; the change is
  legitimate to consider but not on the bug track. Common in
  long-lived projects with users new to the conventions.
- **`intended-and-documented`** — the behaviour is intended AND
  the reporter would clearly see this from existing docs. Distinct
  from `feature-request-disguised-as-bug`: this is *"please read
  the docs"*; the disguised case is *"the docs are correct but the
  user has a real request"*.

[`issue-reassess`](../reassess/SKILL.md) uses the nature
field to bucket campaign findings into the right report sections.
[`issue-reassess-stats`](../reassess-stats/SKILL.md) uses
it for its `feature-request-disguised-as-bug` callout (a common
class that maintainers want to surface for tracker hygiene).

## The `cases` array

For multi-case reproducers, each entry captures one case:

| Field | Type | Notes |
|---|---|---|
| `expr` | string | The expression or sub-case description |
| `expected` | string | What the reporter / maintainer expected |
| `actual_master` | string | What the run on `<default-branch>` produced |
| `match_on_master` | bool | `true` if `actual_master` matches `expected` |
| `history` | array | Optional prior baselines; see below |
| `note` | string | Short per-case comment |

Each `history` entry captures a maintainer's prior observation:

| Field | Type | Notes |
|---|---|---|
| `year` | int | Year of the observation |
| `status` | string | What was observed (verbatim from the comment) |
| `source` | string | Tracker comment URL, mailing-list URL, or other reference |

## Probe sub-schemas

`cross_type_probe` and `operator_variants_probe` have the same
shape:

| Field | Type | Notes |
|---|---|---|
| `file` | string | Filename of the probe script in the evidence package (e.g. `cross-type-probe.foo`) |
| `log` | string | Filename of the probe output |
| `summary` | string | One-line roll-up (e.g. *"3/4 backings throw; primitive array returns wrong value"*) |
| `findings` | string | Optional longer prose. Used when the probe surfaced a separate-issue candidate; details belong in `cross-type-probe-findings.md` in the evidence package. |

See [`probe-templates.md`](probe-templates.md) for what populates
these.

## The `notes` field

Free-form prose. Use it for:

- **API-evolution citations** — when an adaptation was made per
  release-notes documentation
  ([`extraction.md` → *"API-evolution adaptation"*](extraction.md#api-evolution-adaptation)).
- **Environment qualifications** — *"passes on JDK 21 master;
  reporter ran JDK 8; retry on JDK 8 would strengthen the
  verdict"*.
- **Liminal classifications** — when the verdict sits between two
  labels, explain the choice.
- **New-issue candidates** — when a probe surfaced a sibling-type
  bug worth a separate issue.
- **Workaround the reporter mentioned** — important for
  understanding why the issue may have lingered open despite a
  workaround being known.

Keep it factual; analysis goes here, recommendations go to the
calling skill's report.

## Hand-back contract

After writing `verdict.json`, this skill hands back to the caller:

- The path to the evidence package directory.
- The verdict's `classification` and `nature` (also in the JSON,
  but surfacing them in the response saves the caller a file
  read).
- Any new-issue candidates the probe surfaced.

The caller is one of:

- A human invoking the skill standalone — receives a brief recap
  on stdout.
- [`issue-triage`](../triage/SKILL.md) — uses the verdict as
  Step 2's runtime evidence input.
- [`issue-reassess`](../reassess/SKILL.md) — collects the
  verdict into the campaign aggregate; the campaign dashboard at
  [`issue-reassess-stats`](../reassess-stats/SKILL.md) reads
  the JSON file directly.

**Hand-back is read-only on the tracker.** This skill never posts,
transitions, or closes; the caller decides what user-facing action
to take based on the verdict.

## Evidence-package contract

The full evidence package per issue, per
[`<project-config>/reproducer-conventions.md`](../../../../projects/_template/reproducer-conventions.md):

| File | Purpose |
|---|---|
| `description.md` | Frozen copy of the issue body + comments |
| `issue.json` | Frozen JSON snapshot of the tracker state |
| `original.<ext>` | Verbatim reporter's code (untouched) |
| `reproducer.<ext>` | Adapted runnable form |
| `run.log` | stdout + stderr + command + rev + runtime version |
| `verdict.json` | This file |
| `cross-type-probe.<ext>` (optional) | Probe script |
| `cross-type-probe.log` (optional) | Probe output |
| `cross-type-probe-findings.md` (optional) | When findings warrant a separate write-up |

This package is what [`issue-reassess`](../reassess/SKILL.md)
feeds into its campaign report and what
[`issue-reassess-stats`](../reassess-stats/SKILL.md) reads
for the dashboard.

### Evidence packages are local-only — never committed

`description.md` and `issue.json` are **verbatim, frozen copies of
the reporter's words** — issue body and every comment, attributed,
unredacted. The evidence package is working material for a human
reviewer, **not** data to publish. Committing a campaign directory
to a public repository puts every reporter's comment text on the
public record verbatim, re-hosted outside the tracker, with no
notice to the people who wrote it — a privacy regression the
framework must not ship as a default.

Rules:

- The campaign root lives **outside any git repository** by
  default — per
  [`<project-config>/reproducer-conventions.md`](../../../../projects/_template/reproducer-conventions.md)
  the convention is `~/work/<project>-reassess/<campaign-id>/<ISSUE-KEY>/`,
  deliberately under `$HOME`, not in the source tree.
- If an operator relocates the scratch dir inside a repo (including
  the adopter's `<project-config>` tree), the campaign directory
  **MUST be gitignored**. The shipped
  [`projects/_template/.gitignore`](../../../../projects/_template/.gitignore)
  carries the default patterns so a fresh adopter is safe without
  having to think about it.
- Never add a campaign/evidence path to a commit to "share results"
  — share the *report* (`issue-reassess` produces an aggregated,
  reviewed write-up); the raw evidence package stays local.

## Clickable references (Golden rule 9)

Whenever this skill
emits a reference to an issue or PR — the `verdict.json` artefact
(the `url` field plus any cited PRs in `linked_prs`), the
hand-back artefact, the per-case progress output the user sees —
the reference must be one click away in whatever surface it
lands on:

- **On data / markdown surfaces** (verdict.json `url` field
  consumed downstream as raw URLs; any markdown-rendered nature
  analysis): use the full URL or the markdown link form per
  [`AGENTS.md` § *Linking tracker issues and PRs*](../../../../AGENTS.md#linking-tracker-issues-and-prs):
  - **Issue**: `[<issue-tracker>#NNN](https://github.com/<issue-tracker>/issues/NNN)`
  - **PR**: `[<upstream>#NNN](https://github.com/<upstream>/pull/NNN)`

- **On terminal surfaces** (the per-case progress output, the
  hand-back artefact): wrap the visible short form
  (`<issue-tracker>#NNN`, `<upstream>#NNN`) in **OSC 8 hyperlink
  escape sequences** (`\e]8;;<URL>\e\\<short>\e]8;;\e\\`) so
  modern terminals (iTerm2, Kitty, GNOME Terminal, WezTerm,
  Windows Terminal, …) render the short text as clickable. Where
  OSC 8 is unsupported (CI logs, dumb terminals), fall back to
  printing the bare URL on the same line after the number.

Bare `#NNN` with no link wrapper of any kind is never acceptable
— the verdict.json artefact is consumed downstream by
`issue-reassess` and `issue-reassess-stats` as drill-down
evidence.

**Self-check before writing the verdict.json file**: grep the body
for bare `#\d+` tokens that aren't already inside a markdown link,
a raw `https://...` URL, or an OSC 8 wrapper, and convert any
match.

## Cross-references

- [`SKILL.md`](SKILL.md) — orchestration; this file expands Step 10.
- [`extraction.md`](extraction.md) — populates `shape`,
  `original.<ext>`, `reproducer.<ext>`.
- [`runtime-recipes.md`](runtime-recipes.md) — populates `rev`,
  `jdk`, `command`, `runtime_ms`, `exit_code`, `run.log`.
- [`verification.md`](verification.md) — populates
  `classification`, `matched_original_failure`, `cases`,
  `cases_summary`.
- [`probe-templates.md`](probe-templates.md) — populates
  `cross_type_probe`, `operator_variants_probe`.
- [`<project-config>/reproducer-conventions.md`](../../../../projects/_template/reproducer-conventions.md) —
  evidence-package directory layout.
- [`issue-reassess`](../reassess/SKILL.md) — campaign caller
  consuming `verdict.json`.
- [`issue-reassess-stats`](../reassess-stats/SKILL.md) —
  dashboard caller aggregating `verdict.json` files.
