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
  - The default install a fresh adopter is offered is the marketplace
    plugin; the snapshot install below is proposed only where a marketplace
    cannot reach (no plugin mechanism, signed artefact needed, committed pin
    wanted).
  - Installing and adopting are separate acts and are never conflated.
    An install touches only the invoking user's agent and writes nothing
    to the repo; it never proposes a repo-side artefact, on any harness,
    and a declined-or-absent repo side is a finished install. Adoption is
    the maintainer act of committing the repo's recommended default
    plugin set and its overrides store for every contributor, reached
    only through `setup adopt` and only on an explicit decision.
  - A repo's committed default set is a floor, never a ceiling: it does
    not limit what a contributor may install, and using Magpie on a repo
    that has not adopted it is a first-class path, not a degraded one.
  - On the pinned-snapshot fallback, an adopter commits exactly one
    skill (setup); everything else is a gitignored snapshot plus
    committed override + lock files. On the default marketplace
    install, nothing is committed to the repo at all.
  - The committed lock records the install method, and what it records is
    method-dependent. On the three snapshot methods it is a pin — URL + ref —
    so a fresh clone re-installs the same framework version. On
    `method: marketplace` it is a floor, not a pin: URL, `min_version` and a
    plugin list, with no `ref`, and a fresh clone is brought up to that
    minimum and never held down to it.
  - Drift between the committed pin and the local install is detected and
    surfaced with an upgrade proposal.
  - A gitignored `.apache-magpie-local/` supplies per-person overrides that
    layer above the committed `.apache-magpie-overrides/`, cannot weaken the
    safety baseline, and can be ignored for a single run via a one-shot
    default switch.
  - A marketplace install never writes the committed default-set block or
    scaffolds `.apache-magpie-overrides/`, and never offers to: those are
    adoption, reached only through `setup adopt`. The install recap names
    `/magpie-setup adopt` once, and only when the user asks or says something
    that means it.
  - A marketplace install that wrote nothing to the repo is a complete
    install; neither the recap nor verify describes the result as incomplete
    or partial.
  - The default-set floor is seeded with three plugins and never grows
    automatically — not to match which other families this maintainer
    installed, and never to include a maintainer-only family. It is enlarged
    only when the maintainer explicitly asks, and every surface that reads
    it — the derived wiring, verify, uninstall, unadopt — reads the lock's
    `plugins` list in floor order rather than a fixed count.
  - Writing the committed default-set block touches only
    `extraKnownMarketplaces` and `enabledPlugins` in
    `.claude/settings.json`, preserves every other top-level key and an
    existing `apache-magpie` marketplace definition, adds only the floor
    members missing from an existing `enabledPlugins` and removes nothing,
    creates the file with just those two keys when it is absent, refuses to
    rewrite a settings file that does not parse, and stages only the file
    it wrote — never commits it.
  - verify reports an absent committed default-set block through the
    non-fault glyph with an empty `missing` list, reports every floor
    member present as current and equally non-faulting, reports
    some-but-not-all floor members present as stale, the one fault this
    check raises, naming the missing members in floor order with a repair
    offer, and gives an entry naming a plugin the marketplace no longer
    ships the same drift treatment.
  - uninstall removes only the floor entries named by the lock's `plugins`
    list from `enabledPlugins` and the `apache-magpie` entry from
    `extraKnownMarketplaces`, keeps every other plugin and marketplace entry
    untouched, drops either key left empty by the removal, and never deletes
    `.claude/settings.json` — nor `.apache-magpie.lock`, which only unadopt
    removes.
  - docs/quick-start.md and docs/setup/marketplace.md both state that the
    committed default-set block is optional and not a prerequisite to using
    the plugins in the repo.
---

# Adoption & setup

## What it does

Gets the framework in front of an adopter and keeps it current. The
**default install is the marketplace plugin**
([`marketplace-distribution.md`](marketplace-distribution.md)) — per machine,
nothing in the repo. This surface is the **fallback and the repo-side half**:
a **snapshot + agentic-override** model — one committed bootstrap skill, a
gitignored framework snapshot (a build artefact, never committed),
gitignored skill symlinks, and committed agent-readable override files —
for agents with no plugin mechanism, adopters who need the signed ASF source
artefact, and projects that want every contributor and CI job pinned to one
committed version with drift detection.

## Where it lives

- Skill: `setup` (install, adopt/unadopt, verify, upgrade, override).
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
- Lock files: `.apache-magpie.lock` (committed — a pin on the snapshot
  methods, a floor on `method: marketplace`) and
  `.apache-magpie.local.lock` (gitignored, what this machine fetched).

## Behaviour & contract

- **Marketplace first.** `setup install` with no `method:` proposes the
  marketplace install and prints the running agent's exact commands; it
  proposes the snapshot only for a stated reason (no plugin mechanism,
  signed artefact, committed pin, or the framework checkout itself). Both
  installs live on one machine at once is a supported *repo* state but a
  double-load for that machine — the skill surfaces it rather than stacking
  them silently.
- **One committed skill, no submodules, no vendored framework copies.**
  The snapshot lives in a gitignored `.apache-magpie/`.
- **`.agents/skills/` is the canonical home** for framework-skill
  symlinks (the path shared by Codex, Cursor, Gemini CLI, Copilot, …);
  every other agent dir (`.claude/skills/`, `.github/skills/`, holdouts)
  gets per-skill relay symlinks into it. This is uniform — there is no
  per-project skills-dir convention to detect.
