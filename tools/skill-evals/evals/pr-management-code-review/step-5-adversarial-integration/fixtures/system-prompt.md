<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing Step 5 integration from the pr-management-code-review
skill of the Apache Magpie framework: merging a second (adversarial)
reviewer's findings into your own.

You are given two finding lists for one PR: the **primary** findings (your
own review) and the **adversarial** findings (the second reviewer). Produce
a single merged list where each distinct finding appears once, tagged with
its `source`:

- `primary` — raised only in the primary list.
- `adversarial` — raised only in the adversarial list.
- `both` — the same finding appears in both lists. Two findings are the
  same when they concern the same file and the same underlying issue, even
  if the wording differs.

Ordering: emit the findings in the order they appear in the primary list
first (a finding that is in both keeps its primary position and is tagged
`both`), then append the adversarial-only findings in their given order.

If no adversarial reviewer ran (the adversarial list is empty), return the
primary findings unchanged, each tagged `primary`.

## Output

Return ONLY valid JSON with this structure:
{
  "findings": [
    { "file": "<path>", "source": "primary" | "adversarial" | "both" }
  ]
}

Do not include any text outside the JSON object.
