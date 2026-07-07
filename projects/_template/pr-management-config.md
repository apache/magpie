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

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — pr-management-triage configuration

This file is the **per-project configuration** for the
[`pr-management-triage`](../../skills/pr-management-triage/SKILL.md) skill.
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
| `committers_team` | `<github-org>/<committers-team-slug>` | `classify-and-act.md` row F5b — team-mention detection. Used to recognise PR comments that `@`-mention the project's committers as a maintainer-to-maintainer ping. Example: `apache/airflow-committers`. |
| `area_label_prefix` | `area:` | `classify-and-act.md`, `pr-management-stats` — area-label grouping. Adjust to the prefix your project uses for area labels (e.g. `comp:`, `module:`), or leave blank if your project doesn't group PRs by area. |

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
| `triage_feedback_channel` | `pr-body` | Where the deterministic quality-violation feedback for the `draft`, `comment` (deterministic-flag), and `close` actions is delivered. `pr-body` (default): the violations are **folded into the PR description** as a managed marker block — editing a PR body does **not** notify subscribers, so the maintainer mailbox stays quiet (the [denoise rationale](../../skills/pr-management-triage/rationale.md#why-fold-feedback-into-the-pr-body-denoise)). `comment`: the legacy behaviour — the same feedback is posted as a PR comment, which notifies every subscriber. Pings, `request-author-confirmation`, security-language, suspicious-changes, and stale-sweep messages are unaffected by this key — their purpose *is* to notify a human, so they always post a comment. See [`actions.md`](../../skills/pr-management-triage/actions.md) and [`comment-templates.md#body-fold-rendering`](../../skills/pr-management-triage/comment-templates.md#body-fold-rendering). |
| `confirmation_handback_mode` | `reviewer-ping` | `request-author-confirmation` action's "If yes" branch. `reviewer-ping`: the author marks threads resolved and `@`-pings the reviewer for a final look + label. `maintainer-sweep`: the author replies with a short `yes / ready` and the next triage sweep promotes the PR to the maintainer review queue. Pick `maintainer-sweep` if your project runs a regular maintainer triage cadence and prefers a lightweight contributor confirmation over a reviewer-driven hand-back. See [`comment-templates.md#request-author-confirmation`](../../skills/pr-management-triage/comment-templates.md) for both bodies. |
| `session_history_gist` | `enabled` | [Step 6b](../../skills/pr-management-triage/SKILL.md#step-6b--propose-session-history-gist-update) — propose appending each session to a private GitHub gist on the maintainer's account. Set to `disabled` to skip Step 6b unconditionally for this project (overrides the per-invocation `no-history` flag). The local state file at `.apache-magpie.session-state.json` is read regardless so an existing gist remains discoverable. See [`session-history.md`](../../skills/pr-management-triage/session-history.md). |
