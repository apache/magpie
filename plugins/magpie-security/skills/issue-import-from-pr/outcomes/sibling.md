<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-pr — beside `security-issue-import`

It is the smaller sibling of [`security-issue-import`](../../issue-import/SKILL.md):

| | `security-issue-import` | `security-issue-import-from-pr` |
|---|---|---|
| Source | `<security-list>` Gmail / PonyMail thread | `<upstream>` PR URL or number |
| Reporter | External researcher | None; the PR author is the remediation developer and de-facto finder |
| Receipt reply | Drafted on the inbound thread | Skipped: no reporter |
| Inbound confidentiality | Report is private | PR is already public |
| Validity discussion | On the tracker, after import | Already agreed informally; tracker lands `Assessed` |
| Initial board column | `Needs triage` | `Assessed` |
