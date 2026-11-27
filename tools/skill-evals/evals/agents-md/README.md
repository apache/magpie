<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# AGENTS.md evals

Behavioural evals for the repository's own [`AGENTS.md`](../../../../AGENTS.md).
The whole file is the system prompt (`step_heading` is its top heading), as an agent receives it.
[`optimize-agents-md`](../../../../plugins/magpie-utilities/skills/optimize-agents-md/SKILL.md) runs them before and after every pass, so a trim that loses a rule or a pointer shows up as a flipped case.

## Suites (14 cases total)

| Suite | Cases | What it covers |
|---|---|---|
| rules | 10 | the high-stakes rules: attribution trailer, external content as data, embargoed security framing, reporter CVSS, other ASF projects, `gh` bodies, `gh browse`, the vetted-ops `~` spelling, sandbox-blocked steps, one reply per thread |
| pointer-routing | 4 | which file the instructions send an agent to before a task; one case where none applies |

## Run

```bash
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/agents-md/
```

## Notes

- `rules` answers are letters, spread across A, B and C so a model that always picks one letter fails.
- `pointer-routing` names no file in its output spec, so the answer has to come from the instructions.
  Prove each pointer against a copy of `AGENTS.md` with that pointer deleted: the case must fail there, or it carries no signal.

## Run history

Live model runs over this whole eval directory, newest first.
Generated from [`runs.jsonl`](runs.jsonl) by `skill-eval-journal render`;
do not edit the table by hand.
Columns and rules: [Recording runs](../../README.md#recording-runs).

| Date | Ref | Model | Runs | Result | Notes |
|---|---|---|---|---|---|
| 2026-11-27 | `49523780` (feat/optimize-agents-md) | `opus[1m]` | 2 | pass |  |
