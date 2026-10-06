<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# IP intake model `icla`

The `icla` branch of [`committer-onboarding`](../SKILL.md) Step 1a.
Read this file only when `committer_intake.model` is `icla` (the default).

## Step 1a — IP-compliance check

**`icla` model (default):**

Open https://whimsy.apache.org/roster/committer/<apache-id> if
the candidate already has an Apache ID. An existing Apache
account implies an ICLA on file; skip to Step 1b.

If `<apache-id>` is "none", check whether the candidate's legal
name appears on the signed ICLA list:
https://people.apache.org/committer-index.html (search by name).

The public index is updated by the secretary after processing —
there is typically a lag of several days between the candidate
emailing the ICLA and it appearing on the list. Ask the
nominator whether the candidate has already said they filed it.

Three outcomes:

- **ICLA on file** (appears on the index) → proceed to Step 1b.
- **ICLA submitted but not yet processed** (candidate confirms
  they emailed secretary but it is not showing yet) → proceed to
  Step 1b using the "submitted, awaiting processing" congratulations
  variant (no ICLA instructions — they have already filed). Hold
  the secretary account-creation request until the nominator
  confirms the secretary has processed it (i.e. it appears on the
  index or the secretary replies). Note the hold clearly so the
  nominator knows to follow up.
- **No ICLA filed** (not on index and candidate has not said they
  filed it) → include the ICLA instruction block in the
  congratulations email (see
  [`detail/email-templates.md`](email-templates.md) §
  ICLA instructions). Onboarding cannot proceed to account
  creation until the ICLA is processed; flag the waiting step
  clearly.
