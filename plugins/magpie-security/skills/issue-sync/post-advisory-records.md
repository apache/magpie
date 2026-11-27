<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — records after the advisory

Part of the Step 2b lookup in [`signals-to-actions.md`](signals-to-actions.md), which says when to read this file.

- **Advisory-records update** — records the published CVE in the project's own security records
  (the site repository its security pages are built from), when the project configures
  [`advisory_records`](../../../../<project-config>/project.md#advisory-records)
  ([`docs/security/advisory-records.md`](../../../../docs/security/advisory-records.md)).
  It replaces the security-pages reminder for those projects: sync makes the edit instead of asking the release manager for it.

  **Trigger, at the announcement.** The *Advisory archived on `<users-list>`* combined apply is being proposed
  (the user confirmed the archive URL; [`gather.md` 1d](gather.md#1d-mine-comments-and-mail-messages-for-actionable-signals)),
  `advisory_records` is configured, no comment carries the `advisory-records v1` marker,
  and in pull-request mode `gh pr list --repo <site repo> --head <branch> --state all` finds no open or merged pull request.
  Generate the record the apply is about to push, with the confirmed URL:
  `generate-cve-json <N> --advisory-url <URL> --output <scratch>/<CVE-ID>.json`,
  and run the planner on it with `--announced-url <URL>` and `--public-date <the announcement's date>` in place of the cve.org flags
  ([`closed-tracker-check.md`](closed-tracker-check.md) step 4 maps the configuration to flags).
  A change becomes one more item of the same batch, under the same confirmation; no change, no item.

  **Trigger, after cve.org.** Step 1g recorded `advisory_records_pending: true` for a closed-`announced` tracker
  the announcement pass did not record (no `advisory-records v1` comment): cve.org reports the CVE `PUBLISHED`,
  in pull-request mode no open or merged pull request comes from the configured branch,
  and the planner returned a change (or, with no working copy yet, a `checkout` command).
  Before either trigger there is no proposal — the planner refuses, and the observed state says *"waiting for cve.org"*.
  Without `advisory_records` there is no proposal either; the observed state says *"not configured — skipped"*.

  **Proposed action.** One numbered item showing the planner's file change (the diff it printed) and its numbered commands, verbatim and in order.
  In the direct mode they are [`magpie-vcs`](../../../../tools/vcs/README.md) commands:
  the clean check, the branch check (Git), `update`, the planner re-run with `--apply`, `stage`, `diff`, `commit`, and `push` (Git).
  On Subversion, say that the `commit` publishes the change.
  With no working copy, the item is the single `checkout` command; the change is proposed on the next sync.
  At the announcement the item runs after the apply has regenerated and pushed the CVE JSON (its steps 4 and 5):
  the `--apply` run takes the record regenerated then, so the site gets exactly the JSON the CVE tool holds
  (sorted keys, the configured indent, no `CNA_private`).

  **Pull-request mode** (`advisory_records.publish: pull-request`). Show the pull request's title and body with the commands,
  and say that the push publishes the branch on the fork and the last command publishes the pull request;
  between the commit and the push, sync runs the configured adversarial review ([`apply-and-push.md`](apply-and-push.md)).
  When Step 1g found only a closed pull request (`records_pr_closed_url`), name it in the item: the team removed its status comment to try again.

  - **Through `vetted-op-git`**, under the secure agent setup: when `uvx --from ~/.claude/magpie/vetted-ops vetted-op-git --policy-from <site checkout> policy`
    reports the site repository as `upstream` with `worktree_roots`, plan from the forge, never from the checkout (the sandbox cannot read it):
    save each file the record touches at the base branch with `uvx --from ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-sync --policy-from <site checkout> --save <name> repo-file <path> <base>`
    and pass it as `--from-saved <path>=<saved file>`; for a 404, pass `--site-absent <path>` (the planner refuses a path answered by neither;
    for `--backfill`, save `repo-tree <base>` and pass it as `--site-listing`).
    `--policy-from` takes only a checkout your `operator-git.toml` lists for the site repository.
    Then run the planner with `--vetted-git --worktree-root <one of them> --workspace <its workspace>` and those flags
    (and `--upstream-remote`), and the commit's attribution trailer resolved per [`docs/setup/commit-attribution.md`](../../../../docs/setup/commit-attribution.md): the project's convention as `--commit-trailer <Key: value>` (or `--no-commit-trailer` when the convention is none), else `--agent '<agent name and version>'`, which writes the framework's own `Generated-by: <agent name and version>`; the planner refuses `--vetted-git` without one of the three.
    Its eight commands: `git-fetch`, whose printed commit replaces `<start-sha>`, `git-worktree-add`,
    the planner re-run with `--apply` into the worktree, `vetted-op-checks`, `git-stage`, `git-commit`, `git-push-branch` to the operator's fork, and `git-pr-create`.
    When the site policy sets `[git] site_hooks = "skip"` (`vetted-op-git --policy-from <site checkout> policy` prints `site_hooks = 'skip'`), pass `--site-hooks-skipped`:
    the checks step gets `--skip-site-hooks`, and the pull-request body ends with *"Hooks were not run locally; the repository's CI checks this PR."*
    Say both in the item. Without it, read `.pre-commit-config.yaml` the same way first: when the site has one, its hooks cannot run in the sandbox,
    so skip the vetted route and hand over the `magpie-vcs` commands below from the start.
    If `vetted-op-checks` still refuses after the worktree exists, hand over the planner's `fallback_commands` instead:
    they first remove the worktree (with its uncommitted change) and delete its never-pushed branch, then run the `magpie-vcs` commands,
    which make the same branch again in the checkout, the one later syncs look the pull request up by.
    Each `vetted-op-git` call is a write the user confirms in the harness; run them as printed, with the literal `~`.
  - **Otherwise**, the eleven `magpie-vcs` and `gh` commands of the site working copy: the clean check, the branch check (the base branch), `update`, `new-branch`,
    the planner re-run with `--apply` (it also writes the pull-request body file), `stage`, `diff`, `commit`, `push` to the operator's fork,
    `switch` back to the base branch, and `gh pr create` against the site repository.
    `gh pr create` carries `MAGPIE_ALLOW_SECURITY_LANG=1`, agent-guard's exemption for a disclosure that is already public;
    keep it — the planner prints the command only past its publication gate.
    Under the secure setup the site checkout is out of the sandbox's reach: hand these to the user, and name what `setup config` proposes to enable the vetted route.

  **Guard.** Never run a command the user has not confirmed, never edit the page or the JSON file by hand,
  and never push to another branch or remote than the configured ones — in pull-request mode, never to the site repository at all.
  The site pull request is public: its title, body and commit message carry only what the planner prints (the published record's identifier, files and announcement), never tracker text.
  The planner is idempotent: an already-recorded CVE yields `unchanged` and no proposal.
  In pull-request mode an open or merged pull request from the configured branch stands for the record, so there is never a second one.

- **Advisory-records pull request, already open** — Step 1g returned `record_pr`:
  a pull request from the configured branch exists (`records_pr_url`) but no `advisory-records v1` comment records it.
  **Proposed action.** Only the status comment that records it, as [`apply-and-push.md`](apply-and-push.md) describes for pull-request mode; no commands.

- **Advisory-records pull request merged** — Step 1g returned `pr_merged`: the pull request the `advisory-records v1` comment names has merged.
  **Proposed action.** A short status comment: line 1 is the marker
  ```html
  <!-- apache-magpie: advisory-records-merged v1 -->
  ```
  then one sentence naming the merged pull request,
  then the ticked item `- [x] <!-- apache-magpie: security-pages-checklist v1 --> Project security pages updated with CVE_ID`.
  **Guard.** Once per tracker: never re-propose while a team comment opens with that marker.

- **Advisory-records check after cve.org** — Step 1g returned `recheck`: the record went to the site earlier
  (an `advisory-records-merged v1` comment, or a direct-mode `advisory-records v1` comment) and cve.org now lists the CVE `PUBLISHED`.
  With a site policy, read the site's copy of each file the record touches from the forge, never the checkout: `uvx --from ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-sync --policy-from <site checkout> --save <name> repo-file <path> <base>`,
  and run the planner (no `--apply`) with `--recheck --from-saved <path>=<saved file>` (or `--site-absent <path>` for a 404) and the record regenerated now.
  A GitHub site without a site policy is read with `gh api repos/<site repo>/contents/<path>?ref=<base> --jq .content` (the `.content` it prints is what `--from-saved` takes).
  A direct-mode site with a working copy the session can read (a Subversion site among them) is rechecked there instead:
  bring it up to date with the `update` command and run the planner with `--recheck --working-copy <copy>`. `--recheck` compares contents, not presence: a JSON file must equal the rendered record,
  and a page entry must match the entry rendered from it, or the planner reports `unverified`, since a hand-kept page entry cannot be replaced safely.
  Pass `site_recheck: unchanged` for `unchanged`, `differs` for a proposed change, `unverified` for `unverified`, and `failed` when the read fails.
  `recheck_unverified` is a blocker: the team compares the entry by hand and records the result with the closing comment below; it is never reported as matching.
  `recheck_unchanged` (*"advisory records: the site record matches the published record"*) proposes one closing status comment, so the site is read once:
  line 1 is the marker
  ```html
  <!-- apache-magpie: advisory-records-recheck v1 -->
  ```
  then `unchanged:` and one sentence saying the site's record matches the published one.
  **Guard.** Once per tracker: that marker, like the refresh-merged marker below, ends the check, and `closed-announced` returns `done`.

- **Advisory-records refresh** — Step 1g returned `refresh`: the site's record differs from the published one
  (with `refresh_pr_closed_url` when an earlier refresh pull request was closed without merging: name it in the item).
  **Proposed action.** The same publication as the update above, on the branch `advisory-records/<CVE-ID>-refresh`
  (`--pr-branch 'advisory-records/{cve_id}-refresh' --pr-title 'Update {cve_id} in the security pages'`), against the real site checkout;
  for `refresh_attempt` 2 and later the branch is `advisory-records/<CVE-ID>-refresh-<refresh_attempt>`, since the earlier branch is still on the fork.
  After it succeeds, post a status comment whose line 1 is the marker
  ```html
  <!-- apache-magpie: advisory-records-refresh v1 -->
  ```
  then one sentence naming the pull request's full URL (or, in the direct mode, the commit, which ends the check).

- **Advisory-records refresh pull request** — Step 1g follows the latest refresh comment's pull request as it follows the first one:
  `check_refresh_pr` asks for `gh pr view <refresh_pr_url> --json state,url` (pass `state` as `refresh_pr_state`, or `refresh_pr_lookup_failed: true`);
  `refresh_pr_open` is an observed-state line, `retry_refresh_lookup` is *"try again next sync"*,
  a closed unmerged one returns to `refresh` above, and `refresh_pr_merged` proposes a short status comment whose line 1 is the marker
  ```html
  <!-- apache-magpie: advisory-records-refresh-merged v1 -->
  ```
  then one sentence naming the merged pull request. **Guard.** That marker ends the check: never re-propose while a team comment opens with it.

- **Advisory-records pull request open or closed** — `pr_open` is an observed-state line (*"advisory records: <URL> open"*), not a proposal.
  `pr_closed` is a blocker naming the pull request: propose nothing, neither a new pull request nor a reopen;
  the team decides how to record the CVE.

- **Security-pages reminder comment** — the ASF security-committers policy's post-announcement step *"The project team updates the
  project's security pages"* is a website edit, which sync cannot perform or gate the close-out on
  (the close-out fires on the archive-URL signal).
  Projects that configure `advisory_records` never get this reminder: the *Advisory-records update* above makes the edit.
  Nor do projects with no `security_pages_url`: there is no page to update, so the step does not exist for them
  (`/magpie-setup:setup config` asks whether the project has such a page and offers to create one).
  Sync carries the checklist item that records it: both hand-off comment variants embed a
  `- [ ] <!-- apache-magpie: security-pages-checklist v1 --> Project
  security pages updated with CVE_ID` box, and ticking it records the completion marker on the tracker.
  This proposal covers the marker still unrecorded after the advisory has shipped.

  **Trigger.** Step 1g recorded `security_pages_reminder_pending: true` for a closed-`announced` tracker —
  the *Public advisory URL* body field is populated (the advisory has demonstrably shipped),
  no comment holds a ticked `- [x] <!-- apache-magpie: security-pages-checklist v1 -->` item (the body never counts: it carries report text),
  and no comment carries the reminder marker below.
  The trigger state exists only on a closed tracker (the Step 14 close-out adds `announced` and closes in one apply),
  so this proposal is reached through the
  [1g](gather.md#1g-recently-closed-trackers--check-cveorg-publication-state)
  closed-bucket scan, never through the open-tracker signals.
  An unticked box in the hand-off comment is the *pending* state that fires the reminder, not the satisfied one.

  **Proposed action.** A short status comment tagging the release
  manager. Line 1 of the body is the reminder marker
  ```html
  <!-- apache-magpie: security-pages-reminder v1 -->
  ```
  followed by one sentence naming the outstanding item with a link to the project's security pages
  (the `security_pages_url` key from
  [`<project-config>/project.md`](../../../../<project-config>/project.md#repositories);
  a project without the key never reaches this proposal, see [`closed-tracker-check.md`](closed-tracker-check.md)), and
  the checklist item
  `- [ ] <!-- apache-magpie: security-pages-checklist v1 --> Project security pages updated with CVE_ID`,
  so ticking the box on either comment records the step.
  Per [*"Brevity: emails state facts, not context"*](../../../../docs/editorial-guidelines.md#brevity-emails-state-facts-not-context),
  state the outstanding item, not the rationale (the RM has already seen it in the hand-off comment).

  **Guard.** The reminder marker makes this once per tracker:
  never re-propose while a comment carrying `<!-- apache-magpie: security-pages-reminder v1 -->` exists, ticked or not.
  The checklist marker cannot serve as the guard, because the hand-off comment always carries it.
  Never propose editing the website, reopening the tracker, or any label on this signal's behalf.
