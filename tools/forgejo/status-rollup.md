<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Forgejo / Gitea — Status-rollup comment](#forgejo--gitea--status-rollup-comment)
  - [The rollup comment shape](#the-rollup-comment-shape)
  - [Summary — action labels](#summary--action-labels)
  - [The entry body](#the-entry-body)
  - [Upsert recipe — append to an existing rollup, or create one](#upsert-recipe--append-to-an-existing-rollup-or-create-one)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Forgejo / Gitea — Status-rollup comment

Every agent-authored status update on a `<tracker>` issue (the import
receipt, each sync pass, CVE allocation, dedupe merges, fix-PR
announcements, etc.) lands in **one single rollup comment** per
tracker. Each pass appends a new *entry* to that comment instead of
posting a fresh one. The result: scrolling a tracker's timeline shows
one rollup comment plus the human discussion, not twenty bot comments
drowning out the actual conversation.

This file is the canonical shape + upsert recipe for Forgejo/Gitea.

## The rollup comment shape

One comment per tracker, identified by an opening HTML marker on the
first line:

```markdown
<!-- <tracker-name> status rollup v1 — all bot-authored status updates fold into this single comment. -->
<details><summary>YYYY-MM-DD · @user · <Action></summary>

<entry body>

</details>

---

<details><summary>YYYY-MM-DD · @user · <Action></summary>

<entry body>

</details>
```

Rules (all load-bearing — breaking any of them breaks Markdown rendering):

- **First line is the marker.** `<!-- <tracker-name> status rollup v1 — … -->`
  identifies the comment as the rollup.
- **Every entry is its own `<details>` block.** Including the very
  first one (the import receipt).
- **Open tag is one line.** Write `<details><summary>…</summary>` on
  a single line.
- **Summary contains three fields, `·`-separated**, in this order:
  `YYYY-MM-DD · @handle · <Action>`. Optional fourth field in parentheses is allowed only for disambiguation.
- **Exactly one blank line after `<summary>…</summary>`.**
- **Exactly one blank line before `</details>`.**
- **No leading whitespace on any line inside the entry.**
- **Entries are separated by a bare `---` on its own line**, with one
  blank line on each side.
- **Chronological order — newest at the bottom.**

## Summary — action labels

Each skill emits one of the following `<Action>` strings so the summary
line tells the reader at a glance *what* the entry represents:

| Emitting skill | `<Action>` value | Optional parenthetical |
|---|---|---|
| `security-issue-import` | `Import` | class + reporter, e.g. `Import (Report, Jane Doe)` |
| `security-issue-sync` | `Sync` | one-phrase headline |
| `security-cve-allocate` | `CVE allocated` | the allocated ID |
| `security-issue-deduplicate` | `Merge (kept)` / `Merge (dropped)` | counterpart number |
| `security-issue-fix` | `Fix PR` | upstream PR number |

## The entry body

Inside the `<details>` block, write what the skill used to write in
its pre-collapse body — the bold headline, the `**Next:**` line, the
reporter-notification line, the full rationale.

Required elements inside every entry body:

- **Bold headline** as the first line (e.g. `**Sync 2026-04-21 — pr merged → fix released.**`).
- **`**Next:**` line** — one sentence on what comes next.
- **Reporter-notification line** when applicable.

## Upsert recipe — append to an existing rollup, or create one

To append an entry to an existing rollup comment on Forgejo/Gitea, the agent must:

1. **Find the existing rollup comment:**
   Fetch the issue comments and find the one starting with `<!-- <tracker-name> status rollup v1`:
   ```bash
   curl -s -H "Authorization: token $TEA_TOKEN" \
     "$FORGEJO_HOST/api/v1/repos/<tracker>/issues/<N>/comments" > comments.json
   # Use jq to find the comment ID and body
   ```
2. **Append or Create:**
   - If found, append the new `<details>...` block to the existing body and update the comment using `PATCH /api/v1/repos/<tracker>/issues/comments/<comment-id>`.
   - If not found, create a new comment with the marker and the first `<details>...` block using `POST /api/v1/repos/<tracker>/issues/<N>/comments`.

Always use a temporary file to construct the JSON payload properly before sending via `curl`.
