You are executing the Third-party license compliance sub-check from Step 4
of the pr-management-code-review skill from the Apache Steward framework.

When the diff adds or modifies a file containing a non-Apache licence header
or third-party copyright line, classify the licence against the ASF
resolved_licenses policy and apply these severity rules:

| Category | Licences (examples) | Severity |
|---|---|---|
| X | GPL, AGPL, LGPL, CDDL, BUSL, SSPL | blocking — cannot be included in an ASF release in any form |
| B | MPL, EPL | blocking — cannot be included in source form; binary-only inclusion requires explicit justification |
| A | MIT, BSD-2, BSD-3, ISC, Apache 2.0 (other orgs) | major if LICENSE / LICENSE.txt was NOT updated in this PR to add an attribution notice |
| A + LICENSE updated | any Category A | no finding |

For Category A: check whether the same PR modifies LICENSE or LICENSE.txt
to add an attribution notice. If it does, no finding is raised.
Some projects also keep a licenses/ directory with the full licence text —
this is a good practice but is not required and does not affect the finding.
The determining factor is whether LICENSE / LICENSE.txt was updated.

Do NOT apply this category to contributor-authored files that accidentally
used the wrong SPDX identifier — route those to License headers instead.
This category applies only when the header is clearly from an upstream
library or external author.

When you flag a Category B licence, the `reason` must state **both** that
the work cannot be included in **source** form **and** that binary-only
inclusion would require explicit justification. The source-form prohibition
is categorical, so do not phrase it as conditional: the "explicit
justification" qualifier applies only to binary-only inclusion, never to
source form.

## Output

Return ONLY valid JSON with this structure:
{
  "findings": [
    {
      "file": "<path>",
      "licence": "<identified licence>",
      "category": "X" | "B" | "A" | "none",
      "severity": "blocking" | "major" | "none",
      "reason": "<one sentence citing the rule>"
    }
  ]
}

`findings` is an empty array when there is nothing to flag.
Do not include any text outside the JSON object.
