# good-first-issue-author evals

Behavioral evals for the `good-first-issue-author` skill.

## Suites (13 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| suitability-gate | Suitability gate (step 3 of the runtime loop) | 8 | suitable (no factors); the four Tier 1 hard stops (`scope-too-large`, `security-sensitive`, `architectural-decision`, `deprecation-decision`); a single Tier 2 miss (`no-code-pointer`); a multi-factor Tier 2 case (`no-acceptance-criteria` + `no-code-pointer` + `scope-unclear`); a prompt-injection candidate that is suitable on its merits but flagged |
| readiness-check | Readiness checklist R1-R9 (step 5 of the runtime loop) | 5 | clean pass; missing code pointer (R3); missing acceptance criteria (R4); missing effort estimate + missing footer (R5 + R9); a prompt-injection draft that is content-complete but flagged |

Both steps use `step-config.json`, so the prompt is extracted live from
the skill text: the suitability gate from
`.claude/skills/good-first-issue-author/SKILL.md` (`## Suitability gate`),
the readiness checklist from
`.claude/skills/good-first-issue-author/readiness-checks.md`
(`## Readiness checklist`). A change to either section is reflected in the
prompt, so the eval catches prompt-vs-output drift.

## Run

```bash
# All cases (pure-stdlib runner, no uv/network needed)
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/good-first-issue-author/

# One suite
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/good-first-issue-author/suitability-gate/fixtures/

# One case
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/good-first-issue-author/suitability-gate/fixtures/case-1-suitable

# Automated comparison against a model CLI
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "claude -p" \
    tools/skill-evals/evals/good-first-issue-author/
```

All cases use exact-match `expected.json` (enums, sorted code lists, and
booleans), so `--cli` mode reports PASS/FAIL automatically with no MANUAL
fallbacks.
