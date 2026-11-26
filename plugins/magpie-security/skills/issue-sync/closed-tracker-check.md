<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — Step 1g — recently-closed trackers

Part of Step 1 in [`gather.md`](gather.md), which says when to read this file.

For **closed** trackers carrying the `announced` label (which `sync all` includes alongside open issues),
the CNA-tool record is `public` and the issue closed at Step 15, but propagation to `cve.org` takes minutes to days.
Once cve.org shows it published, the reporter is owed a final *"CVE is live"* email.

The check is read-only and uses the MITRE CVE Services API v2
([`tools/cve-org/tool.md`](../../../../tools/cve-org/tool.md#publication-state-check--check-published)).
For each closed-`announced` tracker in this run:

1. Extract the `CVE-YYYY-NNNNN` ID from the tracker's *CVE tool link* body field.
2. Call the API as a plain command (a pipe keeps it inside the sandbox under the secure setup),
   and read `.cveMetadata.state` and `.cveMetadata.datePublished` from its JSON output:
   ```bash
   uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-sync cve-check-published <CVE-ID>
   ```
3. Write `{cve_id, cve_org_state, date_published, lookup_failed, notification_sent_on_thread, body, comments, collaborators, public_advisory_url, advisory_records_configured, security_pages_configured, planner_exit, planner_result, planner_reason, site_recheck, refresh_pr_state, refresh_pr_lookup_failed}`
   and run `<sm> closed-announced`. `comments` are the 1a comments with their `author` and `authorAssociation`;
   `collaborators` is the tracker's collaborator list, for a backend whose comments carry no association.
   Only a comment by the team (`OWNER` / `COLLABORATOR`, or a login in `collaborators`) can carry the state markers below; pass the full collaborator list, since team members with access through a GitHub team show as `MEMBER`.
   Its `cve_org` is the move:
   `notify` (propose the *CVE-published* reporter email in Step 2b), `already_notified` (a prior *"CVE-published reporter notification drafted"* comment and a sent message on the thread — record it),
   `wait` (*"cve.org shows RESERVED; propagation not complete yet"*), `blocker` (the record was rejected after publication: no email, flag it to the security team),
   `retry` (*"cve.org lookup failed — try again next sync"*; never propose a notification on an absent response) or `skip` (no CVE ID: a closing disposition, dropped from the sweep).

**Gmail-budget.** The cve.org check is one HTTP call per tracker, not metered against the Gmail budget,
but within the "≤ 1 extra HTTP round-trip per tracker" soft limit for closed-bucket scans:
with several closed trackers in scope, run the checks in parallel via the subagent fanout (one `vetted-op-read` per subagent), not serially in the orchestrator.

**Security-pages checklist.** The same closed-`announced` bucket is the only place the post-announcement security-pages step can be observed:
the Step 14 close-out adds `announced` and closes the tracker in one apply, so an open tracker never carries the trigger state.
The same command scans the team's comments from the 1a fetch — no extra API call — for the ticked checklist item
`- [x] <!-- apache-magpie: security-pages-checklist v1 -->` and for a comment opening with `<!-- apache-magpie: security-pages-reminder v1 -->`,
and sets `security_pages_reminder_pending` only when the *Public advisory URL* is populated and neither exists
(an unticked box in the hand-off comment is the pending state, not the satisfied one).
Step 2b turns a pending flag into the *Security-pages reminder comment* proposal ([`signals-to-actions.md`](signals-to-actions.md)).
Pass `security_pages_configured: false` when [`<project-config>/project.md`](../../../../<project-config>/project.md#repositories) has no `security_pages_url` (unset, empty or still `TODO`):
the project has no security page to update, so the flag stays `false`, the output carries `security_pages: not_configured`,
and the observed state records *"security pages: not configured — no reminder"*. `/magpie-setup:setup config` offers to create the page.

**Advisory records.** When [`<project-config>/project.md`](../../../../<project-config>/project.md#advisory-records) declares an `advisory_records` block,
sync also records the CVE in the project's own security records — a site repository over Git or Subversion
([`docs/security/advisory-records.md`](../../../../docs/security/advisory-records.md)).
Without the block, record *"advisory records: not configured — skipped"* in the observed state and do nothing else.
With it, `security_pages_reminder_pending` is always `false`: sync proposes the edit itself instead of reminding the release manager.
The record normally went to the site already, in the pass that recorded the advisory's announcement ([`post-advisory-records.md`](post-advisory-records.md)); this scan follows it up and catches the trackers that pass did not record.
`closed-announced` prints the step in `advisory_records`: `done` (an `advisory-records v1` comment exists and cve.org has not listed the CVE yet, or the check below is finished), `waiting_for_cve_org` (no record yet and not `PUBLISHED` yet; the tool refuses before publication too — never work around it) or `run_planner`.
Once cve.org lists a CVE the site already records, it prints `recheck`: compare the site's record with the one regenerated now, as [`post-advisory-records.md`](post-advisory-records.md) describes,
and pass the result back as `site_recheck` (`unchanged`, `differs`, `unverified`, `failed`), which yields `recheck_unchanged` (propose the closing `advisory-records-recheck v1` comment), `refresh` (propose the refresh), `recheck_unverified` (a blocker: the entry cannot be compared) or `retry_recheck` (*"try again next sync"*).
A refresh comment's pull request is then followed like the first one: `check_refresh_pr` (pass `refresh_pr_state`, or `refresh_pr_lookup_failed: true`), then `refresh_pr_open`, `refresh_pr_merged` (propose the `advisory-records-refresh-merged v1` comment), or, closed unmerged, `refresh` again with `refresh_pr_closed_url` and `refresh_attempt`.
An `advisory-records-recheck v1` or `advisory-records-refresh-merged v1` comment (or a direct-mode refresh comment) ends the check, so the site's record is read once.
With `advisory_records.publish: pull-request`, pass `advisory_records_publish: pull-request` too; the record then goes through a pull request,
and the `advisory-records v1` comment names it, so `done` waits for an `advisory-records-merged v1` comment instead.
`closed-announced` may first ask for that pull request's state, as two plain read-only commands (`<site repo>` is `pull_request.repo`, or the `owner/name` of a GitHub `repository` URL):

- `check_pr` — the comment names `records_pr_url`: `gh pr view <records_pr_url> --json state,url`; pass its `state` as `records_pr_state`.
- `find_pr` — no comment yet: `gh pr list --repo <site repo> --head <pull_request.branch with the CVE ID> --state all --json state,url`;
  pass an `OPEN` or `MERGED` entry over a `CLOSED` one as `records_pr_state` and `records_pr_url`, or `records_pr_state: NONE` when the list is empty.
- A failed lookup passes `records_pr_lookup_failed: true` (`retry_pr_lookup`: try again next sync, propose nothing).

The answer is `pr_open` (observed state *"advisory records: <URL> open"*, nothing to propose), `pr_merged` (propose the merged comment),
`pr_closed` (a blocker naming the pull request), `record_pr` (a pull request exists but no comment records it: propose that comment, never a second pull request),
or the planner steps below, with `records_pr_closed_url` when only a closed pull request was found:

3. Write the record to the session scratch directory:
   `uv run --project <framework>/tools/cve-tool-vulnogram/generate-cve-json generate-cve-json <N> --output <scratch>/<CVE-ID>.json`.
4. Run the planner as a plain command, without `--apply`.
   Each `advisory_records` key maps to the flag of the same name (`layout`, `vcs`, `repository`, `branch`, `remote`, `commit_message`,
   and the layout's `path`, `indent` → `--json-indent`, `keep_cna_private`, `format`, `release_line_parts`, `section_name`, `section_template`, `entry_template`, `fix_commit_template`, `section_parent`;
   `publish`, and in pull-request mode `pull_request.repo` → `--pr-repo`, `.branch` → `--pr-branch`, `.title` → `--pr-title`, `.fork` → `--fork`, `.fork_remote` → `--fork-remote`);
   the working copy is `user.md → environment.advisory_records_clone`, else `advisory_records.working_copy`,
   and the fork and its remote are `user.md → environment.advisory_records_fork` / `advisory_records_fork_remote`, else the `pull_request` keys:
   ```bash
   uv run --project <framework>/tools/cve-tool-vulnogram/generate-cve-json advisory-records --layout <layout> --working-copy <path> --path '<path template>' --record <scratch>/<CVE-ID>.json --cve-org-state PUBLISHED --date-published <datePublished> [--reported-date <date>] [layout flags]
   ```
   In pull-request mode under the secure setup, add `--vetted-git --worktree-root <dir> --workspace <dir>` when the site policy is in place
   (`uvx --from ~/.claude/magpie/vetted-ops vetted-op-git --policy-from <site checkout> policy` prints its `worktree_roots` and `workspace`);
   the commands are then `vetted-op-git` operations ([`docs/security/advisory-records.md`](../../../../docs/security/advisory-records.md#publishing-through-vetted-op-git)).
   For `release-page`, pass `--reported-date` (the date of the first message on the *Security mailing list thread*).
   When the output names a missing input (`--release-date` for a new release section, `--fix-commit`, `--affects`), find it on the tracker,
   in [`release-trains.md`](../../../../<project-config>/release-trains.md) or in the release's announcement, and run it again; ask the user when none of them has it.
5. Pass the planner's exit code (and `proposed` / `unchanged`, and a refusal's reason) back to `closed-announced`:
   `pending` → `advisory_records_pending: true`, keeping the tool's diff and numbered commands (and in pull-request mode its pull-request title and body) for Step 2b;
   `already_recorded`; `pending_checkout` → `advisory_records_pending: true` with the single `checkout` command;
   `refused` → a blocker when the page cannot be parsed or already holds the CVE under another release; `config_error` → show the user.

**When the tracker has no CVE ID.** Closed trackers without a `CVE-YYYY-NNNNN` in the *CVE tool link* body field
are closing dispositions (`invalid` / `duplicate` / `wontfix`):
skip the cve.org check entirely and drop the tracker from the closed-bucket sweep.
