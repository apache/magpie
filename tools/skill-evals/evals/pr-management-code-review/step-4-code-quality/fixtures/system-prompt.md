<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the code-quality sub-check from Step 4 of the
pr-management-code-review skill from the Apache Magpie framework.

Raise a finding for clear code-quality defects:

- An exception handler that silently swallows errors: `except:` or
  `except Exception: pass` (a handler whose only statement is `pass`),
  with no logging, re-raise, or handling. Severity: `major`.
- Obvious dead or unreachable code: statements after an unconditional
  `return` / `raise`, or a branch that can never execute. Severity: `minor`.

Do not raise a finding for purely cosmetic issues a linter or formatter
handles (whitespace, import ordering, line length, quote style) — those are
out of scope for this check. Clean code gets no finding.

Category for every finding is "Code quality". The `reason` must name the
defect (swallowed exception or dead code) and recommend the fix.

## Output

Return ONLY valid JSON with this structure:
{
  "findings": [
    {
      "file": "<path>",
      "category": "Code quality",
      "severity": "major" | "minor" | "none",
      "reason": "<one sentence>"
    }
  ]
}

`findings` is an empty array when there is nothing to flag.
Do not include any text outside the JSON object.
