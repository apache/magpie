<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the AI-generated-code-signals sub-check from Step 4 of
the pr-management-code-review skill from the Apache Magpie framework.

Raise a finding for signals that code was generated without verification:

- A call to a non-existent / fabricated API, method, or import that does
  not exist on the referenced standard library or third-party package
  (for example `json.parse(...)`, which is not a Python stdlib function).
  Severity: `major`.
- A placeholder or stub left in place where real logic is required: a body
  that is only `pass`, `...`, or `raise NotImplementedError`, or a
  `# TODO: implement` / `# your code here` comment standing in for the
  implementation. Severity: `major`.
- A fabricated or templated comment/docstring that describes behaviour the
  code does not implement. Severity: `minor`.

Do not raise a finding for genuine, working code, or for a legitimately
tracked `TODO` that is not standing in for required logic.

Category for every finding is "AI-generated code signals". The `reason`
must name the specific signal (fabricated API, placeholder/stub, or
mismatched comment) and recommend the fix.

## Output

Return ONLY valid JSON with this structure:
{
  "findings": [
    {
      "file": "<path>",
      "category": "AI-generated code signals",
      "severity": "major" | "minor" | "none",
      "reason": "<one sentence>"
    }
  ]
}

`findings` is an empty array when there is nothing to flag.
Do not include any text outside the JSON object.
