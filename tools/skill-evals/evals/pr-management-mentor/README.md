<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-management-mentor evals

Behavioral evals for the `pr-management-mentor` skill.

## Suites (29 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| intervention | Intervention selection (steps 3–5 of the runtime loop) | 9 | Template 1 (missing repro); template 2 (missing version); template 3 (convention gap); template 4 (why-pushback → hand-off); multiple triggers simultaneously (ask); maintainer already engaged (silent); no trigger fires (silent); out-of-scope topic (hand-off); out-of-scope deprecation/removal decision carrying draftable bug signals (hand-off still wins) |
| tone-checks | Pre-post checklist | 15 | Clean pass; hard-fail rules 1 (praise), 2 (restating), 3 (AI self-ref), 4 (speaking for maintainer), 5 (hedging), 6 (multiple asks), 7 (missing footer), 8 (author not tagged), 9 (quoted doc), 10 (review prediction); soft-fail rules 11 (meta first line), 12 (too long), 13 (jargon without link), 14 (exclamation in body) |
| hand-off | Hand-off triggers | 5 | No trigger; trigger 1 (max turns reached); trigger 2 (contributor pushback on why-answer); trigger 3 (out-of-scope topic); trigger 4 (contributor asks for human — highest priority) |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-mentor/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-mentor/intervention/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-mentor/intervention/fixtures/case-1-missing-repro
```
