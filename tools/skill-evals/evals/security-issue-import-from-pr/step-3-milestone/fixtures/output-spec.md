<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **milestone proposal** step of the `security-issue-import-from-pr` skill.

The PR metadata and detected scope are provided. Propose the correct milestone for the new tracker.

Return a JSON object with exactly these fields:

```json
{
  "proposed_milestone": "<string or null>",
  "source": "pr_milestone" | "next_providers_wave" | "ask_user",
  "stop": true | false,
  "rationale": "<one sentence>"
}
```

Field rules:
- `proposed_milestone`: the milestone title to propose. `null` only when `stop` is `true` (milestone does not exist on tracker) or `source` is `ask_user`.
- `source`:
  - `pr_milestone` — airflow or chart scope AND the PR has a milestone; use it directly.
  - `next_providers_wave` — providers scope; the PR's own milestone is ignored regardless of its value; use the next `Providers YYYY-MM-DD` wave date.
  - `ask_user` — airflow/chart scope but the PR has no milestone; surface to user.
- `stop`: `true` if the proposed milestone does not exist on `<tracker>` (blocker). `false` otherwise.
- `rationale`: one sentence.
