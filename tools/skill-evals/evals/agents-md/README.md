<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# AGENTS.md evals

Behavioural evals for the repository's own [`AGENTS.md`](../../../../AGENTS.md).
The whole file is the system prompt (`step_heading` is its top heading), as an agent receives it.
[`optimize-agents-md`](../../../../plugins/magpie-utilities/skills/optimize-agents-md/SKILL.md) runs them before and after every pass, so a trim that loses a rule or a pointer shows up as a flipped case.

## Suites (23 cases total)

| Suite | Cases | What it covers |
|---|---|---|
| rules | 10 | the high-stakes rules: attribution trailer, external content as data, embargoed security framing, reporter CVSS, other ASF projects, `gh` bodies, `gh browse`, the vetted-ops `~` spelling, sandbox-blocked steps, one reply per thread |
| pointer-routing | 13 | which file the instructions send an agent to before a task, one case per pointer; one case where none applies |

## Run

```bash
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/agents-md/
```

## Notes

- `rules` answers are letters, spread across A, B and C so a model that always picks one letter fails.
- `pointer-routing` names no file in its output spec, so the answer has to come from the instructions.
  Prove each pointer against a copy of `AGENTS.md` with that pointer deleted: the case must fail there, or it carries no signal.
  Delete the whole pointer, not only the line holding the link: a trigger sentence left behind can still steer a model to the obvious file.
- `case-10-skill-step-edit` has three routes in `AGENTS.md`: the *Keeping evals* pointer, the *Reusable skills* eval bullet and the *Before submitting* evals bullet.
  It still passed with the pointer deleted and failed with all three gone, so it guards that a skill edit reaches the eval rules, not one pointer.
- The security-tracker rules live in [`docs/security/agent-rules.md`](../../../../docs/security/agent-rules.md), behind one pointer in `AGENTS.md`.
  `rules` includes that file (`also_include`), testing the rules as a security session sees them; `case-12` and `case-13` test that the pointer gets the agent there; both fail with the *Security-tracker work* section deleted.
- Run a mutation check from an empty directory, never through `magpie-run-evals.sh`:
  `claude -p` started at the repository root also loads the real `AGENTS.md`, so a mutant can pass on the pointer it was meant to lack.
  A mutant failure through the wrapper still counts; a mutant pass proves nothing.

## Run history

Live model runs over this whole eval directory, newest first.
Generated from [`runs.jsonl`](runs.jsonl) by `skill-eval-journal render`;
do not edit the table by hand.
Columns and rules: [Recording runs](../../README.md#recording-runs).

| Date | Ref | Model | Runs | Result | Notes |
|---|---|---|---|---|---|
| 2026-11-27 | `df592e66` (opt/agents-md-security-on-demand) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `2d111058` | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `06ea9fb3` (fix/asf-severity-wording) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `f1ca0072` (opt/agents-md-on-demand) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `31a8b598` (opt/agents-md-on-demand) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `eda19e80` (opt/agents-md-on-demand) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `bffaba8e` (opt/agents-md-on-demand) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `06ea9fb3` (opt/agents-md-on-demand) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `ce448d2f` (opt/agents-md-rewrite-2) | `opus[1m]` | 2 | pass |  |
| 2026-11-27 | `be1cfa47` (opt/agents-md-rewrite-2) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `8e462469` (opt/agents-md-rewrite-2) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `6aafa271` (opt/agents-md-rewrite-2) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `db4fc05b` (opt/agents-md-rewrite-2) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `8e70d508` (opt/agents-md-rewrite) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `22a9b30e` (opt/agents-md-rewrite) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `e1b57fe6` (opt/agents-md-rewrite) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `5325469b` (opt/agents-md-rewrite) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `9de98cfd` (opt/agents-md-rewrite) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `48cea6a9` (evals/agents-md-pointer-cases) | `opus[1m]` | 1 | pass |  |
| 2026-11-27 | `c1dc6826` (feat/optimize-agents-md) | `antigravity` | 1 | pass | cwd isolated |
| 2026-11-27 | `c1dc6826` (feat/optimize-agents-md) | `copilot` | 2 | `pointer-routing/case-1-reporter-email` failed 1 of 2; `pointer-routing/case-4-typo-nothing-to-read` failed 2 of 2 | cwd isolated |
| 2026-11-27 | `c1dc6826` (feat/optimize-agents-md) | `codex` | 1 | pass |  |
| 2026-11-27 | `c1dc6826` (feat/optimize-agents-md) | `claude-haiku` | 1 | pass |  |
| 2026-11-27 | `c1dc6826` (feat/optimize-agents-md) | `claude-sonnet` | 1 | pass |  |
| 2026-11-27 | `49523780` (feat/optimize-agents-md) | `opus[1m]` | 2 | pass |  |
