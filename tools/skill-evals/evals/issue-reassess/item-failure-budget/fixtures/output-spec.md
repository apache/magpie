<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "continue" | "stop",
  "stop_reason": "budget" | "write-failure" | "config-error" | null,
  "failed": [<item number>, ...],
  "unfinished": [<item number>, ...],
  "retry_write": false,
  "rerun_selector": "<comma-separated item numbers>" | null
}
```

- `action` — `continue` when the sweep carries on with the next item; `stop` when it stops now.
- `stop_reason` — `budget` when more items failed than the budget allows; `write-failure` when a post, label, close or transition failed; `config-error` when `item_failure_budget` is malformed; `null` when `action` is `continue`.
- `failed` — the items recorded as `failed`, ascending. A write failure is listed here too.
- `unfinished` — the items not reached, ascending; `[]` when the sweep continues.
- `retry_write` — `true` if the failed write would be attempted again in this run. Always `false` under the rule.
- `rerun_selector` — the selector that reruns exactly the failed and unfinished items, numbers ascending and comma-separated with no spaces (e.g. `"12,15"`); `null` when there are none, or when the run stopped on a config error before any item.
