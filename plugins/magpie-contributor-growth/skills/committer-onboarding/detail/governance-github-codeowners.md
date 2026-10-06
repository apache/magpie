<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Governance model `github-codeowners`

The `github-codeowners` branches of [`committer-onboarding`](../SKILL.md), in step order.
Read this file only when `committer_governance.model` is `github-codeowners`.

## Step 0 — vote bar

**For `github-codeowners` governance model:**
The vote bar comes from `committer_governance_github_codeowners.vote_channel` in the config.
There is no "binding" vs "non-binding" distinction: count approvals from reviewers listed in CODEOWNERS or the maintainer team.
The minimum is project-defined: consult the project's `CONTRIBUTING.md`, or the value in the config file if specified.

## Step 1c — account request

**`github-codeowners` model:**

No external account-creation request is needed: the candidate already has the GitHub account they contributed with.
Continue with Step 2, then Step 3 (GitHub maintainer-team invite and optional CODEOWNERS update).

## Step 3 — access checklist

### `github-codeowners` model

Take the team slug, CODEOWNERS path, and vote channel from `committer_governance_github_codeowners` in the config.

#### Checklist — github-codeowners

- [ ] **GitHub team invite** — add the candidate's GitHub handle to
  `committer_governance_github_codeowners.maintainers_team`
  (`contract:people` → `add_team_member(<org>/<team-slug>, <github-handle>)`,
  a write the nominator confirms before it runs). The GitHub adapter's
  command ([`operations.md` § People](../../../../../tools/github/operations.md#people)):

  ```bash
  gh api --method PUT \
    /orgs/<org>/teams/<team-slug>/memberships/<github-handle> \
    -f role=member
  ```

  Ask the nominator to confirm the invite was accepted before proceeding.

- [ ] **CODEOWNERS update** (if `codeowners_file` is not `null`) — open
  a PR adding the candidate's GitHub handle to the CODEOWNERS file at the
  path declared in `committer_governance_github_codeowners.codeowners_file`.
  Show the diff to the nominator and open the PR only after confirmation.

- [ ] **Welcome announcement** — post to the project's community channel
  (GitHub Discussion, mailing list, or Slack, per project conventions),
  drafted in Step 3a.

## Step 4 — completion summary example

**`github-codeowners` example:**

```text
Onboarding complete for <candidate> (@<github-handle>)
Project: <project>   Scenario: <scenario>   Governance: github-codeowners   Intake: <model>

Access granted:
  ✓ GitHub team invite → <org>/<team-slug>
  ✓ CODEOWNERS PR opened (awaiting merge)   [if codeowners_file set]

Communications sent:
  ✓ Congratulations message → <candidate email or GitHub handle>
  ✓ Welcome announcement → <channel>

Pending (if any):
  ⏳ CODEOWNERS PR merge
  ⏳ Team invite accepted by candidate
```
