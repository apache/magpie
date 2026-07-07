<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **field extraction** step of the `security-issue-deduplicate` skill.

Two tracker bodies are provided (keep and drop). Extract all template fields from both and return a JSON object.

```json
{
  "keep": {
    "number": 0,
    "severity": "<string or null>",
    "affected_versions": "<string or null>",
    "reporter_credited_as": "<string or null>",
    "security_mailing_list_thread": "<string or null>",
    "cwe": "<string or null>",
    "cve_tool_link": "<string or null>",
    "pr_with_the_fix": "<string or null>",
    "has_cve_json_attachment": true | false,
    "labels": ["<string>"],
    "milestone": "<string or null>"
  },
  "drop": {
    "number": 0,
    "severity": "<string or null>",
    "affected_versions": "<string or null>",
    "reporter_credited_as": "<string or null>",
    "security_mailing_list_thread": "<string or null>",
    "cwe": "<string or null>",
    "cve_tool_link": "<string or null>",
    "pr_with_the_fix": "<string or null>",
    "has_cve_json_attachment": true | false,
    "labels": ["<string>"],
    "milestone": "<string or null>"
  },
  "cwe_conflict": true | false,
  "severity_propagation_risk": true | false
}
```

Field rules:
- Use `null` for `_No response_` or empty fields.
- `has_cve_json_attachment`: `true` if the tracker has a comment containing a CVE JSON attachment from `generate-cve-json --attach`.
- `cwe_conflict`: `true` when both sides have non-null CWE values that disagree — this is a blocker requiring triager resolution, not silent selection.
- `severity_propagation_risk`: `true` when the drop side has a non-null Severity that differs from the keep side — the drop side's reporter-supplied severity must NOT be propagated into the kept tracker per the independent-scoring rule.
