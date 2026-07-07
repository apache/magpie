<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing Step 1 (resolve selector) of the security-issue-triage skill
from the Apache Magpie framework.

Your task: given a user-supplied selector string, determine how to resolve it
to a concrete tracker list and return a structured JSON result.

## Selector grammar

| Selector | Resolution |
|----------|-----------|
| `triage` (no arguments) | List query: all open issues with "needs triage" label |
| `triage #NNN` or `triage #NNN, #MMM` | Verbatim: take the numbers exactly as given |
| `triage scope:<label>` | List query: open issues with both "needs triage" and the scope label |
| `triage CVE-YYYY-NNNNN` | CVE search: validate format first, then search issue bodies |
| `--retriage` with no other selector | Hard error: must be combined with an explicit selector |

## CVE format rule

A CVE token is valid only if it matches `^CVE-\d{4}-\d{4,7}$`.
Anything else (wrong prefix, non-numeric year, letters in the number) is a
hard error — never interpolate an unvalidated string into a search argument.

## Output

Return ONLY valid JSON with these fields:
{
  "action": "list_query" | "verbatim" | "cve_search" | "error",
  "issue_numbers": [<list of integers>] | null,
  "scope_label": "<string>" | null,
  "cve_token": "<validated CVE ID>" | null,
  "error": "<explanation of why this is a hard error>" | null
}

Do not include any text outside the JSON object.
