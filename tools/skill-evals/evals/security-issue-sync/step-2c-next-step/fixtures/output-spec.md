<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Output specification — Step 2c next-step recommendation

Return a JSON object with these boolean/integer fields.  Do not include the
prose recommendation text itself — only the structural assertions below.

```json
{
  "step_number": <integer — the process step number the recommendation is for>,
  "has_concrete_action": <bool — recommendation includes a concrete action for the user to take>,
  "references_cve_allocate_skill": <bool — recommendation explicitly names or links the security-cve-allocate skill>,
  "has_skill_link": <bool — recommendation includes a markdown link to a skill or doc>,
  "has_bare_issue_numbers": <bool — recommendation contains a bare #NNN or tracker#NNN reference (should be false)>
}
```

Rules:
- `step_number` is the integer that follows "Step" in the recommendation (e.g. "Step 6: …" → 6).
- `has_concrete_action` is true unless the recommendation is purely informational/parking ("no action needed").
- `references_cve_allocate_skill` is true only when the `security-cve-allocate` skill is explicitly named.
- `has_skill_link` is true when any markdown hyperlink whose href ends in `SKILL.md` appears in the recommendation.
- `has_bare_issue_numbers` must be false — any `#NNN` or `<tracker>#NNN` not wrapped in a markdown link is a violation.
