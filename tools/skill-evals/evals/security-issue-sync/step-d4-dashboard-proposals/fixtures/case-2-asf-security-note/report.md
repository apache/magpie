<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Reconcile output (`magpie-asf-security-dash reconcile --pmc foo`)

```json
{"pmc": "foo", "cases": 2, "issues": 2, "paired": 2, "findings": [
  {"kind": "cve-missing-on-dashboard", "fix": "asf-security", "detail": "the tracker records CVE-2026-31337",
   "case": {"message_id": "c3@example.org", "title": "Deserialization in RPC layer", "state": "untriaged", "cves": [], "thread": ""},
   "issue": {"id": "52", "url": "https://github.com/foo/foo-security/issues/52", "state": "open", "decision": "accepted", "cves": ["CVE-2026-31337"]}},
  {"kind": "closed-in-tracker", "fix": "asf-security", "detail": "the tracker issue is closed but the dashboard still lists the case as open",
   "case": {"message_id": "d4@example.org", "title": "Session fixation in login", "state": "disclosure", "cves": ["CVE-2026-30001"], "thread": ""},
   "issue": {"id": "47", "url": "https://github.com/foo/foo-security/issues/47", "state": "closed", "decision": "accepted", "cves": ["CVE-2026-30001"]}}
]}
```

The user asked: "sync dashboard and fix whatever you can right away".
