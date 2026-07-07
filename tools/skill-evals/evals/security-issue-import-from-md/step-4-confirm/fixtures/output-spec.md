<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **confirmation parsing** step of the `security-issue-import-from-md` skill.

A proposal has been surfaced to the user (shown in the report). The user's reply is shown at the end. Parse the reply and return the apply plan.

Return a JSON object with exactly these fields:

```json
{
  "action": "import_all" | "import_partial" | "cancel",
  "findings_to_import": [1, 2, 3],
  "findings_skipped": [4],
  "rationale": "<one sentence>"
}
```

Field rules:
- `action`: `import_all` if user said `go`/`proceed`/`yes, all`; `import_partial` if user said `skip <N>`; `cancel` if user said `cancel`/`none`/`hold off`.
- `findings_to_import`: 1-based indices of findings that will get trackers created. Empty array for `cancel`.
- `findings_skipped`: 1-based indices explicitly dropped. Empty array for `import_all` or `cancel`.
- `rationale`: one sentence.
