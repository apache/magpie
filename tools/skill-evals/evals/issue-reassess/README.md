<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# issue-reassess evals

Behavioral evals for the `issue-reassess` skill. The campaign-level
tallies are already covered by the sibling `issue-reassess-stats` suite,
so these suites anchor on the three places where this skill makes a
*decision* of its own: whether to re-run a candidate, whether a
maintainer comment lets it skip reproduction, and which verdicts become
report headlines.

## Suites (10 cases total)

| Suite | Anchor | Cases | What it covers |
|---|---|---|---|
| step-2-resumability | `SKILL.md` → Step 2 (resumability check) | 3 | fresh campaign with auto-generated id, all four artefact states in one pool, everything reusable at the current rev |
| skip-if-resolvable | `per-issue-flow.md` → 1. Skip-if-resolvable check | 5 | fixed-in-version citation, sibling duplicate, won't-fix by design, no shortcut, injected instruction (adversarial) |
| headline-extraction | `verdict-aggregation.md` → Headline extraction | 2 | mixed verdicts bucketed into action / closure / hygiene, all-fixed campaign |

## Run

```bash
# All cases
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/issue-reassess/

# Single suite
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/issue-reassess/skip-if-resolvable/fixtures/

# Automated, against Claude Code print mode
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "claude -p" \
    tools/skill-evals/evals/issue-reassess/
```
