<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Reconcile output (`magpie-asf-security-dash reconcile --pmc foo`)

```json
{"pmc": "foo", "cases": 2, "issues": 1, "paired": 1, "findings": [
  {"kind": "triage-on-dashboard", "fix": "dashboard-triage",
   "detail": "the tracker has rejected the report; record it at https://dash.security.apache.org/project/foo — the dashboard then emails the reporter itself, so send no separate reply",
   "case": {"message_id": "a1@example.org", "title": "Path traversal in upload handler", "state": "untriaged", "cves": [], "thread": "https://lists.apache.org/thread/a1%40example.org?<security.foo.apache.org>"},
   "issue": {"id": "41", "url": "https://github.com/foo/foo-security/issues/41", "state": "open", "decision": "rejected", "cves": []}},
  {"kind": "untracked", "fix": "import", "detail": "the dashboard tracks this report but the tracker has no issue for it",
   "case": {"message_id": "b2@example.org", "title": "XSS in admin console", "state": "untriaged", "cves": [], "thread": "https://lists.apache.org/thread/b2%40example.org?<security.foo.apache.org>"}}
]}
```

The tracker issue was closed as `invalid` by the team yesterday; the reporter has not been told yet.
