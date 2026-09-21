<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# preflight-reconciliation evals

Behavioral evals for the shared pre-flight block
([`tools/dev/preflight-block.md`](../../../dev/preflight-block.md)) that
every non-`setup` `SKILL.md` carries — specifically the reconciliation
comparison step every skill runs against itself before doing anything
else.

## Suites (5 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-reconciliation | `## Pre-flight — is this project set up?` | 5 | comparing a skill's own `surface_hash` against the project's `reconciled:` stamp |

## Run

```bash
# All cases
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/preflight-reconciliation/

# Single suite
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/preflight-reconciliation/step-reconciliation/fixtures/

# Single case
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/preflight-reconciliation/step-reconciliation/fixtures/case-1-in-sync
```

## Notes

- `step-config.json` points at `tools/dev/preflight-block.md` itself,
  not at a particular skill's `SKILL.md` — the block is generated
  verbatim into every non-`setup` skill, so testing the source is
  equivalent to testing any one of its ~75 copies, and stays accurate
  without picking one skill to stand in for the rest.
- `case-1-in-sync` and `case-5-declined` both land on `outcome: silent`,
  for different reasons: case 1 because the stamped hash matches
  outright, case 5 because it differs but was already declined for this
  exact hash (`acknowledged` matches).
- `case-2-config-moved` and `case-1-in-sync` both describe a readable
  marketplace clone one dev build ahead of what is installed.
  `case-2`'s `expected.json` carries that version in
  `update_available` — the piggybacked report a non-silent check may
  add. `case-1`'s expects `update_available: null`, pinning the rule
  that a silent reconciliation check says nothing about updates, even
  when a newer version is visible.
- `case-3-anchor-moved` and `case-4-no-stamp` both expect
  `update_available: null`: the fixtures give no marketplace-clone
  state, so there is nothing to report.
- The four `outcome` values are the whole vocabulary this check has:
  `silent`, `propose_config`, `propose_reanchor`, `propose_sweep`. No
  case exercises the install-method branch (marketplace floor vs.
  snapshot pin) because the reconciliation comparison is method-agnostic
  by design — see `docs/setup/agentic-overrides.md`'s *Reconciliation on
  framework upgrade* section.
