<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **recap** step of the `security-issue-import-from-md` skill.

An apply result is provided below. Produce the recap output, then return a JSON object asserting its structural properties.

```json
{
  "has_file_basename": true | false,
  "has_findings_count": true | false,
  "has_tracker_links": true | false,
  "has_skipped_findings": true | false,
  "has_handoff_line": true | false,
  "has_bare_issue_numbers": true | false
}
```

Field rules:
- `has_file_basename`: recap names the source markdown file.
- `has_findings_count`: recap states how many findings were parsed.
- `has_tracker_links`: recap contains a clickable full URL (or `<tracker>#NNN` reference) for each imported finding.
- `has_skipped_findings`: recap lists skipped findings with index and title (if any were skipped; `true` when there are skips and they are listed, `false` when there are no skips).
- `has_handoff_line`: recap contains the next-step hand-off line pointing to security-issue-sync.
- `has_bare_issue_numbers`: `true` if tracker references appear as bare `#NNN` without a full URL — this should be `false` (bare numbers without a surrounding full URL are a formatting violation).
