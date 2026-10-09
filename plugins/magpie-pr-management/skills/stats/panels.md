<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# What each dashboard panel means

Read this only when the maintainer asks what a panel or a number means.
Every value is computed by `pr-management stats build` ([`tools/pr-management`](../../../../tools/pr-management/README.md#stats-build--the-pr-management-stats-dashboard)); the definitions it shares with `pr-management-triage` — triage marker, maintainer, bot — are its [shared rules](../../../../tools/pr-management/README.md#shared-rules).
The dashboard's own legend repeats the colour conventions.

| Panel | What it answers |
|---|---|
| **Title + context line** | When the snapshot was taken, by whom, and the closed-PR window (default six weeks). |
| **Hero cards, row 1** | Health rating; open non-bot PRs split by draft state and author class; the ready-for-review queue; untriaged contributor non-drafts, with those older than four weeks called out. |
| **Hero cards, row 2** | How much triage the quality-criteria marker sees (*Quality Criteria triaged*) against broad maintainer engagement with no marker (*De-facto triaged*) — the gap is triage the marker counter misses; AI-assisted triage; bot PRs, which follow their own lifecycle. |
| **What needs attention** | The recommendation rules, high priority first, each with the paste-clean slash command to run. Never empty: a quiet queue shows one "no urgent actions" card. |
| **Trends over time** | Open backlog, PRs opened by author class, ready-queue size, triage velocity (AI vs manual), triage coverage by week opened. The comment window per PR is finite, so older weeks of the two triage series under-count. |
| **Drafts & closes by person** | Who converts PRs to draft and who closes them: a deterministic action concentrated on one person is an automation candidate; a judgement action concentrated on one person is a bus factor. |
| **Closure velocity** | Merged vs closed-without-merge per week. |
| **Opened vs closed** | Whether the backlog grew or shrank each week; the net-delta lines put numbers on it. |
| **Ready-for-review trend** | Cumulative ready PRs per top-pressure area; a climbing line means review velocity is not keeping up with promotion. |
| **Closed by triage reason** | Each week's closures as merged / closed after the author responded / closed with no response (a stale sweep) / closed without triage. |
| **Pressure by area** | Areas ranked by a weighted count of urgent contributor PRs: untriaged by the author's last activity (≥ 4 weeks 5, ≥ 1 week 3, else 1), stale-triaged 2, ready 1, drafts and collaborator PRs 0. Areas with fewer than three contributor PRs are noise and are dropped. |
| **Ready queue by CODEOWNER** | For each owner, ready PRs touching a file they own, and how many of those wait on the author's reply to that owner; the no-match row shows paths CODEOWNERS does not cover. |
| **Triage funnel** | Every contributor non-draft in exactly one bucket: ready, responded, waiting on an AI-drafted note only, waiting on a reply to a maintainer, not yet triaged. |
| **Ready-for-review split** | Why ready PRs wait: never reviewed, discussed with no decision, changes requested, approved and awaiting merge — with the age of each. |
| **Triager activity** | Distinct PRs each maintainer engaged with per week, AI-assisted vs manual. |
| **Detailed tables** | Triaged PRs closed since the cutoff, and triaged PRs still open, per area. |
| **Legend / methodology** | Colours, columns, how the data was fetched, and — when the closed series came from the capped search index — which weeks are truncated. |

The health rating adds 2 points for any untriaged contributor PR older than four weeks, and 1 each for more than 30 in the one-to-four-week bucket, more than 100 ready PRs, and more than 20 stale-triaged drafts: 0 is healthy, 1–2 needs attention, 3 or more needs action.
