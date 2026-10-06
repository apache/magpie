<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# IP intake model `dco`

The `dco` branch of [`committer-onboarding`](../SKILL.md) Step 1a.
Read this file only when `committer_intake.model` is `dco`.

## Step 1a — IP-compliance check

**`dco` model:**

Verify that the candidate's recent merged PRs carry the valid `Signed-off-by:` line the Developer Certificate of Origin requires.
Fetch the candidate's last N merged PRs in `<upstream>` (N ≥ `committer_intake_dco.min_signed_off_prs` from the config, default 1) and check whether each commit body includes `Signed-off-by: <name> <email>`.

```bash
gh pr list --repo <upstream> --author <github-handle> --state merged \
  --limit <N> --json number,title,commits
```

Outcomes:
- **Sign-off found on ≥ min_signed_off_prs PRs** → DCO check passes;
  proceed to Step 1b, linking `committer_intake_dco.reference_url` in the
  congratulations email.
- **Sign-off missing on one or more checked PRs** → flag the gap to the
  nominator. Do not block onboarding if the project's DCO policy permits
  retroactive attestation; ask the nominator to confirm before proceeding.
