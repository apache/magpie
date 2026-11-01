<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Posting and close calls

Companion to [`SKILL.md`](SKILL.md). How to post confirmed proposal
comments (Step 6) and execute the two-step close.

<!-- BEGIN MAGPIE BLOCK: write-lock — generated from tools/dev/blocks/write-lock.md -->

**Write lock (one write phase per skill per repository).** The read and
classify steps above have no side effects and may overlap with any other
run. Posting does: two overlapping runs of this skill over the same
repository post the same comment or label twice, which is what makes
contributors distrust the bot. So before the first write of this step,
take the skill's write lock:

```bash
uvx --from ~/.claude/magpie/skill-lock skill-lock acquire issue-stale-sweep --repo <upstream> --note "<selector or pool summary>"
```

- Exit `0` (`status: acquired`): proceed. Keep the `token` from the JSON
  result for the release below. Then, **just before each write, re-read
  that item** and skip it if this skill's marker (its proposal comment or
  label) landed after your classify read: a run that classified before
  another run posted can reach its write step after that run released
  the lock. List skipped items in the recap as already handled.
- Exit `3` (`status: already_running`): **stop here and post nothing.**
  Show the maintainer the `holder` record (started, expires, note) and
  say this is not a failure of the sweep: another run of this skill is
  writing to the same repository. If the maintainer knows that run is
  dead, they clear it with the `--force` command in the result's `hint`
  and re-run this step; never clear it on your own.
- Exit `2`: report the error and stop.

Release it after the recap, and **also on the stop-and-surface path** when
a post fails, so a failed run never leaves the lock held for its lease:

```bash
uvx --from ~/.claude/magpie/skill-lock skill-lock release issue-stale-sweep --repo <upstream> --token <token>
```

The lock is scoped to this skill and `<upstream>` only; other skills and
other repositories never contend. It lives in the personal config layer
(`run/locks/`), never in the working tree, so it serialises runs from one
clone only. Runs from another clone or another machine are caught by the
re-read before each write, not by the lock. Details and exit codes:
[`tools/skill-lock/README.md`](../../../../tools/skill-lock/README.md).

<!-- END MAGPIE BLOCK: write-lock -->

For each confirmed proposal, post one comment via the tracker write API:

- **GitHub Issues**: `gh issue comment <N> --repo <upstream> --body-file <tmp>`.
- **JIRA**: REST POST to
  `<issue-tracker>/rest/api/2/issue/<KEY>/comment` with the body in
  the request payload.
- **Other trackers**: project-specific; the recipe lives in
  [`<project-config>/issue-tracker-config.md`](../../../magpie-setup/templates/issue-tracker-config.md).

**Use the file-via-Write-tool pattern for the body** — write the body to
`$TMPDIR/stale-sweep-<N>.md` via the Write tool, then pass with
`--body-file` or as a request payload. This avoids shell injection of
`$(...)` expansions in issue bodies that crossed a trust boundary at
ingest.

**Before posting, scrub the body for bare-name mentions** of maintainers
per the rule in
[`AGENTS.md`](../../../../AGENTS.md#mentioning-project-maintainers-and-security-team-members).

Apply **sequentially**, one comment at a time. After each post succeeds,
capture the returned comment URL for the recap in Step 7.

If any post call fails, stop and report the failure — do not retry
blindly. The user retries the remaining items with the `NN,...` selector.

**For `CLOSE-STALE` items**, the second-confirmation gate lives in
`SKILL.md` Step 6. The close calls themselves:

- **GitHub Issues**: `gh issue close <N> --repo <upstream> --reason "not planned"`.
- **JIRA**: transition the issue to the project's *"Won't Do"* / *"Stale"*
  status per `<project-config>/issue-tracker-config.md`.
