<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# IP intake model `icla`

The `icla` branch of [`committer-onboarding`](../SKILL.md) Step 1a.
Read this file only when `committer_intake.model` is `icla` (the default).

## Step 1a — IP-compliance check

**`icla` model (default):**

If the candidate already has an Apache ID, open https://whimsy.apache.org/roster/committer/<apache-id>.
An existing Apache account implies an ICLA on file; skip to Step 1b.

If `<apache-id>` is "none", search the signed ICLA list for the candidate's legal name: https://people.apache.org/committer-index.html.

The secretary updates the public index only after processing, typically several days after the candidate emails the ICLA, so ask the nominator whether the candidate has already said they filed it.

Three outcomes:

- **ICLA on file** (appears on the index) → proceed to Step 1b.
- **ICLA submitted but not yet processed** (candidate confirms
  they emailed secretary but it is not showing yet) → proceed to
  Step 1b using the "submitted, awaiting processing" congratulations
  variant (no ICLA instructions — they have already filed). Hold
  the secretary account-creation request until the nominator
  confirms the secretary has processed it (it appears on the
  index or the secretary replies), and note the hold clearly so the
  nominator knows to follow up.
- **No ICLA filed** (not on index and candidate has not said they
  filed it) → include the ICLA instruction block in the
  congratulations email
  ([`detail/email-templates.md`](email-templates.md) §
  ICLA instructions). Flag clearly that account creation waits
  until the ICLA is processed.
