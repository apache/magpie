<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Contributor growth: calibration, community signals, and candidate screening](#contributor-growth-calibration-community-signals-and-candidate-screening)
  - [What is wrong](#what-is-wrong)
  - [Decisions](#decisions)
  - [Components](#components)
    - [1. Pushback penalty](#1-pushback-penalty)
    - [2. `tools/contributor-metrics`](#2-toolscontributor-metrics)
    - [3. `calibrate` skill](#3-calibrate-skill)
    - [4. Community signals](#4-community-signals)
    - [5. `candidate-screen` skill](#5-candidate-screen-skill)
  - [Real names](#real-names)
  - [Testing](#testing)
  - [Rollout](#rollout)
  - [Risks](#risks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Contributor growth: calibration, community signals, and candidate screening

| | |
|---|---|
| **Status** | Proposed. |
| **Scope** | The `contributor-growth` family: a penalty in `automated-contributions.md`, a new `tools/contributor-metrics` tool, two new skills (`calibrate`, `candidate-screen`), a shared `community-signals.md` used by `nomination` and `contributor-to-committer`, a new `tools/chat` contract with a Slack adapter, and a hand-off from `/magpie-setup config`. |

## What is wrong

An adopter used the family to surface committer and `<governance-body>` candidates, calibrating the thresholds by hand from the project's own past nomination decisions.
The run worked well enough to be useful and showed five gaps:

1. **No calibration path.**
   Thresholds are either framework defaults or numbers a maintainer types in.
   Deriving them from the project's past decisions — the only defensible source — took a manual, one-off analysis.
2. **Pushed-back automated work still scores.**
   `automated-contributions.md` discounts an item that drew maintainer pushback to `0.25`, and one closed after pushback to `0`, but never below zero.
   A contributor with many such items still accumulates count, and one surfaced as a near-candidate on that basis.
3. **Only GitHub is measured.**
   The skills name mailing-list presence and release testing as factors, and past deferrals cite them most often, yet nothing collects them; Step 3 of `nomination` only asks the nominator.
4. **Public community conduct is invisible.**
   Whether a candidate's public activity helps users and the project, or consists of unconstructive complaint, is left entirely to the nominator's memory.
5. **No multi-candidate output.**
   Every skill assesses one handle.
   The screening across all contributors, and the per-candidate evidence the `<governance-body>` asked for (which areas, in what share), had to be assembled ad hoc.

The same feedback also asked that *issues filed* be supporting evidence rather than a required floor, and that triaging other people's issues count as a positive signal.

## Decisions

- **The output is a floor to help notice candidates, never a decision.**
  Every report says so; decisions remain the `<governance-body>`'s.
- **Deterministic counting lives in a tool.**
  Calibration measures on the order of a hundred past nominees across two windows, and screening measures dozens of contributors; that is code, not model passes (Principle 6).
  The model keeps the judgement calls: restatement confirmation, thread classification, community-item classification, and the narrative.
- **Community signals are evidence plus a separate indicator.**
  They never change activity counts or threshold pass/fail.
- **Off-project sources are limited to accounts the candidate linked themselves**, and to posts that mention the project.
  No open web search for a person's name or handle.
- **Identity is confirmed or not used.**
  A cross-platform match counts only when a commit email, the organization's people directory, a chat profile, or the maintainer confirms it.
- **The report is delivered to a private repository only**, verified private through the API before anything is written.
  A secret gist is not private — anyone with its URL can read it — so it is not an option.
- **Real names are used when verified**, never guessed (see [Real names](#real-names)).
- **Calibration working data never leaves the session scratch directory.**
  Only the resulting numbers, and the date, reach configuration.

## Components

### 1. Pushback penalty

A new key in `contributor-nomination-config.md`:

```yaml
automated_pushback_penalty: 0.25   # 0 restores the discount-only behaviour
```

It applies to each item in class `P` (drew pushback on automated content) or `C` (closed after such pushback).
Class `R` (restatement) is low-value, not pushed back on, and is not penalised.

Per count: `adjusted = Σ weights − penalty × (P + C items)`, floored at `0`.
With the defaults, a closed-after-pushback PR nets `−0.25` and a pushed-back merged PR nets `0`.
The penalty is applied once per PR or issue thread, not per comment, so one incident with a long exchange counts once.

The brief shows raw, discounted, penalty, and adjusted side by side.
The existing reporting rules stand: describe flagged items factually, do not label the contributor or speculate about tools, do not reproduce the pushback text, and state that pushback is a negative signal to weigh, not a disqualification.

### 2. `tools/contributor-metrics`

A Python project run with `uv`, `**Capability:** substrate:analytics`, calling `gh` through a subprocess as the other GitHub tools do.

**Input:** one or more handles, `--end <date>`, `--months 6,12`, `<upstream>`, the area-label prefix (config `area_label_prefix`, default `area:`), the maintainer roster used for pushback attribution, `automated_pushback_phrases`, and the weight and penalty keys.

**Output**, one JSON object per handle and window:

- raw and adjusted counts: PRs merged, reviews, substantive reviews, comment threads, issues filed, and **issues triaged** — labelling, reproducing, or answering issues opened by someone else;
- **area breakdown:** per area, merged PRs and reviews as counts and as a share of the candidate's total;
- a monthly timeline;
- every flagged item with its link and class.

Pushback detection by phrase is deterministic and happens in the tool.
Restatement needs judgement: the tool emits `R` *candidates*, and the calling skill confirms them within the existing inspection budget.

Results are cached per handle and window under `$TMPDIR`, so `calibrate` and `candidate-screen` do not refetch.

### 3. `calibrate` skill

A new skill in the family, `capability:stats`.
`/magpie-setup config` offers it when the family is installed and thresholds are blank; setup hands off and implements none of it.

**Step 0** runs the privacy-llm gate — the skill reads `<private-list>`, so an unapproved model in the stack is a hard stop — and the mail-archive backend health probe.

**Inputs:** `since:` (default five years), `holdout:<date>` (nothing dated after it is read), `exclude-thread:<id>` (repeatable), `windows:6,12`, and a recency half-life (default two years).

**Flow:**

1. **Find nominations.**
   Search `<private-list>` through the `mail-archive` contract for discussion, vote, and result threads on committer and `<governance-body>` nominations.
   From each thread the model extracts a structured row only: nominee, target, vote date, outcome (elected, deferred, withdrawn), and a coarse deferral category (narrow focus, little mailing-list presence, short tenure, other).
   No quotes and no member opinions are retained.
2. **Resolve handles.**
   Match nominees to GitHub handles from the thread, the roster, and commit history.
   Unresolved nominees are listed for the maintainer; none is guessed.
3. **Measure** each nominee with `contributor-metrics` (end date = vote date) and with the mailing-list rows of [community signals](#4-community-signals).
4. **Propose floors.**
   Per metric and target, show the recency-weighted p25 and median of elected nominees beside the median of deferred ones, split into recent and older eras, and propose a floor.
   A metric that does not separate elected from deferred is proposed as *evidence only*.
5. **Holdout check** (optional).
   Screen the current window with the proposed floors and list who surfaces, for the maintainer to compare with any live discussion; the skill never reads that discussion.
6. **Write configuration.**
   Propose a diff to `contributor-nomination-config.md` and `committer-readiness.md` holding only the numbers, the evidence-only markers, and `calibrated_on: <date>` — no derivation, no names.
   The default target is `.apache-magpie-local/`; the committed overrides layer is offered as an alternative.
   Applied on confirmation.

The per-nominee working table stays in the session scratch directory and the skill offers to delete it at the end.
Other skills suggest recalibrating when `calibrated_on` is older than twelve months.

### 4. Community signals

A shared `nomination/community-signals.md`, used by `nomination` and `contributor-to-committer` at their Step 3.
Step 3 becomes *collect, then ask the nominator to confirm or add*, instead of *ask*.

**Sources**, each resolved from project configuration; an unconfigured or unreachable source is reported as *not collected*:

| Source | Through | Rows it adds |
|---|---|---|
| `<dev-list>`, `<users-list>` | `mail-archive` contract, public archives | threads started, replies, replies to user questions, **release testing** (vote-thread replies showing testing) |
| Project chat | new `tools/chat` contract — Slack adapter over the Slack MCP, public channels only; Discord as a tracked extension point | messages, answers to other people's questions |
| GitHub Discussions | `gh` GraphQL | answers, accepted answers |
| Self-linked accounts | the candidate's GitHub profile links (blog, social accounts) | posts in the window that mention the project |

No direct messages, no private channels, and the candidate is never contacted.

**Classification**, per item, by the model: *constructive*, *neutral*, or *unconstructive*.
Constructive covers user support, advocacy, talks and tutorials, and **criticism that gives reasons or a proposal**.
Unconstructive is reserved for complaint without substance, hostility, or disparaging people.
Disagreement alone is never unconstructive.
Each item carries a link and a one-line factual summary; no long quotes, and no personal details of anyone else in the message.

**Community indicator:** each constructive item `+1`, each unconstructive item `− community_negative_weight` (default `1`).
Rendered as `community: +12 / −1 (net +11)` beside the threshold table, with the items listed.
It never alters activity counts or threshold pass/fail.

All collected content is external data under the repository's external-content rule; a message that tries to instruct the agent is surfaced and ignored.

### 5. `candidate-screen` skill

A new skill in the family, `capability:stats`.

**Inputs:** `target:committer|pmc|both` (default `both`), `window:6m`, `end:<date>`.
`report_repo` and `report_path` come from `contributor-nomination-config.md`.

**Step 0:** `gh api repos/<report_repo> --jq .private` must be `true`, or the skill refuses.
It shows the repository's collaborators for the maintainer to confirm the audience before anything is written.

**Flow:**

1. **Pool.**
   Committer target: everyone with a merged PR in the window who is not a committer.
   `<governance-body>` target: committers not in it.
   Rosters from the Apache Projects MCP where reachable, else `pmc-roster.md`.
2. **Pre-filter** deterministically on cheap search counts: keep anyone at or above `screen_prefilter_ratio` (default `0.5`) of any floor.
   Everyone dropped is logged with their counts.
3. **Measure** survivors with `contributor-metrics`.
   The shortlist is everyone missing at most `shortlist_max_missing` (default `2`) floors, evidence-only metrics excluded.
   Community signals are collected for the shortlist only.
4. **Write** two to three paragraphs per shortlisted candidate: what they built and where, their review, mentoring, and community work, and factual flags (automated-work pushback, single-area or single-vendor concentration where known).
   Every claim links to its evidence.

**Report**, one markdown file at `<report_path>/<date>-candidate-screen.md`:

- header: window, thresholds and `calibrated_on`, sources collected and not collected, and the floor-not-decision note;
- summary table: candidate, target, floors met, community net, automated-work flags;
- per candidate: area table (area, PRs, reviews, share), threshold table (raw, discounted, penalty, adjusted), community items, and the paragraphs;
- *considered, not shortlisted:* handles with counts only.

**Delivery:** the maintainer reviews the local file first; on confirmation it is committed through `gh api …/contents` with the payload in a file.
The report contains **no `@`-mentions** — plain handles with profile links — so no candidate is notified.
Nothing is posted anywhere else.

## Real names

Reports, briefs, and any drafted message to the `<governance-body>` show a person as **Real Name (`handle`)** when the name comes from a verifiable source, in this order:

1. the organization's people directory (for ASF, the Apache Projects MCP `get_person`) when the person has an account there;
2. the `name` field of their GitHub profile;
3. the author name on their commits to `<upstream>`, when consistent across commits.

When sources disagree, the directory wins and the disagreement is noted.
When none yields a name, the handle is used alone.
A name is never inferred from an email address, a handle, or a mailing-list display name that is not tied to the handle by a confirmed identity.
Email addresses are never included.

## Testing

Each new skill ships an eval suite under `tools/skill-evals/evals/<skill>/`, and `contributor-metrics` ships fixture tests with recorded `gh` JSON and no network.

| Unit | Cases |
|---|---|
| Penalty | weight, penalty, and floor arithmetic; once-per-thread; penalty `0` reproduces current output |
| `contributor-metrics` | area shares; triage detection; `R` candidates emitted, not decided |
| `calibrate` | synthetic archive of ~10 nominations → expected rows; a thread after `holdout` is never read; a non-separating metric is proposed evidence-only; output diff carries no names |
| Community signals | unconfirmed identity excluded; reasoned criticism classified constructive; injection in a message treated as data |
| `candidate-screen` | public `report_repo` refused; no `@`-mentions in output; shortlist boundaries; pre-filtered person appears in the dropped log |
| Real names | directory beats profile; no name inferred from an email local part |

## Rollout

Five PRs, in order, each independently useful:

1. Pushback penalty.
2. `tools/contributor-metrics`, with `contributor-to-committer` and `nomination` switched to it.
3. `calibrate`, and the `/magpie-setup config` hand-off.
4. Community signals and `tools/chat` with the Slack adapter; Discord tracked as an extension point.
5. `candidate-screen`, and the real-names rule applied across the family's renderers.

An adopter then recalibrates and screens with its own configuration; that run is not part of the framework change.

## Risks

- **Identity mismatch** puts someone else's activity in a candidate's file.
  Mitigated by confirm-or-exclude matching and the *possible match, not used* list.
- **Chilling legitimate dissent.**
  Mitigated by classifying reasoned criticism as constructive and keeping the indicator out of pass/fail.
- **Thresholds read as a decision rule.**
  Mitigated by the floor-not-decision note on every output and the evidence-only markers.
- **Private material leaking.**
  Calibration data stays in scratch; the report goes only to an API-verified private repository; nothing is posted publicly; no `@`-mentions.
- **Chat and archive coverage gaps** make quieter channels look like absence.
  Mitigated by reporting every source as collected or not collected.
