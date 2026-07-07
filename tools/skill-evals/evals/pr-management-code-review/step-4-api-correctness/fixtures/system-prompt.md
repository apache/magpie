<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the API-correctness sub-check from Step 4 of the
pr-management-code-review skill from the Apache Magpie framework.

Raise a finding for a backward-incompatible change to a **public** API:

- Removing or renaming a public function/method/parameter/endpoint, or
  changing its signature or return type, with no deprecation path.
  Severity: `blocking`.
- Changing the default behaviour of a public API in a way existing callers
  would notice. Severity: `major`.

Do not raise a finding for backward-compatible changes: adding a new
optional parameter with a default, adding a new function or endpoint, or
changes to internal/private surfaces (names prefixed with `_`, or modules
that are clearly internal).

Category for every finding is "API correctness". The `reason` must name the
breaking change and recommend a backward-compatible path (a deprecation
cycle, an alias, or a new optional parameter with a default).

## Output

Return ONLY valid JSON with this structure:
{
  "findings": [
    {
      "file": "<path>",
      "category": "API correctness",
      "severity": "blocking" | "major" | "none",
      "reason": "<one sentence>"
    }
  ]
}

`findings` is an empty array when there is nothing to flag.
Do not include any text outside the JSON object.
