<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Governance model `maintainer-roster`

The `maintainer-roster` branches of [`committer-onboarding`](../SKILL.md), in step order.
Read this file only when `committer_governance.model` is `maintainer-roster`.

## Step 0 — vote bar

**For `maintainer-roster` governance model:**
The vote bar is `committer_governance_maintainer_roster.min_approvals`
approvals from existing listed maintainers. Count approvals from the
vote channel declared in `committer_governance_maintainer_roster.vote_channel`.
Report the total approvals received vs. the minimum required.

## Step 1c — account request

**`maintainer-roster` model:**

No external account-creation request is needed. Continue with
Step 2, then Step 3 (roster file update and notification
announcement).

## Step 3 — access checklist

### `maintainer-roster` model

Use the values from `committer_governance_maintainer_roster` in the
config for the roster file path and minimum approvals.

#### Checklist — maintainer-roster

- [ ] **Roster file update** — add the candidate's name and GitHub handle
  to `committer_governance_maintainer_roster.roster_file` in
  `<project-config>/`. Show the diff to the nominator and apply only
  after confirmation.

  ```bash
  # Example roster append (substitute actual roster format):
  echo "- @<github-handle> (<candidate name>)" >> <roster-file>
  ```

- [ ] **Commit and PR** — open a PR in the project's configuration
  repository updating the roster file. Show the PR body to the nominator
  and open it only after confirmation.

- [ ] **Welcome announcement** — post to the project's community channel
  per project conventions. Draft in Step 3a below.

## Step 4 — completion summary example

**`maintainer-roster` example:**

```text
Onboarding complete for <candidate> (@<github-handle>)
Project: <project>   Scenario: <scenario>   Governance: maintainer-roster   Intake: <model>

Roster updated:
  ✓ <roster-file> PR opened (awaiting merge)

Communications sent:
  ✓ Congratulations message → <candidate email or GitHub handle>
  ✓ Welcome announcement → <channel>

Pending (if any):
  ⏳ Roster PR merge
```
