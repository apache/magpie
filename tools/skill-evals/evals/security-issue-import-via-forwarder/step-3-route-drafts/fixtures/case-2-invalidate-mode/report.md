# SPDX-License-Identifier: Apache-2.0

## Context

Parent skill `security-issue-invalidate` is at its Step 5d (ASF-relay
branch) and calls the via-forwarder skill with `mode = invalidate`.
This adapter folds the credit-preference question into a separate
back-channel draft (question mode off).

## Mock: Matched adapter

```json
{
  "name": "asf-security",
  "contact_handle": "@asf-security-liaison",
  "via_forwarder_question_mode": false
}
```

## Mock: Routing inputs

- mode: invalidate
- reporter_first_name: "Sam"
- links: [["Advisory", "https://github.com/.../GHSA-0000-0000-0002"]]
- inner_body: "After investigation we determined this report does not reproduce on supported versions and have closed it as not-a-vulnerability. Thank you for the report."
