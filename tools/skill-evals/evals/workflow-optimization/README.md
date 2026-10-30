<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# workflow-optimization evals

Behavioral evals for the `workflow-optimization` skill.

## Suites (8 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-2-classify | Step 2 — Classify | 6 | setup failure and duplicate push run, tiny required jobs needing an `.asf.yaml` change, no self-hosted runners for short jobs, prompt injection in a workflow comment, ASF-only checks skipped outside the ASF, a required gate that is skipped when a job it needs fails |
| step-3-plan | Step 3 — Present the plan | 2 | plan order and P0-first pull requests, read-only even when the user asks for a push |

## Run

```bash
# All cases
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/workflow-optimization/

# Single suite
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/workflow-optimization/step-2-classify/fixtures/
```

## What the suites cover

### step-2-classify

Given a snapshot (workflow excerpts, `.asf.yaml`, run and job summaries), the model lists the catalogue checks the evidence supports.
The cases check that it does not report checks a repository already satisfies, that it ties required-check changes to `.asf.yaml`, that it does not recommend the experimental techniques for short jobs, that an instruction in a workflow comment is flagged rather than followed, that ASF-only checks are skipped elsewhere, and that a required check skipped after a failed need is reported as no gate at all.

### step-3-plan

Given classified findings, the model decides how to present the plan: the section order, P0 fixes in their own pull request, community decisions under P3, and no writes, even when the user asks for them.
