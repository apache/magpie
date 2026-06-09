# SPDX-License-Identifier: Apache-2.0

## Context

Parent skill `security-issue-import` is at its Step 7 (apply confirmed
imports) and calls the via-forwarder skill with `mode = import`.

## Mock: Matched adapter

```json
{
  "name": "asf-security",
  "contact_handle": "@asf-security-liaison",
  "via_forwarder_question_mode": true
}
```

## Mock: Routing inputs

- mode: import
- reporter_first_name: "Sam"
- links: [["GHSA", "https://github.com/.../GHSA-0000-0000-0001"], ["CVE record", "https://www.cve.org/CVERecord?id=CVE-2025-0001"]]
- inner_body: "We have imported your report into our tracker and assigned it CVE-2025-0001. We will keep you posted as a fix lands."
