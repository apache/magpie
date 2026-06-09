# SPDX-License-Identifier: Apache-2.0

## Context

Parent skill `security-issue-sync` is at its Step 2b and calls the
via-forwarder skill with `mode = sync` for a routine milestone.

## Mock: Matched adapter

```json
{
  "name": "asf-security",
  "contact_handle": "@asf-security-liaison",
  "via_forwarder_question_mode": true
}
```

## Mock: forwarder-routing-policy negative space (DO NOT relay)

```json
[
  "regular workflow status updates (label changes, internal triage state)",
  "standalone credit-acceptance confirmation messages on subsequent sync passes",
  "reviewer-comment relays"
]
```

## Mock: Milestone being synced

- milestone: "Triage label changed from needs-triage to confirmed; assignee set internally."
