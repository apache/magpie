<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **canned-response matching** step of the `security-issue-invalidate` skill.

A reasoning summary extracted from the tracker discussion is provided. Your job is to select the best-matching canned-response section from `canned-responses.md` given the invalidity reasoning shape.

Return a JSON object with exactly these fields:

```json
{
  "selected_canned_section": "<section name string>",
  "confidence": "exact" | "best_fit" | "default",
  "rationale": "<one sentence explaining why this section fits>",
  "other_applicable": ["<section name>"]
}
```

Field rules:
- `selected_canned_section`: the canonical section name from the decision table (e.g. "Negative Assessment response", "When someone claims Dag author-provided \"user input\" is dangerous", "DoS/RCE/Arbitrary read via Provider's Connection configuration", "Immediate response for self-XSS issues triggered by Authenticated users", "DoS issues triggered by Authenticated users", "Parameter injection to operator or hook", "Automated scanning results", "When someone submits a media report").
- `confidence`: `exact` when the reasoning maps directly to a named section; `best_fit` when close but not precise; `default` when falling back to "Negative Assessment response".
- `rationale`: one sentence.
- `other_applicable`: list of other sections that could partially apply (may be empty array).
