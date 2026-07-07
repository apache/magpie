<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 3 output spec

The model must produce a completion summary with the following
structure:

- `candidate`: candidate name and Apache ID
- `project`: project name
- `scenario`: one of "new-committer", "committer-to-pmc", "direct-to-pmc"
- `communications_sent`: list of sent communications, each an object
  with `type` and `recipient` keys. `type` is one of exactly:
  `"congratulations_email"`, `"secretary_request"` (the account-creation
  request to root@apache.org; do not rename it to
  `secretary_account_request` or similar), `"welcome_announcement"`.
- `karma_granted`: list of completed karma items, each a bare-string
  target identifier (e.g. `"whimsy_roster"`, `"jira"`, `"github_org"`).
  Must be `[]` when the candidate's Apache account does not yet exist;
  karma cannot be granted before the account is active.
- `pending_items`: list of items still waiting; each item is an
  object with `item` (short identifier) and `action` (one-line
  description of what the nominator must do next). Bare strings are
  not accepted. Use `[]` when all done. Karma granularity: while the
  account is not yet active, emit a single coarse `"karma_grant"`
  item covering all outstanding karma (do not split per target),
  since none of it can be granted until the account exists. Allowed
  `item` identifiers: `"icla_confirmation"`, `"account_creation"`,
  `"karma_grant"`, `"welcome_announcement"`.
- `onboarding_complete`: boolean — true only when `pending_items`
  is `[]` and the account is active
