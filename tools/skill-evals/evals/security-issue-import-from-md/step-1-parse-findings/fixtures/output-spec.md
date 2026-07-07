<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **finding parser** step of the `security-issue-import-from-md` skill.

A markdown findings file (or excerpt of one) is provided below as a mock file read. Parse it into the findings list according to the step rules.

Return a JSON object with exactly these fields:

```json
{
  "findings": [
    {
      "index": 1,
      "title": "<string>",
      "severity": "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN",
      "category": "<string or null>",
      "repository": "<string or null>",
      "branch": "<string or null>",
      "date_created": "<string or null>",
      "has_details": true | false,
      "has_impact": true | false,
      "has_repro_steps": true | false,
      "warnings": ["<string>"]
    }
  ],
  "total_findings": 1
}
```

Field rules:
- `severity`: normalised to uppercase. If the raw value is not one of HIGH, MEDIUM, LOW, UNKNOWN, record `UNKNOWN` and add a warning string.
- `warnings`: list any validation issues (missing sections, bad severity, missing repository, etc.). Empty array if clean.
- `has_details`, `has_impact`, `has_repro_steps`: `true` if the section is present and non-empty.
- `total_findings`: count of findings successfully parsed (including those with warnings).
