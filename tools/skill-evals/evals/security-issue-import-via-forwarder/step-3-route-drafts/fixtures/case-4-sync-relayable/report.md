# SPDX-License-Identifier: Apache-2.0

## Context

Parent skill `security-issue-sync` is at its Step 2b and calls the
via-forwarder skill with `mode = sync` for a reporter-facing milestone.

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

- milestone: "Advisory GHSA-0000-0000-0003 published and CVE-2025-0003 assigned; fix released in 2.10.2."
