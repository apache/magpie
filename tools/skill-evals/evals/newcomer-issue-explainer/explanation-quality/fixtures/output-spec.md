<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "passed": true | false,
  "failing_checks": ["<check-code>", ...]
}
```

- `passed` is `true` when `failing_checks` is `[]`.
- `failing_checks` lists every failing check code (E1–E5), sorted
  alphabetically.
- Do not include any text outside the JSON object.

### How to select failing checks

- Evaluate each check E1–E5 independently against its own definition in the
  checklist. A check fails ONLY when its own stated condition is violated.
- Flag the check for the ROOT violation, not for downstream symptoms it
  causes. If one section widens the task beyond the issue scope, that is an
  E1 failure; do not additionally flag E3 (done definition) or other checks
  merely because the extra scope also affects those sections.
- E2 requires a concrete file path, component name, or function name. A
  generic pointer such as "look around the source tree" or "find where the
  options are set up" does NOT satisfy E2 and fails it, even when every
  other section is well written.
- Include a code in `failing_checks` only when you can point to the specific
  sentence that violates that check's definition. Do not add codes on
  suspicion or as a precaution.
