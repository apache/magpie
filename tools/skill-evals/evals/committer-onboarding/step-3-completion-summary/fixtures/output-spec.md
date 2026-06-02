# Step 3 output spec

The model must produce a completion summary with the following
structure:

- `candidate`: candidate name and Apache ID
- `project`: project name
- `scenario`: one of "new-committer", "committer-to-pmc", "direct-to-pmc"
- `communications_sent`: list of sent communications, each an object
  with `type` and `recipient` keys
- `karma_granted`: list of completed karma items, each an object
  with at least a `target` (e.g. Jira project, Whimsy roster) and a
  short description. Must be `[]` when the candidate's Apache
  account does not yet exist; karma cannot be granted before the
  account is active.
- `pending_items`: list of items still waiting; each item is an
  object with `item` (short identifier, e.g. `"icla_confirmation"`,
  `"account_creation"`, `"karma_grant"`, `"welcome_announcement"`)
  and `action` (one-line description of what the nominator must do
  next). Bare strings are not accepted. Use `[]` when all done.
- `onboarding_complete`: boolean — true only when `pending_items`
  is `[]` and the account is active
