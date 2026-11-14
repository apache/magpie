<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — Step 1h — release-vote threads

Part of Step 1 in [`gather.md`](gather.md), which says when to read this file.

**Opt-in.** This sub-step fires only when the project has enabled release-vote gating in the CVE-JSON generator's config —
`[workflow].release_vote_gating` is `true` in
[`<project-config>/tools/cve-tool-vulnogram/cve-json-config.toml`](../../../../<project-config>/tools/cve-tool-vulnogram/cve-json-config.toml).
Adopters that publish advisories without a separate release-vote step leave the flag off;
the sync skips this sub-step for them and never proposes the `rc voting` label.

**Why this step exists.** With gating on, the generator's `CNA_private.state` goes `DRAFT` → `REVIEW` once an RC for the carrier release is being voted → `PUBLIC` after the advisory ships
(state machine in [`tools/cve-tool-vulnogram/generate-cve-json/SKILL.md`](../../../../tools/cve-tool-vulnogram/generate-cve-json/SKILL.md)).
A tracker label drives it (`[workflow].rc_voting_label`, default `"rc voting"`),
and this sub-step is the **only place** the sync skill proposes adding or removing that label.

**Which trackers this applies to.** Only trackers in the `pr merged` → `fix released` window:

- the tracker carries `pr merged` (fix landed in `<upstream>`);
- it does **not** yet carry `fix released` (the release has not shipped);
- a fix-PR milestone is known and parseable (e.g. `<product> 3.2.3`, `<scope-b> 2026-04-21`);
  without a target release version there is nothing to match against.

Trackers outside this window are skipped:

- `cve allocated` only (no public PR yet) — too early; nothing to vote on.
- `fix released` — too late; the release shipped, and any remaining `rc voting` label is removed
  by the existing `pr merged` → `fix released` transition (see the Step 2b *Labels* bullet).
- `announced` / closed — out of scope entirely.

**Backend selection.** PonyMail is the primary read source here, since `<dev-list>` is public;
fall back to Gmail only when PonyMail MCP is not enabled / not authenticated.
Per-tracker budget: ≤ 1 archive search (adds to the Step 1d combined envelope).

**Resolving the dev-list address.** Default to `dev@<project-domain>` derived from the project's `project_url`;
`[workflow].release_vote_list` in the same TOML config overrides it when the vote runs on another list.

**Query shape (PonyMail).** Search the dev list for `[VOTE]` threads from the **last 21 days**,
long enough to span re-cut RCs, short enough to keep the result set manageable.

```text
mcp__ponymail__search_list(
  list: "dev",
  domain: "<project-domain>",
  query: "[VOTE]",
  timespan: "lte=21d",
  emails_only: true
)
```

**Matching against the tracker's fix milestone.** Write `{gating, labels, fix_milestone, release_product, messages}` — the search results' `subject` and `url`,
the milestone on the fix **PR** (it carries the carrier version, e.g. `<product> 3.2.3`, where the tracker's may be a wave label like `<scope-b> 2026-04-21`) —
and run `<sm> release-vote`. It takes the first version after `Release` in each `[VOTE] Release <Project> <X.Y.Z> from <X.Y.Z>rcN` subject,
treats a `[RESULT][VOTE]` message in the same result set as a closed vote (no label add: the release shipped or the vote failed and a fresh RC follows),
and records `release_vote_in_progress` and `release_vote_thread_url` for a tracker in the `pr merged` window with a matching open vote;
`release_product` keeps a component wave's vote to its own `[VOTE] Release <scope-b> …` thread.

**Hard rule — no auto-apply.** The result feeds Step 2b's proposal and applies only after the user confirms.
Never add `rc voting` silently: the next regen flips `CNA_private.state` to `REVIEW`,
so the human read of *"yes, that vote is for our carrier release"* is the required gate.

---
