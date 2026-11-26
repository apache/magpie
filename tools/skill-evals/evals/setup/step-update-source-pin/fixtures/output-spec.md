<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "propose_bump": ["<source id>", ...],
  "warn": ["<source id>", ...],
  "commits": true | false,
  "on_no": "record-decline" | "nothing" | "n/a"
}
```

`propose_bump` lists, sorted, the ids whose pin the step proposes to move to
the curated one; `[]` when none.

`warn` lists, sorted, the ids the step warns about without proposing a bump;
`[]` when none.

`commits` is whether the step commits the trust-list or lock edit itself
(as opposed to staging it with `git add` and leaving the commit to the
adopter).

`on_no` is what the step does when the operator declines a proposed bump:
`record-decline` when it records the answer, `nothing` when it records
nothing, `n/a` when no bump is proposed.

Do not include any text outside the JSON object.
