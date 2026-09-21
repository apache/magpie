<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# preflight-reconciliation evals

Behavioral evals for the shared pre-flight block
([`tools/dev/preflight-block.md`](../../../dev/preflight-block.md)) that
every non-`setup` `SKILL.md` carries — specifically the reconciliation
comparison step every skill runs against itself before doing anything
else.

## Suites (6 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-reconciliation | `## Pre-flight — is this project set up?` | 6 | comparing a skill's own `surface_hash` against the project's `reconciled:` stamp |

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
- **The stamp key is a skill's frontmatter `name:`** (e.g.
  `magpie-pr-management-code-review`), not `<plugin>/<skill>`: it is
  already in the running skill's own context, unique across the
  framework, and identical under every install shape, including a
  snapshot install with no plugin component to derive at all.
- `case-1-in-sync` and `case-5-declined` both land on `outcome: silent`,
  for different reasons: case 1 because the lock's stamped hash matches
  outright (cheapest path — no local-file read at all), case 5 because
  it differs but `acknowledged.skills` already names this exact hash —
  **recorded when the proposal was last shown, not when it was
  declined**; the pre-flight check never blocks waiting for an answer.
- `case-2-config-moved` and `case-3-anchor-moved` both have every other
  `requires_config` entry resolving — the discrimination between the two
  outcomes rests entirely on whether the *new or changed* entry itself
  resolves through the lookup chain, not on any claim about which input
  the hash change came from (the hash cannot say that on its own).
- `case-4-no-stamp` (no `reconciled:` block anywhere) and
  `case-6-skill-absent-from-stamp` (a `reconciled:` block exists but has
  never covered this particular skill) both land on `outcome:
  propose_sweep` — the same token, different trigger. Case 6 is the more
  common real-world shape: a project that reconciles regularly still
  has newly-configured skills show up unstamped between sweeps.
- No case exercises the `.apache-magpie.lock`-absent-and-nothing-local
  gate directly (that shape is silent by construction — the step skips
  itself before any read — and is covered by `setup`'s own
  `preflight-floor/case-6-unadopted`, which extracts this same section).
- The four `outcome` values are the whole vocabulary this check has:
  `silent`, `propose_config`, `propose_reanchor`, `propose_sweep`. No
  case exercises the install-method branch (marketplace floor vs.
  snapshot pin) because the reconciliation comparison is method-agnostic
  by design — see `docs/setup/agentic-overrides.md`'s *Reconciliation on
  framework upgrade* section.
- This suite does not model a marketplace-clone or `update_available`
  field: the pre-flight block never reads the marketplace clone — that
  comparison belongs to `/magpie-setup verify` alone (the block's own
  step 10 says so), and a sandboxed session could not read it here
  anyway.
