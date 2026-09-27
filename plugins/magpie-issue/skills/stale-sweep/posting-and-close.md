<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Posting and close calls

Companion to [`SKILL.md`](SKILL.md). How to post confirmed proposal
comments (Step 6) and execute the two-step close.

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
