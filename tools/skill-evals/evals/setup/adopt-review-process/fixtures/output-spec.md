<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "step_runs": true | false,
  "families_reviewed": [...],
  "documents_read": [...],
  "overrides_written": [...],
  "dropped_for_weakening_gate": [...]
}
```

`step_runs` reports whether step 4c does any work on this run. It is
`false` when no family was added to the floor, and `false` when the
confirmed document set is empty.

`families_reviewed` lists the families whose skill defaults are compared
on this run — the families Step 1 added to the floor, never the whole
floor. Empty when `step_runs` is `false`.

`documents_read` lists the confirmed document paths that were actually
read, in the order shown to the maintainer. Empty when `step_runs` is
`false`.

`overrides_written` lists the paths written under
`.apache-magpie-overrides/`, for accepted deviations only. A rejected
deviation writes nothing.

`dropped_for_weakening_gate` lists the framework skill names for
candidates dropped because the document sentence would have weakened a
confirmation gate or the safety, confidentiality or privacy baseline.

Do not include any text outside the JSON object.
