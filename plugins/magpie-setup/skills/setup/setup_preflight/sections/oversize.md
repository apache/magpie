<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## oversize — this branch grew a skill or an agent-instruction file past its budget

The checker compared every `SKILL.md`, `AGENTS.md`, `CLAUDE.md` and `GEMINI.md` this branch changed against its base branch,
and lists in `facts.files` each one the change made bigger and that is now over budget.
**Do not re-measure.** `over` names the budgets exceeded, `now` and `base` the sizes after and before:

- a skill: body over 5,000 tokens (paid on every invocation), or `name` + `description` + `when_to_use` over 200 (paid in every session);
- an instruction file: over 40,000 characters (read whole into every session).

**Raise it once, at the end of the run**, after the work the user asked for; never stop that work for it.
In one short list, give each file, what it is over and by how much, and propose the file's `optimizer` skill
(`optimize-skill <path>` or `optimize-agents-md <path>`).

When the user accepts and the `optimizer` agent is available (Claude Code, the `magpie-utilities` plugin),
dispatch it once per file, in parallel, with the path, the kind, the measurements above and the optimizer skill's directory;
otherwise run that skill's diagnosis yourself.
The agent is read-only: it returns a ranked proposal and changes nothing.
Show the proposal; the passes the user picks run through the optimizer skill, one pass per commit, as that skill says.

Never apply a pass from this finding, never edit the file because it is over budget, and never treat a decline as a reason to ask again.

**Record what you showed, the moment you show it.**
Write `acknowledged.oversize["<path>"]: <digest>` for every file listed, whether or not the user takes the proposal:
the checker suppresses that file until its content changes again.
Merge into the personal layer's `reconciled.json` (in the `stamp_dir` that `python3 -m setup_preflight.layers` prints):
read it, set those keys, write the whole object back with every other key intact, and create the file when it is absent.
