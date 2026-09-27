<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# issue-fix — tracker update (Step 10)

## Step 10 — Update the <tracker> tracking issue

Now that a public PR exists, update the private tracking issue:

1. **Append a `Fix PR` entry to the tracker's status-rollup
   comment** — not a new top-level comment. The rollup-upsert
   recipe (detection, append, zero-whitespace rules) lives in
   [`tools/github/status-rollup.md`](../../../../tools/github/status-rollup.md).
   Emit a single `<details>` block with summary
   `<YYYY-MM-DD> · @<author-handle> · Fix PR (<upstream>#<PR>)`;
   the entry body announces the new PR, the branch name, and the
   intended backport (if any). Render the issue reference, the PR
   reference, and any CVE as clickable markdown links per the
   "Linking CVEs" and "Linking `<tracker>` issues and PRs" rules in
   [`AGENTS.md`](../../../../AGENTS.md). The rollup lives inside the
   private repo so it may freely contain the `<upstream>` PR URL,
   the branch name, and the CVE reference.

   If the tracker has no rollup yet (legacy tracker pre-dating the
   convention), run the upsert recipe's Step 2b to create it and
   fold any pre-existing bot comments into the new rollup first —
   see the fold-legacy sub-step in
   [`security-issue-sync`](../issue-sync/SKILL.md).

   Before writing the entry, **scrub the body for bare-name
   mentions** of project maintainers, release managers, and
   security-team members, and replace them with the corresponding
   `@`-handle so GitHub actually notifies the person. The rule
   itself lives in
   [`AGENTS.md` — *Mentioning project maintainers and security-team members*](../../../../AGENTS.md#mentioning-project-maintainers-and-security-team-members);
   the authoritative list of handles for the adopting project is in
   [`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md).
   The public `<upstream>` PR description and any follow-up public
   comments must also obey the rule, but under the usual
   public-surface confidentiality constraints (no `CVE-`,
   `<tracker>`, *"security fix"*, etc. alongside the mention).

2. **Update the issue body "PR with the fix" field** if it is empty
   or points to a stale PR. Use `gh issue view --json body`, patch
   only that field, and apply via `gh issue edit --body-file`, as
   in the [`security-issue-sync`](../issue-sync/SKILL.md)
   skill.

3. **Assign the tracker to the fix owner.** Now that a PR exists,
   propose setting the tracking issue's assignee so the board
   reflects who is on it. This applies the **same rule** as
   `security-issue-sync` — the *Assignees* rule's PR-author and
   sign-up branches in
   [`security-issue-sync/signals-to-actions.md`](../issue-sync/signals-to-actions.md):
   - The natural owner is the **remediation developer** — the
     `<upstream>` PR author driving this fix.
   - If a security-team member **signed up** to own the issue in the
     thread, that volunteer is the owner instead (sign-up branch).
   - **Project-member gate** (mandatory): assign only when the
     person is on the security-team roster in
     [`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md)
     or a `<tracker>` collaborator. A non-member is recorded and
     surfaced but **not** assigned — they cannot see the private
     tracker and GitHub silently drops the write.
   - **Never override** an existing conflicting assignee here; the
     hand-off to the release manager stays at the `fix released`
     transition (sync owns it).

   Propose; apply on confirmation. (The `security-issue-sync` run
   this skill invokes also reconciles the assignee, so when sync
   runs in the same pass this step and sync agree — they read the
   one rule.)

4. **Maintain milestones and labels** — see the next section.

5. **Status update to the reporter** — if the <tracker> issue has an
   identified external reporter and the reporter has not yet been
   told about the fix PR, delegate to the `security-issue-sync`
   skill's "Status update to the reporter" category by re-running
   that skill with a pointer to the new PR. Do **not** draft the
   reporter email directly in this skill — it is the sync skill's
   responsibility.

### Maintaining milestones and labels on `<tracker>`

The fix skill is responsible for leaving the private issue in a
consistent "fix-proposed, awaiting review" state by the time it
returns. That means both the milestone and the label set must match
the current release plan (see "Release branches currently in flight"
in [`AGENTS.md`](../../../../AGENTS.md) for the authoritative default
release target). **Every action in this section is a proposal that
requires explicit user confirmation before it is applied.**

#### 10a. Ensure the target milestone exists

The default milestone for a patch-release fix is whatever
`AGENTS.md` names as the next patch release (currently **`3.2.2`**).
Before assigning, check that the milestone exists:

```bash
gh api 'repos/<tracker>/milestones?state=all&per_page=100' \
  --jq '.[] | select(.title == "<target>") | {number, state}'
```

If the query returns nothing, **propose creating the milestone**:

```bash
# Write tool: file_path: /tmp/ms-title.txt, content: <target>
# Write tool: file_path: /tmp/ms-desc.txt, content: <product> <target> release tracking.
gh api repos/<tracker>/milestones \
  -F title=@/tmp/ms-title.txt \
  -f state=open \
  -F description=@/tmp/ms-desc.txt
```

The skill must present the `title`, `state` and `description` it
will use and wait for a `yes` before running the create call. Once
created, capture the returned milestone `number` — you will need it
for a closed-milestone fallback later.

If the milestone exists but is **closed** (for example because it
was reopened from history), `gh issue edit --milestone "<title>"`
will fail with `'<title>' not found`. Fall back to the REST API and
reference it by number:

```bash
gh api repos/<tracker>/issues/<N> -X PATCH -F milestone=<milestone-number>
```

#### 10b. Assign the issue to the target milestone

If the issue currently sits on a stale milestone (for example
`3.1.9`, `3.2.1` now that it has been cut, or a legacy catch-all
milestone placeholder), propose moving it to the current default and apply
with user confirmation:

```bash
gh issue edit <N> --repo <tracker> --milestone '<target>'
# or, for closed milestones, via REST:
gh api repos/<tracker>/issues/<N> -X PATCH -F milestone=<number>
```

Do **not** silently move an issue that is intentionally parked on
an older milestone (e.g. an already-released patch that still needs
an advisory sent). When in doubt, surface the question to the user
instead of moving it.

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
- **not** `pr merged` or `fix released` (those belong to post-merge
  / post-release states, applied by the `security-issue-sync` skill
  on later runs);
- **not** `announced - emails sent` or `announced` (those
  belong to post-advisory states, also applied by the sync skill).

If a label the skill wants to apply does **not** exist on the
repository (for example a typo in a past doc version — the canonical
example is the README historically saying `vendor-advisory` when the
actual label is `announced - emails sent`), stop and report the
mismatch. Do **not** silently create labels without asking — label
names are the shared vocabulary of the security team, and new labels
should be discussed.

If the user confirms creating a label, do it explicitly:

```bash
gh label create '<name>' --repo <tracker> \
  --description '<short description>' \
  --color '<hex>'
```

#### 10d. Apply the label changes

Once the target label set is agreed, apply all add / remove
operations in a single `gh issue edit` call so the change lands as
one audit trail entry:

```bash
gh issue edit <N> --repo <tracker> \
  --add-label '<scope-a>,cve allocated' \
  --remove-label 'needs triage'
```

#### 10e. Consistency checks before moving on

Before leaving the tracking issue, verify:

- exactly one scope label is set (`<scope-a>` **xor** `<scope-b>`
  **xor** `<scope-c>`);
- the milestone matches the current default from `AGENTS.md`, or
  the user has explicitly confirmed a different one;
- the issue body "PR with the fix" field points at the newly-opened
  public PR;
- the `cve allocated` label is present if the issue body contains a
  CVE tool link, and absent if it does not;
- `needs triage` is gone.

Surface any remaining inconsistency in the Step 11 recap.
