<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Fetch queries

Companion to [`SKILL.md`](SKILL.md). Per-tracker query patterns for Step 1 — fetch open issues and issues closed in the `since:` window.

Fields needed for classification: `number`, `title`, `createdAt`, `updatedAt`, `labels` (names), `state`, `assignees` (count), `comments` (count), `milestone` (title), `author` (login).

Open issues:

| Tracker | Query pattern |
|---|---|
| GitHub Issues | `gh issue list --repo <upstream> --state open --json number,title,createdAt,updatedAt,labels,comments,assignees,milestone --limit 1000` |
| JIRA | JQL: `project = <issue-tracker-project> AND status != Done ORDER BY created DESC` with the fields above |
| Other | Project-specific query from `<project-config>/issue-tracker-config.md` |

Also fetch issues closed in the last `since:` window (default: 7 days) for the closed-this-week count:

| Tracker | Query pattern |
|---|---|
| GitHub Issues | `gh issue list --repo <upstream> --state closed --json number,closedAt,labels --limit 200` filtered to `closedAt >= since` |
| JIRA | JQL: `project = <issue-tracker-project> AND status = Done AND updated >= -7d` |

Paginate until exhausted; batch size 100 is safe.
