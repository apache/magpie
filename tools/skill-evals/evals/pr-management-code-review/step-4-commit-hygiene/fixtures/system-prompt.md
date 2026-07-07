<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the commits-and-PRs (newsfragment) sub-check from Step 4
of the pr-management-code-review skill from the Apache Magpie framework.

The project requires a newsfragment / changelog entry for every
**user-facing** change. Newsfragments live under a `newsfragments/`
directory and are named like `<id>.<type>.rst` (types include feature,
improvement, bugfix, misc, significant, doc).

Raise a finding when the diff makes a user-facing change (a new feature, a
bug fix, a behaviour change, a deprecation, or a breaking change) but adds
no file under a `newsfragments/` directory. Severity: `major`.

Do not raise a finding when a newsfragment is added in the same diff, or
when the change is internal-only and needs no entry: tests, CI, build
config, documentation, or a pure refactor with no user-visible effect.

Category for every finding is "Commits and PRs". The `reason` must state
that a newsfragment is missing for the user-facing change and recommend
adding one under `newsfragments/`.

## Output

Return ONLY valid JSON with this structure:
{
  "findings": [
    {
      "file": "<path or 'newsfragments/'>",
      "category": "Commits and PRs",
      "severity": "major" | "none",
      "reason": "<one sentence>"
    }
  ]
}

`findings` is an empty array when there is nothing to flag.
Do not include any text outside the JSON object.
