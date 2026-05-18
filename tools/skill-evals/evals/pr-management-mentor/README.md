# pr-management-mentor evals

Behavioral evals for the `pr-management-mentor` skill.

## Suites (20 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| tone-checks | Pre-post checklist | 15 | Clean pass; hard-fail rules 1 (praise), 2 (restating), 3 (AI self-ref), 4 (speaking for maintainer), 5 (hedging), 6 (multiple asks), 7 (missing footer), 8 (author not tagged), 9 (quoted doc), 10 (review prediction); soft-fail rules 11 (meta first line), 12 (too long), 13 (jargon without link), 14 (exclamation in body) |
| hand-off | Hand-off triggers | 5 | No trigger; trigger 1 (max turns reached); trigger 2 (contributor pushback on why-answer); trigger 3 (out-of-scope topic); trigger 4 (contributor asks for human — highest priority) |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-mentor/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-mentor/tone-checks/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-mentor/tone-checks/fixtures/case-12-review-prediction
```