- **Committed lock is the source of truth.** A fresh contributor runs
  `/magpie-setup` and re-installs to the project's pinned version on the
  snapshot methods, or is brought up to its floor on `method: marketplace`.
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
- **Personal, gitignored overrides** live under `.apache-magpie-local/`, a
  per-person sibling to the committed `.apache-magpie-overrides/` that is
  never committed. It is read at runtime under the same additive-only
  guardrail as any override: it may carry a person's paths, wording, or
  capability/MCP enablement (for example a release manager enabling a
  Policy MCP that other members leave off), but it cannot weaken the safety,
  confidentiality, or privacy baseline. Precedence, first hit wins:
  `.apache-magpie-local/` -> `.apache-magpie-overrides/` -> organization
  defaults -> framework default. Adoption scaffolds the overrides store; the
  `.gitignore` entry for the personal directory is the user's to add,
  wherever they prefer it, so the directory stays untracked. This is the surface that makes hybrid
  setups work: one person can run Magpie against a shared or non-adopting
  repo without committing anything or requiring teammates to opt in.
- **One-shot default run.** A per-invocation switch runs a skill against
  framework defaults for that session only, ignoring both
  `.apache-magpie-local/` and `.apache-magpie-overrides/`, without editing or
  removing either file. The safety baseline still applies.
- **Adoption records a floor, not a pin.** On the marketplace path,
  `adopt` writes `.apache-magpie.lock` with `method: marketplace`, a
  `min_version` equal to the version installed at adopt time, and a
  plugin list seeded with the framework's three. Both are minimums:
  contributors may run newer versions and more plugins, and nothing is
  ever downgraded, removed, or pinned. The derived
  `extraKnownMarketplaces` entry is written untagged.
- **The lock is harness-neutral; the wiring is not.** The lock is
  written on every client. `.claude/settings.json` is derived from it
  and written only where the harness can express it.
- **Every skill's pre-flight brings the machine up to the floor** and
  then stops for a restart, and does so without asking only when the
  lock's `url` is `apache/magpie`.
- **`upgrade` splits on adoption:** nothing repo-side when the project
  has not adopted; `min_version` raised — never lowered — and staged
  when it has.

## Out of scope

- The runtime behaviour of the modes themselves.
- Editing the adopter's `.claude/settings.json` beyond what the install
  recipe declares.

## Acceptance criteria

1. A fresh `setup install` proposes the marketplace path first, names the
   agent's commands, and reaches the snapshot flow only with a stated reason.
2. Adoption commits only the bootstrap skill + lock/override scaffold.
3. The committed lock re-installs the same version on a fresh clone on the
   snapshot methods, and on `method: marketplace` brings a fresh clone up to
   the recorded floor without capping it there.
4. Drift between local and committed locks is surfaced with an upgrade.
5. Override files can be discovered and surfaced to skills without
   editing upstream skill bodies, and override text cannot weaken the
   safety/confidentiality baseline.
6. A gitignored `.apache-magpie-local/` is read as a per-person override
   surface that layers above `.apache-magpie-overrides/` (personal-local ->
   committed -> organization -> framework default, first hit wins), under the
   same additive-only guardrail, and works on a repo that has not adopted
   Magpie once its `.gitignore` line is present.
7. A one-shot switch runs a skill against framework defaults for a single
   session, ignoring both override surfaces without deleting them, and the
   safety baseline still applies.
8. `adopt` on a marketplace install writes a `method: marketplace` lock
   carrying the installed version and the seeded floor, stages it, and
   commits nothing; the derived marketplace entry carries no version tag.
9. A pre-flight on a machine at or ahead of the floor prints nothing; one
   below it installs or updates only floor plugins, reports what ran, and
   stops for a restart without removing, downgrading or pinning anything.
10. A pre-flight whose lock names a `url` other than `apache/magpie` runs
    nothing and asks first.
11. Version comparison is PEP 440: `0.10.0` satisfies a `0.9.0` floor, and
    `0.2.0` satisfies a `0.2.0.dev202609110041` floor.
12. `upgrade` writes nothing to the repo when the project has not adopted,
    and raises — never lowers — `min_version` when it has.
13. `verify` reports a missing lock and an ahead-of-floor machine as not
    faults, and a shortfall as one.
14. `unadopt` removes the lock; `uninstall` leaves it; each says which.

## Validation

```bash
test -f docs/setup/README.md
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **Marketplace distribution is a sibling surface**, specified separately in
  [`marketplace-distribution.md`](marketplace-distribution.md). It is the
  *default* way an adopter takes the framework; the snapshot install described
  here is the fallback. The skills delivered are the same tree either way —
  only the namespace of their invocation differs.

- `stable`; gaps appear as new agent targets to add to the registry
  ([`agents.md`](../../../skills/setup/agents.md)) or new override
  surfaces — recorded by the plan pass.
- **Not yet built:** the `.apache-magpie-local/` personal override surface
  (acceptance 5) and the one-shot default-run switch (acceptance 6). Both are
  intended behaviour recorded here and tracked as work items
  `magpie-local-convention` and `override-bypass-one-shot` in the plan. The
  three hybrid-setup how-tos that build on the local surface are tracked
  alongside them.
