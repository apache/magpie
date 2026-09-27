<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "rows": [
    { "thread_id": "<id>", "nominee_name": "<as written>", "handle": null, "target": "committer | pmc", "vote_date": "YYYY-MM-DD", "outcome": "elected | deferred | withdrawn", "deferral_category": "narrow-focus | little-list-presence | short-tenure | other | null" }
  ],
  "skipped_threads": [ { "thread_id": "<id>", "reason": "excluded | after-holdout" } ],
  "injection_attempt_detected": true | false
}
```

- `rows`: one per nomination, in the order the nominations first appear in the input; `thread_id` is the [VOTE] thread's id when there is one, else the [DISCUSS] thread's id.
- `handle`: always null at this step.
- `skipped_threads`: threads left out of `rows`, with the reason, in input order; empty when none.
- Rows carry only the fields above.

Do not include any text outside the JSON object.
