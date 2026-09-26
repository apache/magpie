<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Change-request contract binding

The PR operations in this skill are the GitHub *resolution* of the
backend-neutral [`contract:change-request`](../../../../tools/change-request/)
verbs. Triage speaks the contract; the `gh` / GraphQL commands shown
in the steps below are how the GitHub adapter ([`tools/github/`](../../../../tools/github/))
resolves those verbs. A project that declares a different
`change_request.backend` in `<project-config>/project.md` — `jira-patch`
(patches on JIRA issues, landed via SVN) or `mail-patch` (`[PATCH]`
threads on `dev@`, landed via SVN) — resolves the same verbs against
its own backend, and this skill drives it unchanged.

| Triage operation | Contract verb | GitHub resolution (this skill) |
|---|---|---|
| Fetch the candidate queue (Step 1) | `list_open(filter)` | aliased GraphQL PR search |
| Pull one PR out for individual handling | `get(id)` | `gh pr view` / `gh api` |
| Read review history (last-comment-by-viewer, stale reviewer) | `get_discussion(id)` | GraphQL reviews / comments |
| CI-rerun and mark-ready gates (Step 2) | `status(id)` | GraphQL check + mergeable state |
| *comment* disposition (Step 4) | `post_review(id, comment, body)` | `gh pr edit --body` / comment |
| *close* disposition (Step 4) | `reject(id, reason)` | `gh pr close` |

Triage **never** calls `land` — merging is out of scope for this skill
(it lives in `pr-management-quick-merge` and the maintainer's own
merge command). Backends whose `status` returns `checks: none` /
`mergeable: unknown` (a JIRA patch with no pipeline, a bare `[PATCH]`
thread) degrade the CI-rerun and mark-ready gates to advisory: the
skill falls back to a human-judgement prompt rather than blocking. See
the contract's `status` graceful-degradation note.
