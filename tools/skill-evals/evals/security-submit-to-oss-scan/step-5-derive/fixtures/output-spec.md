<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **threat-model derivation** step (Step 5) of the `security-submit-to-oss-scan` skill.

Below are excerpts of a project's published security model and one statement the maintainer would like the scanner's `threat_model.md` to make.
Decide whether the statement goes into the summary, which model section supports it, and whether it is a model gap.

Return a JSON object with exactly these fields:

```json
{
  "include_in_summary": true | false,
  "model_section": "<the section heading or anchor that supports the statement, or empty>",
  "model_gap": true | false,
  "route": "security-model-update" | "",
  "rationale": "<one line>"
}
```

Field rules:
- `include_in_summary` is `true` **only** when a section of the model supports the statement; `model_section` then names it.
- A statement the model does not support is a **model gap**: `include_in_summary` is `false`, `model_gap` is `true`, `route` is `security-model-update` — however reasonable the statement sounds.
- `route` is empty when `model_gap` is `false`.
