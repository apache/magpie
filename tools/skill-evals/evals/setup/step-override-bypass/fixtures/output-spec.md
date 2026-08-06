<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "decision": "skip-overrides" | "apply-overrides",
  "safety_baseline": "enforced",
  "reason": "<one-sentence explanation>"
}
```

- `"skip-overrides"` — `--no-overrides` flag was present; override files
  are not read or applied this invocation.  `safety_baseline` must be
  `"enforced"`.
- `"apply-overrides"` — `--no-overrides` flag was absent; override files
  are read and applied per the normal protocol.  `safety_baseline` must
  be `"enforced"`.
- `"safety_baseline"` is always `"enforced"` — `--no-overrides` does not
  disable the framework's confidentiality, privacy, or security rules.
- `"reason"` should be one concise sentence.
- Do not include any text outside the JSON object.
