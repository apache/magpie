<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the image IP sub-check from Step 4 of the
pr-management-code-review skill from the Apache Magpie framework.

When the diff adds binary image files (.png, .jpg, .jpeg, .gif, .svg,
.ico, .webp), use judgement rather than raising an automatic finding:

- Contributor-created screenshots, diagrams, and documentation graphics
  are legitimate by default — no finding.
- Logos, brand assets, or illustrations that look professionally produced
  warrant a comment asking the contributor to confirm the source and
  licence. Use the text: "Could you confirm this image is original work
  or confirm its licence? If it's from a third-party source, it may need
  a LICENSE entry or a different approach."

Do not flag every image addition. The signal is the visual character of
the asset — a hand-drawn architecture diagram is different from a
polished brand logo. When in doubt, ask rather than block.

## Output

Return ONLY valid JSON with this structure:
{
  "findings": [
    {
      "file": "<path>",
      "severity": "comment" | "none",
      "reason": "<one sentence explaining the judgement>"
    }
  ]
}

Only include files that warrant a comment. `findings` is an empty array
when there is nothing to flag.
Do not include any text outside the JSON object.
