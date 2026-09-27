<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-pr — scope limits and failure modes

## What this skill does **not** do

- **Does not run a validity discussion.** The skill's contract is
  that the assessment has already happened; the tracker lands
  `Assessed`. If you want a validity discussion, do not use this
  skill — open the tracker manually with `Needs triage` instead.
- **Does not draft a reporter reply.** There is no reporter; the
  PR author is the de-facto finder, and any communication with
  them happens on the public PR (which already exists).
- **Does not create the GHSA.** GHSA creation, advisory drafting,
  and the `<upstream>` private-repo coordination all happen
  later in the process — see
  [`docs/security/process.md`](../../../../docs/security/process.md#process-reference-the-16-steps).
- **Does not characterise the public PR as a security fix until
  the advisory ships.** The tracker URL itself is a public-safe
  identifier and may appear in the PR description as a
  cross-reference; what does not appear is the CVE ID, the words
  *"vulnerability"* / *"security fix"* / *"advisory"*, and any
  verbatim quote from the tracker discussion. See the
  [Confidentiality of `<tracker>`](../../../../AGENTS.md#confidentiality-of-the-tracker-repository)
  rule.
- **Does not run `security-issue-sync` on the new tracker.** The
  initial body is already coherent; sync's job (reconciling PR
  state, milestone, assignee against current reality) is not
  needed on a tracker that is being created from those exact
  signals. Run sync only when the PR or thread state evolves
  later.

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `gh api repos/<upstream>` returns 404 | Repo placeholder not substituted | Re-read `<project-config>/project.md` for the `upstream_repo:` value. |
| PR is `CLOSED` (not merged) | Fix abandoned upstream | Stop and confirm with the user that a tracker is still wanted; otherwise abandon. |
| `gh api repos/<tracker>/issues` returns 422 | Missing or invalid title / body field shape | Re-check the body against the issue template's eleven fields; the `### <field>` headings must match exactly (case-sensitive). |
| `addProjectV2ItemById` returns `not found` for the project | Project-board node ID changed | Re-run the introspection query in [`project-board.md`](../../../../tools/github/project-board.md) and update [`project.md`](../../../../<project-config>/project.md). |
| Multiple existing trackers match the duplicate-guard search | Earlier closed-as-duplicate trackers reference the PR number in passing | Surface all hits to the user; let them confirm `force` to proceed anyway. |
| Mixed-scope PR (e.g. `<scope-b>/` + `<scope-a>/`) | The fix lives in more than one product | Stop; surface the per-scope split decision to the user before re-invoking. |
