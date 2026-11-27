<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# AGENTS.md evals

Behavioural evals for this repository's `AGENTS.md`, started from [`optimize-agents-md`](https://github.com/apache/magpie/tree/main/plugins/magpie-utilities/skills/optimize-agents-md)'s template.
The whole file is the system prompt (`step_heading` is its top heading), as an agent receives it.
`optimize-agents-md` runs them before and after every pass, so a trim that loses a rule or a pointer shows up as a flipped case.

## Suites

| Suite | What it covers |
|---|---|
| rules | one multiple-choice case per pinned section and per high-stakes rule, the right letter spread across A, B and C |
| pointer-routing | which file the instructions send an agent to before a task, one case per pointer, plus one where nothing should be read |

## Run

Under the secure setup, through its installed wrapper, as a bare command from the repository root:

```bash
~/.claude/scripts/magpie-run-evals.sh .apache-magpie-overrides/evals/agents-md
```

The wrapper runs outside the sandbox from a copy the agent cannot edit.
Do not replace it with a hand-run command against the Magpie framework's cached tools: a sandboxed agent can write that tree, so running it outside the sandbox runs agent-editable code.

Where no sandbox is in use at all, run the runner directly (`<framework>` is the installed Magpie framework):

```bash
PYTHONPATH=<framework>/tools/skill-evals/src python3 -m skill_evals.runner \
  .apache-magpie-overrides/evals/agents-md --cli "claude -p" --cli-cwd "$(mktemp -d)"
```

`--cli-cwd` starts the model in an empty directory: from the repository root it would also load the real `AGENTS.md`, and a pointer check could pass on the pointer it deleted.

## Notes

- `pointer-routing` names no file in its output spec, so the answer has to come from the instructions.
  Prove each pointer against a copy of `AGENTS.md` with the whole pointer deleted: the case must fail there, or it carries no signal.
