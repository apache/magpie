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
3. Write `{cve_id, cve_org_state, date_published, lookup_failed, notification_sent_on_thread, body, comments, public_advisory_url, advisory_records_configured, planner_exit, planner_result, planner_reason}`
   and run `<sm> closed-announced`. Its `cve_org` is the move:
   `notify` (propose the *CVE-published* reporter email in Step 2b), `already_notified` (a prior *"CVE-published reporter notification drafted"* comment and a sent message on the thread — record it),
   `wait` (*"cve.org shows RESERVED; propagation not complete yet"*), `blocker` (the record was rejected after publication: no email, flag it to the security team),
   `retry` (*"cve.org lookup failed — try again next sync"*; never propose a notification on an absent response) or `skip` (no CVE ID: a closing disposition, dropped from the sweep).

**Gmail-budget.** The cve.org check is one HTTP call per tracker, not metered against the Gmail budget,
but within the "≤ 1 extra HTTP round-trip per tracker" soft limit for closed-bucket scans:
with several closed trackers in scope, run the checks in parallel via the subagent fanout (one `vetted-op-read` per subagent), not serially in the orchestrator.

**Security-pages checklist.** The same closed-`announced` bucket is the only place the post-announcement security-pages step can be observed:
the Step 14 close-out adds `announced` and closes the tracker in one apply, so an open tracker never carries the trigger state.
The same command scans the body and every comment the 1a fetch returned — no extra API call — for the ticked checklist item
`- [x] <!-- apache-magpie: security-pages-checklist v1 -->` and for a comment opening with `<!-- apache-magpie: security-pages-reminder v1 -->`,
and sets `security_pages_reminder_pending` only when the *Public advisory URL* is populated and neither exists
(an unticked box in the hand-off comment is the pending state, not the satisfied one).
Step 2b turns a pending flag into the *Security-pages reminder comment* proposal ([`signals-to-actions.md`](signals-to-actions.md)).

**Advisory records.** When [`<project-config>/project.md`](../../../../<project-config>/project.md#advisory-records) declares an `advisory_records` block,
sync also records the CVE in the project's own security records — a site repository over Git or Subversion
([`docs/security/advisory-records.md`](../../../../docs/security/advisory-records.md)).
Without the block, record *"advisory records: not configured — skipped"* in the observed state and do nothing else.
With it, `security_pages_reminder_pending` is always `false`: sync proposes the edit itself instead of reminding the release manager.
`closed-announced` prints the step in `advisory_records`: `done` (an `advisory-records v1` comment exists), `waiting_for_cve_org` (not `PUBLISHED` yet; the tool refuses before publication too — never work around it) or `run_planner`, then:

3. Write the record to the session scratch directory:
   `uv run --project <framework>/tools/cve-tool-vulnogram/generate-cve-json generate-cve-json <N> --output <scratch>/<CVE-ID>.json`.
4. Run the planner as a plain command, without `--apply`.
   Each `advisory_records` key maps to the flag of the same name (`layout`, `vcs`, `repository`, `branch`, `remote`, `commit_message`,
   and the layout's `path`, `indent` → `--json-indent`, `keep_cna_private`, `format`, `release_line_parts`, `section_name`, `section_template`, `entry_template`, `fix_commit_template`, `section_parent`);
   the working copy is `user.md → environment.advisory_records_clone`, else `advisory_records.working_copy`:
   ```bash
   uv run --project <framework>/tools/cve-tool-vulnogram/generate-cve-json advisory-records --layout <layout> --working-copy <path> --path '<path template>' --record <scratch>/<CVE-ID>.json --cve-org-state PUBLISHED --date-published <datePublished> [--reported-date <date>] [layout flags]
   ```
   For `release-page`, pass `--reported-date` (the date of the first message on the *Security mailing list thread*).
   When the output names a missing input (`--release-date` for a new release section, `--fix-commit`, `--affects`), find it on the tracker,
   in [`release-trains.md`](../../../../<project-config>/release-trains.md) or in the release's announcement, and run it again; ask the user when none of them has it.
5. Pass the planner's exit code (and `proposed` / `unchanged`, and a refusal's reason) back to `closed-announced`:
   `pending` → `advisory_records_pending: true`, keeping the tool's diff and numbered commands for Step 2b;
   `already_recorded`; `pending_checkout` → `advisory_records_pending: true` with the single `checkout` command;
   `refused` → a blocker when the page cannot be parsed or already holds the CVE under another release; `config_error` → show the user.

**When the tracker has no CVE ID.** Closed trackers without a `CVE-YYYY-NNNNN` in the *CVE tool link* body field
are closing dispositions (`invalid` / `duplicate` / `wontfix`):
skip the cve.org check entirely and drop the tracker from the closed-bucket sweep.
