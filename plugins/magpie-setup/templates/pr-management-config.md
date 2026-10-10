<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — pr-management-triage configuration](#todo-project-name--pr-management-triage-configuration)
  - [Identifiers](#identifiers)
  - [Project-specific labels](#project-specific-labels)
  - [Grace windows](#grace-windows)
  - [Workflow choices](#workflow-choices)
  - [CI check patterns](#ci-check-patterns)
  - [Typed-decision pre-filter (opt-in)](#typed-decision-pre-filter-opt-in)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — pr-management-triage configuration

This file is the **per-project configuration** for the
[`pr-management-triage`](../../../skills/pr-management-triage/SKILL.md) skill.
It holds the concrete values for your adopter project.

Copy this file into your own
`<project-config>/pr-management-config.md` and replace every
`<placeholder>` with your project's value. The suggested label
strings and grace-window defaults below are reasonable starting
points — keep them as-is or override with your project's
existing conventions.

## Identifiers

| Key | Value | Used by |
|---|---|---|
| `committers_team` | `<github-org>/<committers-team-slug>` | `pr-management triage classify` — pre-filters F5b / F5c and every maintainer test (team membership). Used to recognise PR comments that `@`-mention the project's committers as a maintainer-to-maintainer ping. Example: `apache/airflow-committers`. |
| `area_label_prefix` | `area:` | `pr-management triage classify`, `pr-management-stats` — area-label grouping. Adjust to the prefix your project uses for area labels (e.g. `comp:`, `module:`), or leave blank if your project doesn't group PRs by area. |

## Project-specific labels

Labels the skill applies or watches for. Each row maps a generic
**framework concept** to whatever label string the adopter uses.
If the project doesn't have a given concept, leave the value blank
and the skill will skip that row of decision-table actions.

The labels below are **suggested defaults** — readable English
strings that work for most projects. Override with your project's
existing label names if any are already in use.

| Concept | Suggested label | Notes |
|---|---|---|
| `ready_for_maintainer_review` | `ready for maintainer review` | Applied by the `mark-ready` action; used by `pr-management-code-review` as a default selector. |
| `quality_violations_close` | `closed because of multiple quality violations` | Applied when a PR is closed for failing the project's PR quality criteria after multiple opportunities to fix. |
| `suspicious_changes` | `suspicious changes detected` | Applied to first-time-contributor workflow approvals where the diff looks suspicious (binary blobs, unrelated CI changes, etc.). |
| `work_in_progress` |  | Leave blank if your project doesn't use a dedicated WIP label (the skill relies on draft status instead); fill in the label name if your project does. |

## Grace windows

Tunable thresholds. The defaults below are sized for a project
with **~50–100 open PRs and a triage sweep every 1–2 days**.
Scale them up for projects with lower contributor traffic — less
frequent sweeps imply longer grace windows so the skill doesn't
fire stale-action proposals on PRs the maintainer hasn't had a
chance to look at yet.

| Concept | Default | Project value |
|---|---|---|
| Stale-draft close threshold (triaged) | 7 days | 7 days |
| Stale-draft close threshold (untriaged) | 14 days | 14 days |
| Inactive-open → draft threshold | 28 days | 28 days |
| Stale-review-ping cooldown | 7 days | 7 days |
| Stale-workflow-approval threshold | 28 days | 28 days |
| Stale-Copilot-review threshold | 7 days | 7 days |

## Workflow choices

Some triage actions branch on a project-specific workflow
preference rather than a quantitative threshold. Each key
below picks one of the documented variants; leave at the
default to use the standard variant.

| Key | Default | Notes |
|---|---|---|
| `triage_feedback_channel` | `pr-body` | Where every contributor-facing triage note is delivered. `pr-body` (default): one maintainer-triage note is **folded into the PR description** and replaced in place on every refresh — editing a PR body notifies nobody but the `@`-mentioned author, so the maintainer mailbox stays quiet (the [denoise rationale](../../magpie-pr-management/skills/pr-triage/design-notes.md#why-fold-feedback-into-the-pr-body-denoise)). `comment`: the legacy behaviour — each note is posted as a PR comment, which notifies every subscriber. The suspicious-changes receipt always posts as a comment. `pr-management triage render` and `triage fold` implement both channels. |
| `confirmation_handback_mode` | `reviewer-ping` | `request-author-confirmation` action's "If yes" branch. `reviewer-ping`: the author marks threads resolved and `@`-pings the reviewer for a final look + label. `maintainer-sweep`: the author replies with a short `yes / ready` and the next triage sweep promotes the PR to the maintainer review queue. Pick `maintainer-sweep` if your project runs a regular maintainer triage cadence and prefers a lightweight contributor confirmation over a reviewer-driven hand-back. See [`triage render#request-author-confirmation`](../../../tools/pr-management/README.md#triage-render--the-contributor-facing-bodies) for both bodies. |
| `backport_branches` | *(empty)* | Base-branch patterns (e.g. `v*-test`, `release/*`) that receive only cherry-picks from the default branch. Enables the [backport check](../../magpie-pr-management/skills/pr-triage/backport-check.md) (Step 0.7) for PRs targeting them. Leave empty if the project does not cherry-pick. |
| `backport_policy` | `fixes-only` | What a backport may carry. `fixes-only`: flag features, behaviour changes, new deprecations, removals and refactors for closing. `any`: skip the change-type check and only verify the backport is a faithful cherry-pick. |
| `session_history_gist` | `enabled` | [Step 6b](../../../skills/pr-management-triage/session-history.md#step-6b--propose-session-history-gist-update) — propose appending each session to a private GitHub gist on the maintainer's account. Set to `disabled` to skip Step 6b unconditionally for this project (overrides the per-invocation `no-history` flag). The local state file (`session-state.json` in the personal config layer) is read regardless so an existing gist remains discoverable. See [`session-history.md`](../../../skills/pr-management-triage/session-history.md). |
| `mention_allowlist` | *(empty)* | Handles and teams every `pr-management` body may `@`-mention live (e.g. `` `@release-bot` `@acme/docs-team` ``). By default only the PR author is mentioned and every other handle is backtick-quoted. The renderers read this from any config layer; the agent-guard `mention` guard honours it only from `.apache-magpie-overrides/pr-management-config.md` on the target repository's default branch on GitHub, so it takes effect once merged there. One call can add a handle with `--allow-mention <login>` (plus `MAGPIE_ALLOW_MENTIONS=1` on the posting command). |

## CI check patterns

Regular expressions the classifier matches against check names.
Leave a value empty to use the framework default.

| Key | Default | Notes |
|---|---|---|
| `real_ci_patterns` | *(empty)* | Check names that are **real CI**, as regexes matched from the start of the name, case-insensitive (e.g. `` `Tests` `Static checks` `Build` ``). A green rollup counts as `passing` only when one context matches. Empty: any context that is not a known bot or labeler check (`Mergeable`, `WIP`, `DCO`, `boring-cyborg`, …) counts. |
| `static_check_patterns` | *(empty)* | Extra **static-check** name fragments, added to the built-in list (`lint`, `mypy`, `ruff`, `pre-commit`, `spelling`, `build docs`, …). A failure here routes to a code-fix comment instead of a rerun. |

## Typed-decision pre-filter (opt-in)

Runs an advisory classification pass during Step 2 triage alongside the deterministic decision table using `typed_decision.choice()`.
The deterministic decision table always executes authoritatively to determine classifications and actions per `PRINCIPLES.md` §6.
The pre-filter pass runs alongside it to record predictive telemetry and evaluate accuracy.
Can be declared here or overridden in `.apache-magpie-overrides/pr-management-triage.md` (or `pr-management-triage.md` in the personal layer).

| Key | Default | Notes |
|---|---|---|
| `enable_typed_decision_prefilter` | `false` | Enable the opt-in typed-decision pre-filter. When `false` (default), triage runs the deterministic decision table exclusively. When `true`, calls `typed_decision.choice()` alongside the decision table to record shadow predictions. On provider unavailability or low confidence, falls through cleanly. |
| `typed_decision_confidence_threshold` | `0.85` | Minimum confidence score required to accept the pre-filter prediction as high confidence. |

**Third-Party Endpoint and Privacy Prerequisites:**
- Endpoint: `https://api.typesafe.ai/v1/systemone`
- Credentials: `TYPESAFE_API_KEY` (or fallback `JEV_API_KEY`) or `~/.config/apache-magpie/typesafe.key`.
- Privacy-LLM approval: Requires an opt-in entry in `<project-config>/privacy-llm.md` with non-empty `Data-residency contract` and valid non-placeholder `Approved-by` sign-offs.
- Transmits public PR metadata (title, body, and commits); does not send private repository data.

**Human-in-the-loop invariant:**
Pre-filtering only gathers advisory predictions and evaluates accuracy.
It NEVER bypasses the deterministic table or acts on a PR without explicit maintainer confirmation in the interaction loop.

**Telemetry:**
When enabled, every call is logged to `.apache-magpie-local/logs/pr-triage-typed-decision.jsonl` with `{pr, table_classification, predicted_label, confidence, latency_ms, match, outcome}` for adopter precision/recall evaluation.
