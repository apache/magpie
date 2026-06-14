<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 3 output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "binding_plus1": <integer>,
  "binding_minus1": <integer>,
  "binding_zero": <integer>,
  "nonbinding_plus1": <integer>,
  "nonbinding_minus1": <integer>,
  "nonbinding_zero": <integer>,
  "fractional_count": <integer>,
  "excluded_ambiguous_count": <integer>,
  "result": "PASSED" | "FAILED",
  "pass_rule_applied": "<description of rule>",
  "subject": "<result email subject line>",
  "body": "<result email body>",
  "proposed_label": "vote-passed" | "rc-rolled",
  "force_close_logged": true | false
}
```

Grading rules:
- `result` is `"PASSED"` iff `binding_plus1 >= 3` AND `binding_plus1 > binding_minus1`.
- `result` is `"FAILED"` in all other cases.
- `proposed_label` is `"vote-passed"` when `result` is `"PASSED"`.
- `proposed_label` is `"rc-rolled"` when `result` is `"FAILED"`.
- `subject` must contain the version and rcN from the RC identifier.
- `body` must contain the binding and non-binding vote counts.
- `force_close_logged` is `true` only when `--force-close` was accepted at Step 0.
- No extra keys are permitted.
