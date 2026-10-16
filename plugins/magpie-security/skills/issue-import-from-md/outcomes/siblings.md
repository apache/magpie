<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-md — beside the other import skills

It is the third on-ramp alongside the two other import skills:

| | `security-issue-import` | `security-issue-import-from-pr` | `security-issue-import-from-md` |
|---|---|---|---|
| Source | `<security-list>` Gmail / PonyMail thread | `<upstream>` PR URL or number | Markdown file with one or more findings |
| Reporter | External researcher | None (PR author = remediation developer) | None (the file is the report; usually AI- or scanner-generated) |
| Receipt-of-confirmation reply | Drafted on the inbound thread | Skipped — no reporter to reply to | Skipped — no reporter to reply to |
| Validity assessment | Hosted on the tracker after import | Already done informally before invocation | Hosted on the tracker after import |
| Initial board column | `Needs triage` | `Assessed` | `Needs triage` |
| Cardinality | One thread → one tracker | One PR → one tracker | One file → N trackers |
