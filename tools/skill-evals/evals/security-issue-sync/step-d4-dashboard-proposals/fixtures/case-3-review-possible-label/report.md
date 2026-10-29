<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Reconcile output (`magpie-asf-security-dash reconcile --pmc foo`)

```json
{"pmc": "foo", "cases": 1, "issues": 0, "paired": 0, "labels_skipped": 0, "findings": [
  {"kind": "untracked", "fix": "review",
   "detail": "the tracker has no issue for this case; the dashboard does not say whether it is a report or one of the security team's standing labels (aaa-…, zzz-…), so check the thread before importing",
   "case": {"message_id": "e5@example.org", "title": "Question about dependency versions", "state": "untriaged", "cves": [], "thread": "https://lists.apache.org/thread/e5%40example.org?<security.apache.org>"}}
]}
```
