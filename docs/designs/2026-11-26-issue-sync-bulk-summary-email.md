<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [One state summary instead of many nudges in a bulk sync](#one-state-summary-instead-of-many-nudges-in-a-bulk-sync)
  - [Problem](#problem)
  - [Decision](#decision)
  - [Shape](#shape)
  - [Threshold and settings](#threshold-and-settings)
  - [Privacy constraints](#privacy-constraints)
  - [What changes where](#what-changes-where)
  - [Alternatives considered](#alternatives-considered)
  - [Open questions](#open-questions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# One state summary instead of many nudges in a bulk sync

| | |
|---|---|
| **Status** | Built. Model-graded evals for the new step are not written yet; see [Open questions](#open-questions). |
| **Scope** | `security-issue-sync` bulk mode, and the `issue-sync nudge-summary` command of `tools/security-management`. |

## Problem

A bulk sync (`sync all`, around 90 trackers on a busy project) assesses every tracker and merges the proposals.
Every tracker whose triage proposal or question to the team went unanswered got its own nudge:
a comment restating the question and `@`-mentioning the people asked.
One real run proposed 28 of them, nearly identical.
The maintainer rejected them all, for two reasons:
28 notifications land on the same handful of people at once, which trains them to ignore the next one;
and 28 separate comments still do not show anyone the overall picture, which is what the team needed.

The nudge itself was never a named rule.
Nothing in the skill defined when a team question is unanswered or what a nudge looks like,
so each run improvised one per tracker, and the bulk orchestrator had nothing to count.

## Decision

1. **Name the nudge.** `signals-to-actions.md` gains an *Unanswered team question* bullet:
   when the newest triage proposal, or a question to named team members, has had no answer from them for `nudge_after_days` (default 7),
   propose one short status comment that restates the decision and `@`-mentions the people asked, minus `do_not_ping`, at most once per question.
   It is a standalone comment, the one exception besides the release-manager comments to the rollup-only rule, because an `@`-mention in an edited rollup notifies nobody;
   its `<!-- apache-magpie: team-nudge v1 -->` marker lets pre-flight treat it as skill-authored and lets the next sync see that the question was nudged.
   Single-tracker syncs keep it.
2. **Report the question as state, not as a comment.** Bulk subagents return `pending_team_question` (`url`, a one-line `question`, `asked`, `since`, `nudged`)
   and four dates and names the summary needs (`milestone_due_on`, `release_manager`, `released_on`, `expected_disclosure_by`, plus `state`).
3. **Collapse in code.** `issue-sync nudge-summary` counts the nudge candidates and, at or above `nudge_summary_threshold` (default 5), collapses them:
   no tracker gets a nudge, and the merged proposal gains one *State summary* group.
   Below the threshold it returns the candidates and the per-tracker nudges are proposed as before.
   The rule is a function of the reports, so it runs as code, with tests, not as prose the model re-derives.
4. **Draft after the sweep.** The summary is previewed in the merged proposal, but the draft is rendered again after the apply loop and the Step 5d end-of-sync sweep
   (`stage: final`), so it describes the state the sync leaves behind, not the state it found.
   The final stage does not recount: the collapse Step 4b decided stands, since those nudges were already withheld,
   and it reads only applied values (`current_*`), never a proposal the user may have declined.
   Pre-flight-skipped trackers have no subagent report, so their pre-flight nodes (number, state, title, labels, milestone) feed a minimal report each,
   and the summary still counts and groups them.
   It is then confirmed like any other draft (`parse-reply`) and created through the drafting backend.
5. **Recap.** One line: *"N nudges replaced by summary email draft `<id>` to `<security-list>`"*.

## Shape

The email is plain text, each tracker as its title over its full URL, a new thread (no `Re:`, no `In-Reply-To`), `To:` the private `<security-list>` only:

```text
Subject: <PROJECT> security tracker state, <YYYY-MM-DD>

Hello security team,

This is the state of the <N> open trackers in <tracker> after today's sync.
It replaces <K> separate reminder comments on the trackers.
Please answer on each tracker, so every decision stays with its own case.

1. Needs a decision: <n>

- <tracker title>
  https://github.com/<tracker>/issues/<N>
  Question: <one line>
  Asked: <Name> (<login>), <login>; waiting <d> days

2. Fix work needed (valid, no fix PR yet): <n>

- <tracker title>
  https://github.com/<tracker>/issues/<N>
  target <release>, cut <YYYY-MM-DD>

3. In flight (fix PR open or merged, awaiting release): <n>

- <tracker title>
  https://github.com/<tracker>/issues/<N>
  fix PR open; release <release>, <YYYY-MM-DD>

4. Waiting on the release manager (released, advisory not sent): <n>

- <tracker title>
  https://github.com/<tracker>/issues/<N>
  Release manager: <Name> (<login>); waiting <d> days since <release> shipped

5. Upcoming deadlines (next 14 days, and overdue)

- <YYYY-MM-DD>: disclosure window ends (OVERDUE by <d> days): <tracker title>
  https://github.com/<tracker>/issues/<N>

- <YYYY-MM-DD>: release <release> cut: <tracker title>
  https://github.com/<tracker>/issues/<N>

<M> other trackers in this sync need nothing from the team right now.

Drafted by the security-issue-sync skill and reviewed before sending.
```

Every open tracker lands in at most one of groups 1 to 4, first match wins, terminal state first:
a closing disposition (`invalid`, `duplicate`, `wontfix`, `not CVE worthy`), an `announced` label or a shipped advisory lists nowhere;
then a pending question or `needs triage` (1), `fix released` or a shipped release with the advisory not sent (4), a fix PR open or merged (3), past triage with no fix PR (2).
Release-cut deadlines come only from groups 2 and 3, so a shipped release never shows as an overdue cut.
Group 1 lists every pending question, not only the nudge candidates, longest wait first, so the picture is complete.
Closed trackers and the rest are counted, not listed.

## Threshold and settings

The threshold and the wait sit in the `security-issue-sync.md` override file (personal layer first, then `.apache-magpie-overrides/`),
next to `bot_logins:`, the existing bulk-mode setting.
`do_not_ping` is different: who is away is personal and temporary, so it lives only in the operator's resolved `user.md`, never in committed project config.

| Key | Where | Default | Meaning |
|---|---|---|---|
| `nudge_summary_threshold` | override file | `5` | Collapse at this many nudge candidates; `off` never collapses; `0` or a non-number is refused. |
| `nudge_after_days` | override file | `7` | How long a team question waits before it earns a nudge. |
| `security_issue_sync.do_not_ping` | `user.md` | none | Handles never `@`-mentioned in a nudge and never named in the summary. |

The command reads `do_not_ping` only from its `user` input (that block of `user.md`); a `do_not_ping` passed any other way is ignored.

Five is where a run starts to read as a broadcast: below it, a nudge per tracker is still targeted.
Seven days matches the stale-review-ping cooldown the PR-management family uses.

## Privacy constraints

- **Private list only.** The recipient is `security_list` from `project.md`, never an argument the agent picks.
  The command refuses a missing or placeholder address, and an address that appears among the project's public lists.
- **Nothing the list does not already handle.** The body carries each tracker's title (the cleaned title, which the private list already sees) with its full tracker URL,
  the one-line question, the names of the people asked, release titles and dates.
  It carries no CVE ID, severity, CWE, reporter detail or quoted discussion.
- **Scrub, then check, in the command.** Titles and questions lose CVE and GHSA IDs, bare `#NNN` references, `do_not_ping` handles and names, and the `@` of any other handle.
  Then the `check` guardrails run over the body as an `email` surface (reporter CVSS, other ASF projects, the CVE-tool URL), plus a residue check for `@`, record IDs and bare references, and return `clean` / `violations`.
  No draft is created while `clean` is false.
- **The tracker's own links only.** A reported `issue_url` is used only when it is this tracker's URL for that issue; anything else gets the canonical URL.
- **Plain text, real links, never sent.** The draft goes through `oauth_curl` or `maildir`; `claude_ai_mcp` rewrites links, so it is never used for a body that is mostly links.
  With neither available, the draft is printed for the user to send.
- **One thread rule unaffected.** The summary answers no inbound thread.
  Reporter drafts stay separate, each on its own thread.
- **No `@` in the email.** It is not a ping; names appear as *Name (login)*.
- **No trace of `do_not_ping`.** Those handles are not named, and nothing hints that anyone was skipped:
  a question whose askees are all excluded reads *"Asked: the security team"*, exactly as one that named nobody,
  and an excluded release manager leaves a plain *"Waiting <d> days since <release> shipped"* line, exactly as an unknown one.

## What changes where

| File | Change |
|---|---|
| `tools/security-management/src/security_management/issue_sync/summary.py` | New: `nudge-summary`, the collapse rule, the groups and the plain-text renderer. |
| `tools/security-management/src/security_management/issue_sync/preflight.py` | The Step 1b query also reads each tracker's title and milestone, for the summary's pre-flight-skipped trackers. |
| `tools/security-management/src/security_management/issue_sync/bulk.py` | `parse-bulk-reply` takes `summary` and the `summary:skip` clause, and returns `summary`. |
| `tools/security-management/tests/test_issue_sync_summary.py` | New tests for both. |
| `plugins/magpie-security/skills/issue-sync/bulk-mode.md` | The report fields, step 4b (collapse), step 6 (draft after the sweep), the settings table, the hard rule. |
| `plugins/magpie-security/skills/issue-sync/signals-to-actions.md` | The *Unanswered team question* nudge, with a pointer to the collapse. |
| `plugins/magpie-security/skills/issue-sync/apply-and-push.md` | The team-nudge comment recipe; Step 5d hands over to the summary before the recap. |
| `tools/spec-loop/specs/security-issue-lifecycle.md` | The behaviour, as a guarantee. |

## Alternatives considered

- **Keep the nudges, batch them per person.** One comment per person asked still lands on many trackers,
  and a reader still has to visit every one to see the whole.
- **One comment on a tracking issue instead of an email.** It notifies only the people it mentions, and the security list is where the team already reads about the backlog;
  a tracker comment would also need its own home issue, which the tracker does not have.
- **Post to `<private-list>`.** The governing body's list is wider than the security team and is for escalation (process Step 4), not routine state.
- **Recount the threshold after the apply.** If the apply closed or answered enough trackers to drop below the threshold, the summary would vanish while its nudges stayed withheld: neither would reach the team.
- **Render once, from the pre-apply reports.** Cheaper, but the email would describe state the same run had just changed: a tracker moved to `fix released` would still read as *in flight*.
- **Always send the summary, whatever the count.** On a quiet week it is a weekly email nobody asked for; the threshold keeps it for the runs that would otherwise be noisy.
- **Leave the collapse in prose.** The model would recount and regroup on every run; the count, the threshold and the grouping are a function of the reports, so they belong in code.

## Open questions

- The model-graded eval suites have no bulk-orchestration suite (those cases moved to the tool's tests), so no eval covers the subagent filling `pending_team_question`;
  a `step-1d-signals` case for it is the next addition.
