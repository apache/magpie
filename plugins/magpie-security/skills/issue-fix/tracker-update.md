<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# issue-fix — tracker update (Step 10)

## Step 10 — Update the <tracker> tracking issue

Now that a public PR exists, update the private tracking issue:

1. **Append a `Fix PR` entry to the tracker's status-rollup comment** — not a new top-level comment.
   The rollup recipe (detection, append, zero-whitespace rules) lives in [`tools/github/status-rollup.md`](../../../../tools/github/status-rollup.md).
   Write the entry body to `<scratch>/rollup-entry-<N>.md` with the Write tool and append it:

   ```bash
   uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-fix rollup-append <N> "Fix PR (<upstream>#<PR>)" <scratch>/rollup-entry-<N>.md
   ```

   The tool adds the `<YYYY-MM-DD> · @<author-handle> · Fix PR (<upstream>#<PR>)` `<details>` envelope, so the file holds the body only.
   The entry body announces the new PR, the branch name, and the intended backport (if any), with the issue, PR and CVE references as clickable links per [`AGENTS.md` § *Linking CVEs*](../../../../AGENTS.md#linking-cves) and [§ *Linking tracker issues and PRs*](../../../../AGENTS.md#linking-tracker-issues-and-prs).
   The rollup is private, so it may contain the `<upstream>` PR URL, the branch name, and the CVE reference.

   If the tracker has no rollup yet (a legacy tracker), `rollup-append` creates it; first propose folding any pre-existing bot comments into it (the fold-legacy sub-step in [`security-issue-sync`](../issue-sync/SKILL.md)), one call per accepted comment, oldest first:
   `uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-fix rollup-fold <N> <comment-id> "<Action>"`.

   Before writing the entry, **replace bare-name mentions** of maintainers, release managers, and security-team members with their `@`-handle, per [`AGENTS.md` — *Mentioning project maintainers and security-team members*](../../../../AGENTS.md#mentioning-project-maintainers-and-security-team-members); the handles are in [`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md).
   The public `<upstream>` PR description and follow-up public comments obey the same rule, with none of the [5c forbidden terms](implementation-plan.md#5c-commit-message-and-pr-title) alongside the mention.

2. **Update the issue body "PR with the fix" field** if it is empty or points to a stale PR (the Step 2a value tells you which).
   Write the PR URL to `<scratch>/pr-with-fix-<N>.md` with the Write tool, then patch only that field:

   ```bash
   uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-fix body-field-set <N> "PR with the fix" <scratch>/pr-with-fix-<N>.md
   ```

   Exit `3` means the heading is absent or duplicated — surface it and fall back to a manual edit.

3. **Assign the tracker to the fix owner.** Propose setting the assignee so the board reflects who is on it, applying the **same rule** as `security-issue-sync` — the *Assignees* rule's PR-author and sign-up branches in [`security-issue-sync/signals-to-actions.md`](../issue-sync/signals-to-actions.md):
   - The natural owner is the **remediation developer** — the `<upstream>` PR author driving this fix.
   - If a security-team member **signed up** to own the issue in the thread, that volunteer is the owner instead (sign-up branch).
   - **Project-member gate** (mandatory): assign only when the person is on the security-team roster in [`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md) or a `<tracker>` collaborator.
     A non-member is recorded and surfaced but **not** assigned — GitHub silently drops the write.
   - **Never override** an existing conflicting assignee here; the hand-off to the release manager stays at the `fix released` transition (sync owns it).

   Propose; apply on confirmation.

4. **Maintain milestones and labels** — see the next section.

5. **Status update to the reporter** — if the `<tracker>` issue has an identified external reporter who has not yet been told about the fix PR, re-run `security-issue-sync` with a pointer to the new PR (its "Status update to the reporter" category).
   Do **not** draft the reporter email in this skill.

### Maintaining milestones and labels on `<tracker>`

The skill leaves the private issue in a consistent "fix-proposed, awaiting review" state: milestone and label set match the current release plan (the default release target is in "Release branches currently in flight" and "What this means for sync and fix skills" in [`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md#release-branches-currently-in-flight)).
**Every action in this section is a proposal that requires explicit user confirmation before it is applied.**

#### 10a. Ensure the target milestone exists

The default milestone for a patch-release fix is the next patch release `<project-config>/release-trains.md` names (`<target>` below).
Before assigning, check that the milestone exists:

```bash
gh api 'repos/<tracker>/milestones?state=all&per_page=100' \
  --jq '.[] | select(.title == "<target>") | {number, state}'
```

If the query returns nothing, **propose creating the milestone**.
`<scratch>` is the session scratch directory as an absolute path (fall back to `$TMPDIR`); `gh` may run outside the sandbox, where `$TMPDIR` differs, so pass it absolute paths.

```bash
# Write tool: file_path: <scratch>/ms-title.txt, content: <target>
# Write tool: file_path: <scratch>/ms-desc.txt, content: <product> <target> release tracking.
gh api repos/<tracker>/milestones \
  -F title=@<scratch>/ms-title.txt \
  -f state=open \
  -F description=@<scratch>/ms-desc.txt
```

Present the `title`, `state` and `description` and wait for a `yes` before running the create call.
Capture the returned milestone `number` for the closed-milestone fallback.

If the milestone exists but is **closed**, `gh issue edit --milestone "<title>"` fails with `'<title>' not found`.
Fall back to the REST API and reference it by number:

```bash
gh api repos/<tracker>/issues/<N> -X PATCH -F milestone=<milestone-number>
```

#### 10b. Assign the issue to the target milestone

If the issue sits on a stale milestone (a patch release already cut, a retired release line listed as legacy in `<project-config>/release-trains.md`, or a legacy catch-all placeholder), propose moving it to the current default and apply on confirmation:

```bash
gh issue edit <N> --repo <tracker> --milestone '<target>'
# or, for closed milestones, via REST:
gh api repos/<tracker>/issues/<N> -X PATCH -F milestone=<number>
```

Do **not** silently move an issue intentionally parked on an older milestone (e.g. an already-released patch that still needs an advisory sent).
When in doubt, ask the user instead of moving it.

#### 10c. Ensure the required labels exist

The current label set on `<tracker>` can be listed with:

```bash
gh label list --repo <tracker> --limit 100 \
  --json name,description,color --jq '.[].name'
```

For a post-triage, pre-merge fix, the target label set is:

- **one** scope label: `<scope-a>` | `<scope-b>` | `<scope-c>`;
- `cve allocated` if a CVE has been allocated;
- `needs triage` **removed** (if still present after triage);
- `pr created` once the public PR is open;
- **not** `pr merged` or `fix released` (post-merge / post-release states, applied by `security-issue-sync` on later runs);
- **not** `announced - emails sent` or `announced` (post-advisory states, also applied by sync).

If a label the skill wants to apply does **not** exist on the repository (e.g. a stale doc name — the README once said `vendor-advisory` where the actual label is `announced - emails sent`), stop and report the mismatch.
Do **not** create labels without asking — label names are the security team's shared vocabulary.

If the user confirms creating a label, do it explicitly:

```bash
gh label create '<name>' --repo <tracker> \
  --description '<short description>' \
  --color '<hex>'
```

#### 10d. Apply the label changes

Once the target label set is agreed, apply all adds and removes in a single `gh issue edit` call, so the change lands as one audit-trail entry:

```bash
gh issue edit <N> --repo <tracker> \
  --add-label '<scope-a>,cve allocated' \
  --remove-label 'needs triage'
```

#### 10e. Consistency checks before moving on

Before leaving the tracking issue, verify:

- exactly one scope label is set (`<scope-a>` **xor** `<scope-b>` **xor** `<scope-c>`);
- the milestone matches the current default from `<project-config>/release-trains.md`, or the user has explicitly confirmed a different one;
- the issue body "PR with the fix" field points at the newly-opened public PR;
- the `cve allocated` label is present if the issue body contains a CVE tool link, and absent if it does not (read both fields with `body-field-get`, never the whole body);
- `needs triage` is gone.

Surface any remaining inconsistency in the Step 11 recap.
