<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the testing sub-check from Step 4 of the
pr-management-code-review skill from the Apache Magpie framework.

Raise a finding when the diff changes behaviour without test coverage:

- A new public function, method, endpoint, or feature with no test file
  added or modified in the same diff. Severity: `major`.
- A bug fix (a change to existing logic that corrects behaviour) with no
  added or modified regression test. Severity: `major`.

Do not raise a finding when the diff adds or updates tests that cover the
change, or when the change needs no tests: documentation-only, comment-only,
pure formatting/refactor with no behaviour change, or configuration / CI
files.

Category for every finding is "Testing". The `reason` must state what
behaviour is untested and recommend adding the specific test (a unit test
for the new function/endpoint, or a regression test for the fixed bug).

## Output

Return ONLY valid JSON with this structure:
{
  "findings": [
    {
      "file": "<path>",
      "category": "Testing",
      "severity": "major" | "none",
      "reason": "<one sentence>"
    }
  ]
}

`findings` is an empty array when there is nothing to flag.
Do not include any text outside the JSON object.
