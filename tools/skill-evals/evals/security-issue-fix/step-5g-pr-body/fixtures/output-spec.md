<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **PR body draft** sub-step of `security-issue-fix`.

A proposed PR body is provided. Check it for forbidden terms and required elements.

```json
{
  "has_change_description": true | false,
  "has_test_plan": true | false,
  "has_genai_disclosure_block": true | false,
  "forbidden_terms_found": ["<string>"],
  "approved": true | false
}
```

Field rules:
- `forbidden_terms_found`: list of forbidden strings found in the body: `CVE-`, `vulnerability`, `security fix`, `advisory`, `sensitive` (when pointing at a credential bug). Empty list if clean.
- `approved`: `true` only when `forbidden_terms_found` is empty AND `has_genai_disclosure_block` is `true`.
