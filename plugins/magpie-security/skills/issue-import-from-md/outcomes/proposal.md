<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-md — the proposal

From Step 4; `security-management issue-import-from-md render-proposal` renders it.

Render a single proposal covering every parsed finding:

```text
<file-basename> — N findings parsed.

| # | Severity | Category                       | Title                                              | Possible duplicate |
|---|----------|--------------------------------|----------------------------------------------------|--------------------|
| 1 | HIGH     | Insecure Deserialization / RCE | Arbitrary callable invocation during serialized…  | <tracker>#NNN      |
| 2 | HIGH     | Insecure Deserialization / RCE | Arbitrary import in custom deadline-reference…    | (none)             |
| 3 | MEDIUM   | Server-Side Request Forgery    | SSRF from API server via worker-supplied hostname | (none)             |
| 4 | MEDIUM   | Broken access control          | Import-error per-DAG authorization check is a no-op | (none)             |
| 5 | LOW      | Open redirect                  | Open-redirect validator accepts backslash-prefix… | (none)             |
| 6 | LOW      | Xss                            | DAG-author-controlled hrefs rendered without…     | (none)             |

Default disposition: import all 6 as `Needs triage`.
Reply with one of:
  - `go` / `proceed` / `yes, all`     — import every finding above.
  - `skip 4`                          — drop finding 4; import the rest.
  - `skip 4,6`                        — drop multiple.
  - `cancel` / `none`                 — bail; no trackers created.
```
