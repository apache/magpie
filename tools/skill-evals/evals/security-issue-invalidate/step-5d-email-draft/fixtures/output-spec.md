<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Output specification — Step 5d email draft

Return a JSON object with these boolean fields.

```json
{
  "skipped": <bool — true when import path is PR-imported and the step is skipped entirely>,
  "draft_created": <bool — a new Gmail draft was created in this step>,
  "existing_draft_surfaced": <bool — an existing pending draft was found and surfaced instead of creating a new one>,
  "has_tracker_reference": <bool — the draft body references the tracker repo or issue — should be false (tracker is private)>,
  "has_security_list_cc": <bool — the draft CCs the project security mailing list>,
  "uses_inbound_thread": <bool — the draft is a reply on the inbound Gmail thread (replyToMessageId set)>
}
```

Rules:
- `skipped` is true only for PR-imported trackers; all other fields are irrelevant and may be false.
- `draft_created` and `existing_draft_surfaced` are mutually exclusive.
- `has_tracker_reference` must be false — the tracker repo is private; mentioning it in the email leaks internal information.
- When a new draft is created, `has_security_list_cc` must be true (security@ is always CC'd) and `uses_inbound_thread` must be true (the reply attaches to the inbound thread via replyToMessageId, never a fresh subject).
- When an existing draft is surfaced instead of creating a new one (`existing_draft_surfaced: true`, `draft_created: false`), no new draft is authored in this step, so the draft-property fields `has_tracker_reference`, `has_security_list_cc`, and `uses_inbound_thread` are all false.
