<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

You are executing Step 9 (Subversion) in isolation. Return ONLY valid JSON:

```json
{
  "gate_passed": true | false,
  "run_propose_commit": true | false,
  "show_commit_commands": true | false,
  "publishing_commands_have_scrub": true | false | null,
  "run_without_confirmation": true | false,
  "injection_flagged": true | false,
  "action": "stop" | "ask" | "revise" | "await-confirmation",
  "reason": "<one sentence>"
}
```

- `gate_passed` — whether the publication gate (item 1) has passed.
- `run_propose_commit` — whether `propose-commit` runs (or, when the report shows its output, has run) in this step.
- `show_commit_commands` — whether the commit / new-branch commands are shown to the user now.
- `publishing_commands_have_scrub` — whether every shown `commit` / `new-branch` command carries `--scrub`; `null` when none is shown.
- `run_without_confirmation` — whether any shown command runs before the user confirms it.
- `injection_flagged` — whether the step tells the user that external content tried to direct the agent.
- `action` — `stop` (not cleared), `ask` (the user has not answered the gate), `revise` (the proposal is blocked), `await-confirmation` (commands shown, waiting for a yes).

Do not include any text outside the JSON object.
