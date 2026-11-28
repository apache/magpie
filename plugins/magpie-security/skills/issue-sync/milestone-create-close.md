<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — create or close a milestone

Part of the Step 2b lookup in [`signals-to-actions.md`](signals-to-actions.md), which says when to read this file.

  **If the milestone does not yet exist**, the proposal says so and includes the exact `gh api` command to create it.
  Before constructing the create call, **run the upstream-date lookup** per
  [`<project-config>/milestones.md` § *Read the due date from upstream*](../../../../<project-config>/milestones.md#read-the-due-date-from-upstream):
  query `<upstream>` for the matching milestone (by scope label mapping) and, if found, reuse its `due_on` verbatim.
  Never guess a date.
  For a provider-wave milestone the description names the release manager, so the advisory owner is visible at a glance:

  **Use the Write tool** (not Bash) to write each field value verbatim
  to a temp file, then pass via `-F`.
  `<scratch>` is the session scratch directory as an absolute path (fall back to `$TMPDIR`); `gh` may run outside the sandbox, where `$TMPDIR` differs, so pass it absolute paths.

  *Write tool call:* `file_path: <scratch>/ms-title-<tracker>.txt`,
  `content: <Milestone>`

  *Write tool call:* `file_path: <scratch>/ms-desc-<tracker>.txt`,
  `content: <optional>`

  ```bash
  # Core or chart (due_on mirrored from upstream when available):
  gh api repos/<tracker>/milestones \
    -F title=@<scratch>/ms-title-<tracker>.txt \
    -f state=open \
    -F description=@<scratch>/ms-desc-<tracker>.txt \
    -f due_on='<ISO8601 from upstream, omit if upstream has none>'
  ```

  For provider waves, update the Write tool calls with:

  *Write tool call:* `file_path: <scratch>/ms-title-<tracker>.txt`,
  `content: Providers YYYY-MM-DD`

  *Write tool call:* `file_path: <scratch>/ms-desc-<tracker>.txt`,
  `content: Providers release cut on YYYY-MM-DD, RM: <Name>`

  ```bash
  # Provider wave (cut date + RM from the Release Plan wiki /
  # dev@ [VOTE] thread; upstream does not milestone providers
  # waves so due_on typically comes from the wiki):
  gh api repos/<tracker>/milestones \
    -F title=@<scratch>/ms-title-<tracker>.txt \
    -f state=open \
    -F description=@<scratch>/ms-desc-<tracker>.txt
  ```

  After the create call, assign the milestone via `gh issue edit <N> --milestone 'Providers YYYY-MM-DD'`
  (or by milestone number via the REST API if the milestone is closed).

  **Closing the milestone on the last close.** When a sync pass closes a tracker (the Step 15 terminal transition — cve.org reports PUBLISHED),
  check whether it was the last open issue on its milestone; if so, **propose closing the milestone itself** in the same run,
  as its own numbered item alongside the per-tracker close.
  Condition set and PATCH recipe: [`<project-config>/milestones.md`](../../../../<project-config>/milestones.md#closing-the-milestone).
  Concretely: after the per-tracker close lands, run
  `gh api 'repos/<tracker>/issues?milestone=<N>&state=open&per_page=1' --jq 'length'`
  — if it returns `0` and the milestone is still `open`, PATCH `state=closed` on `repos/<tracker>/milestones/<N>`.
  Do not auto-close an empty milestone whose trackers were closed for other reasons than Step 15 (e.g. `duplicate` / `invalid`):
  the closure applies only when every tracker landed through the terminal advisory flow.
