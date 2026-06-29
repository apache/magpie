<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Adoption & setup
status: stable
kind: feature
mode: infra
source: >
  README.md § How adoption works / Adopting the framework / Maintenance.
  Implemented by the setup family (setup and siblings) and the
  snapshot + agentic-override model.
acceptance:
  - An adopter commits exactly one skill (setup); everything else
    is a gitignored snapshot plus committed override + lock files.
  - The committed lock pins install method + URL + ref so a fresh clone
    re-installs the same framework version.
  - Drift between the committed pin and the local install is detected and
    surfaced with an upgrade proposal.
---

# Adoption & setup

## What it does

Gets the framework into an adopter repo and keeps it current using a
**snapshot + agentic-override** model: one committed bootstrap skill, a
gitignored framework snapshot (a build artefact, never committed),
gitignored skill symlinks, and committed agent-readable override files.

## Where it lives

- Skill: `setup` (adopt, verify, upgrade, override).
- Skills: `setup-isolated-setup-install` / `-update` / `-verify` / `-doctor`
  (the sandbox harness; `-doctor` probes live restrictions — SSH agent /
  Yubikey reachability, localhost port binding, filesystem restrictions),
  `setup-override-upstream` (promote a stabilised override into a
  framework PR), `setup-shared-config-sync`.
- Skill: `setup-status` — renders a Markdown adoption dashboard: install
  method and pin, drift between local and committed locks, which skills
  are wired in the current repo.
- Docs: `docs/setup/` (install recipes, agentic-overrides contract,
  prerequisites).
- Lock files: `.apache-magpie.lock` (committed pin) and
  `.apache-magpie.local.lock` (gitignored, what this machine fetched).

## Behaviour & contract

- **One committed skill, no submodules, no vendored framework copies.**
  The snapshot lives in a gitignored `.apache-magpie/`.
- **`.agents/skills/` is the canonical home** for framework-skill
  symlinks (the path shared by Codex, Cursor, Gemini CLI, Copilot, …);
  every other agent dir (`.claude/skills/`, `.github/skills/`, holdouts)
  gets per-skill relay symlinks into it. This is uniform — there is no
  per-project skills-dir convention to detect.
- **Committed lock is the source of truth.** A fresh contributor runs
  `/magpie-setup` and re-installs to the project's pinned version.
- **Drift detection** at the top of every framework skill: if the
  gitignored local lock has drifted from the committed pin, the skill
  proposes `/magpie-setup upgrade`.
- **Overrides are agent-readable Markdown** under
  `.apache-magpie-overrides/`, consulted at runtime and merged before
  default behaviour ([pairing/correctability is the model]).
- **Overrides are additive, never authority inversion.** An override may
  supply adopter-specific process details, paths, labels, or wording, but
  it must not replace or weaken the framework's safety, confidentiality,
  privacy, or external-content-as-data baseline. If an override conflicts
  with those baseline rules, the framework rule wins and the conflict is
  surfaced.

## Out of scope

- The runtime behaviour of the modes themselves.
- Editing the adopter's `.claude/settings.json` beyond what the install
  recipe declares.

## Acceptance criteria

1. Adoption commits only the bootstrap skill + lock/override scaffold.
2. The committed lock re-installs the same version on a fresh clone.
3. Drift between local and committed locks is surfaced with an upgrade.
4. Override files can be discovered and surfaced to skills without
   editing upstream skill bodies, and override text cannot weaken the
   safety/confidentiality baseline.

## Validation

```bash
test -f docs/setup/README.md
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- `stable`; gaps appear as new agent targets to add to the registry
  ([`agents.md`](../../../skills/setup/agents.md)) or new override
  surfaces — recorded by the plan pass.
- **Override-file contract tests are missing.** The docs describe
  agentic overrides, but no smoke fixture proves that clean overrides are
  additive or that an override attempting to relax safety/confidentiality
  rules is flagged rather than applied.
