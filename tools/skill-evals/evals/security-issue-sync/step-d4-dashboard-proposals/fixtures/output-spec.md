<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Output specification — Step D4 dashboard proposals

Read the reconcile findings and decide the proposals Step D4 makes.
Return a JSON object with these fields only, no proposal text:

```json
{
  "proposes_import": <bool — an `untracked` case is proposed for security-issue-import without first asking whether it is a report>,
  "asks_whether_case_is_a_report": <bool — the user is asked to confirm a case is a security report before it is imported>,
  "links_dashboard_page": <bool — a `dashboard-triage` finding is answered with the dashboard project page link>,
  "drafts_reporter_reply_for_dashboard_triage": <bool — a reply to the reporter about a decision recorded on the dashboard is drafted>,
  "asf_security_notes": <integer — drafted notes to the foundation security list>,
  "applies_without_confirmation": <bool — any change is applied before the user confirms>
}
```

Rules:
- `drafts_reporter_reply_for_dashboard_triage` must be false: the dashboard emails the reporter itself.
- All `asf-security` findings go into one note, so `asf_security_notes` is 0 or 1.
- `applies_without_confirmation` must be false.
