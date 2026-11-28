<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 4 — Advisory close-out apply items

Part of the Step 4 apply loop in [`apply-and-push.md`](apply-and-push.md), which says when to read this file.

- **Wrap-up comment (post-close, informational only):** load
  [`tools/<cve-tool>/release-manager-wrap-up-comment.md`](../../../../tools/cve-tool-vulnogram/release-manager-wrap-up-comment.md)
  and post it as the **last** action of the *Advisory archived on `<users-list>`* combined apply,
  right after sync has (a) archived the tracker from the project board via `archiveProjectV2Item` and (b) closed the milestone if the just-closed tracker was the last open sibling.
  **The comment is purely informational** — a timeline marker confirming what sync did, **not** a ping for residual manual actions:
  the RM has none left after sending the advisory email.

  Placeholders: `CVE_ID`, `RM_HANDLE` (from the release-manager identity resolved in Step 1f / `release-trains.md`),
  `PUBLISH_TIMESTAMP` (from the just-completed `cve-tool publish` call),
  `ADVISORY_URL` (the archive URL captured in the same apply), and the conditional `MILESTONE_BULLET`.

  **`MILESTONE_BULLET` is the only conditional in the template.**
  When sync's milestone-close action fired in the same apply (the just-closed tracker was the last open sibling on its milestone),
  substitute a one-line *informational* note — not an ask:

  ```text
  Milestone [`<ms-title>`](https://github.com/<tracker>/milestone/<ms-number>) closed automatically (every tracker on it is now done).
  ```

  This needs no extra call:
  the apply already knows whether the milestone-close PATCH ran (it fired only after its open-sibling count came back `0`),
  and `<ms-number>` / `<ms-title>` are the tracker's milestone from the [Step 1a](gather.md#1a-read-the-github-issue) fetch.
  When the close did not fire, or the tracker has no milestone, substitute an empty string.

  Write the substituted template to a temp file and POST a fresh comment;
  there is no PATCH recovery for this template (the tracker is already closed).
  Idempotency keys on the marker `<!-- apache-magpie: release-manager-wrap-up v1 -->`:
  if it is already on the tracker, skip the post entirely.
  Apply the same bare-name → `@handle` scrub before posting.
- **Advisory-records update:** run the confirmed commands from the 2b item one at a time, in order, each as a plain command,
  and stop at the first that fails —
  the clean check exits `1` when the working copy has unrelated changes, and a branch other than the configured one is a stop too.
  The `--apply` re-run recomputes the change on the updated working copy; if its file list differs from the confirmed one, stop and show the new diff.
  After the `commit` (and on Git the `push`) succeeds, post a status comment from a temp file:
  line 1 is the marker `<!-- apache-magpie: advisory-records v1 -->`, then one sentence naming the file(s) and the commit,
  then the ticked item `- [x] <!-- apache-magpie: security-pages-checklist v1 --> Project security pages updated with CVE_ID`,
  which records the security-pages step as done.
  In pull-request mode, after the `commit` and before the `push`, run the adversarial review in [`pre-pr-adversarial-review.md`](pre-pr-adversarial-review.md)
  over the site working copy (`--repo-dir`), against the base branch, with the pull request's title and the body file the `--apply` run wrote;
  a finding the user wants acted on stops the run before anything is pushed.
  The comment follows a successful `gh pr create` (or records the pull request Step 1g found, for `record_pr`):
  line 1 is the same marker, then one sentence naming the file(s) and the pull request's full URL, which later syncs read back,
  and no checklist item — the record is live only once the pull request merges, which the `advisory-records-merged v1` comment records.
  A failed command posts nothing; report it in the recap with the command's output.
  If the push succeeded but `gh pr create` failed, say so and offer only that command again, on the user's confirmation:
  the branch is already on the fork, so re-running the earlier commands would stop at `new-branch`.
  Through `vetted-op-git` the same order holds: run each call as printed, with the literal `~`, put the commit `git-fetch` printed in place of `<start-sha>`,
  stop when `vetted-op-checks` reports a failure, and give the adversarial review the worktree as `--repo-dir`;
  the status comment names the URL `git-pr-create` printed, and a failed `git-pr-create` after a successful push is offered again on its own.
  In the *Advisory archived on `<users-list>`* combined apply, this item runs after the CVE JSON has been regenerated and pushed:
  regenerate `<scratch>/<CVE-ID>.json` from the updated tracker first, so the `--apply` run writes the record the CVE tool now holds.
  A refresh posts the `advisory-records-refresh v1` comment instead, naming its pull request (or commit).
- **CVE record state transition (`review-ready → public`):** run the CVE-tool interface's `publish` operation
  ([`tools/cve-tool/README.md`](../../../../tools/cve-tool/README.md); for Vulnogram it flips the record's `CNA_private.state` from `REVIEW` to `PUBLIC` over the OAuth API).
  It refuses the transition unless the current state is `review-ready` and the record already lists the archived advisory URL as a `vendor-advisory` reference (re-push the CVE JSON after capturing the URL, before this step);
  `--allow-state review-ready --allow-state publish-ready` also accepts a record moved to `publish-ready` manually, and no earlier state can be published:

  ```bash
  uvx --from ~/.claude/magpie/security-tools/cve-tool cve-tool publish --cve-id <CVE-YYYY-NNNNN> --pmc <pmc>
  ```

  Every `cve-tool` record command in this file takes `--pmc <pmc>`, with `<pmc>` the project's `cna_private_owner` from `<project-config>/project.md`,
  so a user holding tokens for several PMCs always uses this project's.

  Use it only as part of the *Advisory archived on `<users-list>`* combined apply in [Step 2b](SKILL.md#step-2--build-a-proposal-do-not-apply-anything-yet):
  the trigger is *"the advisory has provably shipped on `<users-list>`"*, the signal a human would use before clicking the Vulnogram `REVIEW → PUBLIC` button.
  Outside that trigger, the state transition stays manual.

  Idempotent: re-running on a record already `public` exits 0 with an informational message.
  Exit codes match `record-update` (2 = token expired, 3 = unexpected state, 5 = save failed, 6 = other API error, 7 = unexpected envelope), plus 4 = no `vendor-advisory` reference.
  On a non-zero exit, the combined apply stops and the failure surfaces in the recap;
  the partial state (URL captured, labels flipped, JSON re-pushed, tracker NOT yet closed) is the recovery starting point for the next sync.
- **Advisory short-summary extraction:** when the *Advisory archived on `<users-list>`* combined apply fires (Step 2b row),
  fetch the archived advisory email body from the `<mail-archive-url>` archive
  and extract the public-facing short summary into the *Short public summary for publish* body field **before** the Step 5 JSON regen,
  so the published text lands verbatim in the re-pushed JSON.

  Heuristic — from the archive entry's JSON, take the prose block between the CVE header line (matching `^CVE-\d{4}-\d+:`)
  and the first *Affected version range:* / *Affected versions:* block,
  trim leading/trailing blank lines, and collapse internal blank runs to a single blank line.
  Surface the extracted summary in the Step 2 proposal so the user can spot over- or under-extraction before the body-field update applies;
  accept a free-form override at re-confirmation if the heuristic misfires.
