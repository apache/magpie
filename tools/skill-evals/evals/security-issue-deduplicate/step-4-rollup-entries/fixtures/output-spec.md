<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **rollup-entry construction** step of the `security-issue-deduplicate` skill.

A merge scenario is provided. Build the two rollup entries and return a JSON object asserting their structural properties.

```json
{
  "kept_entry": {
    "has_drop_tracker_link": true | false,
    "has_one_sentence_headline": true | false,
    "has_credit_lines_for_both": true | false,
    "has_both_thread_refs": true | false,
    "has_next_step": true | false,
    "has_bare_issue_numbers": true | false
  },
  "dropped_entry": {
    "has_keep_tracker_link": true | false,
    "has_one_sentence_headline": true | false,
    "has_second_independent_report_ref": true | false,
    "has_next_step_pointer": true | false,
    "has_bare_issue_numbers": true | false
  }
}
```

Field rules:
- `has_drop_tracker_link` / `has_keep_tracker_link`: the cross-reference must be a full clickable markdown URL, not a bare `#NNN`.
- `has_credit_lines_for_both`: kept entry lists both reporters' credits.
- `has_both_thread_refs`: kept entry references both mailing-list threads (keep and drop).
- `has_next_step`: kept entry ends with a one-line next-step sentence.
- `has_second_independent_report_ref`: dropped entry notes that content was merged as "Second independent report".
- `has_next_step_pointer`: dropped entry points the reader to the kept tracker for ongoing work.
- `has_bare_issue_numbers`: `true` if any cross-reference appears as bare `#NNN` without a full URL — should be `false` for both entries.

Build ONLY the single entry the prompt asks for (the kept entry or the dropped
entry, not both). Report that built entry's real properties. For the entry you
were NOT asked to build, set every `true | false` field in its object to
`false`, because you constructed no text for it, so none of its properties hold. Do
not populate or infer properties for the entry you did not build.
- `has_bare_issue_numbers` stays `false` for a well-formed built entry: always
  render a cross-reference as a full markdown URL, never a bare `#NNN`.
