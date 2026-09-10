<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Repo-committed setup: default plugin set and per-skill first-run configuration](#repo-committed-setup-default-plugin-set-and-per-skill-first-run-configuration)
  - [Problem](#problem)
  - [Scope](#scope)
  - [Decisions](#decisions)
  - [Subsystem A — the optional committed default set](#subsystem-a--the-optional-committed-default-set)
    - [What setup offers](#what-setup-offers)
    - [Merge rules](#merge-rules)
    - [Harness reach](#harness-reach)
    - [Verify, uninstall, pre-flight](#verify-uninstall-pre-flight)
  - [Subsystem B — the per-skill first-run wizard](#subsystem-b--the-per-skill-first-run-wizard)
    - [Declaring what a skill needs](#declaring-what-a-skill-needs)
    - [The generated map and its drift hook](#the-generated-map-and-its-drift-hook)
    - [Firing the wizard](#firing-the-wizard)
    - [What the wizard does](#what-the-wizard-does)
  - [Subsystem C — documentation and screenshots](#subsystem-c--documentation-and-screenshots)
    - [Prose](#prose)
    - [The screenshot set: 14 to 25](#the-screenshot-set-14-to-25)
  - [Sequencing](#sequencing)
  - [Acceptance criteria](#acceptance-criteria)
  - [Alternatives considered](#alternatives-considered)
  - [Risks](#risks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Repo-committed setup: default plugin set and per-skill first-run configuration

| | |
|---|---|
| **Status** | Design approved; implementation not started |
| **Created** | 2026-09-10 |
| **Supersedes** | Nothing. Extends the marketplace install path added for 0.2.0 and the shared pre-flight from #1193 |
| **Spec surface** | [`tools/spec-loop/specs/adoption-and-setup.md`](../../tools/spec-loop/specs/adoption-and-setup.md) |

## Problem

The marketplace install became the default path in 0.2.0, and it commits
nothing to the repository — by design. `install.md` Step M5 says so in as many
words: no lock, no snapshot, no symlink, and `.apache-magpie-overrides/` merely
*offered* as an aside. Three consequences follow, and all three are the same
root cause:

1. **The default plugin set is documentation only.** The
   `extraKnownMarketplaces` + `enabledPlugins` block that lets a contributor
   arrive Magpie-ready exists as copy-paste JSON in
   [`docs/setup/marketplaces.md`](../setup/marketplaces.md). No code path
   writes it, so a maintainer either transcribes it by hand or never learns it
   exists.
2. **The config store is never created on the default path.** The 40 template
   files in `projects/_template/` are scaffolded by Step 9, which belongs to
   the snapshot path. A marketplace-installed skill still reads
   `.apache-magpie-overrides/` at run time, but nothing has put anything there.
3. **A skill discovers its missing configuration by acting on wrong
   assumptions.** The shared pre-flight added in #1193 answers "has this repo
   adopted Magpie at all"; it does not answer "does *this skill* have the
   configuration it needs". A skill whose config file is absent proceeds
   against defaults.

## Scope

Three subsystems, each independently shippable, delivered in order.

| | Delivers | Depends on |
|---|---|---|
| **A** | `setup` offers to write the committed default-set block and the config store | — |
| **B** | Per-skill first-run configuration wizard | the config store existing (A) |
| **C** | Documentation and screenshots for both | A settled; wizard shots need B |

**Out of scope.** The three outstanding placeholder captures
(`codex-install.png`, `vscode-install.png`, `gemini-install.png`) are unrelated
work. The eleven existing captures stay as they are. No change to the
pinned-snapshot install path, to lock-file handling, or to the secure-isolation
setup.

## Decisions

Five forks were settled during design; each shapes the rest of the document.

1. **The committed set is a fixed, framework-defined floor** — `magpie-setup`,
   `magpie-utilities`, `magpie-agent-guard` — not "whatever the maintainer
   installed". Maintainer-only families such as `magpie-security` stay a
   personal, user-scope install.
2. **Committing the block is optional and never a prerequisite.** Plugins work
   in the repo with or without it. It is a convenience for teammates.
3. **Setup offers it once, at Step M5, defaulting to no; staleness is reported
   by `verify` only.** The per-skill pre-flight never mentions the block.
4. **A skill declares only its *required* config in frontmatter**; the optional
   set is derived by tooling from the skill's own prose.
5. **The wizard auto-detects, asks only the gaps, writes, stages, and
   continues** into the skill the user actually invoked.

A consequence of decision 1 is worth stating plainly, because it removes work
the original request implied: **with a fixed floor there is nothing to re-sync
when a maintainer installs another family.** Installing `magpie-security` does
not change the floor. No per-install hook is needed — which is fortunate, since
#1193 established that no code runs on plugin install or upgrade on most
harnesses. The only drift that can occur is the framework's *own* floor
changing between releases, which is a periodic repair check.

## Subsystem A — the optional committed default set

### What setup offers

`skills/setup/install.md` Step M5 currently lists three things the marketplace
install "deliberately does not set up". Replace the second bullet with a single
opt-in offer covering both repo-side artefacts together, presented as one
question defaulting to **no**:

- **The default-set block** in the repo's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "apache-magpie": {
      "source": { "source": "github", "repo": "apache/magpie" }
    }
  },
  "enabledPlugins": {
    "magpie-setup@apache-magpie": true,
    "magpie-utilities@apache-magpie": true,
    "magpie-agent-guard@apache-magpie": true
  }
}
```

- **The config store** — `.apache-magpie-overrides/`, scaffolded from
  `projects/_template/` exactly as Step 9 does today, with the same exclusions
  (`.gitignore`, `pr-management-triage-ci-check-map.md`) and the same
  `project.md` pre-population from detected fit signals.

The offer must state, in the prompt itself, that the block is optional and that
the plugins work in this repo either way. A maintainer declining it is a
supported end state, not a partial install, and setup's recap must not describe
the result as incomplete.

Setup offers to `git add` both, and never commits.

### Merge rules

The repo's `.claude/settings.json` is not Magpie's file. This repository's own
carries `sandbox` and `permissions` blocks that must survive untouched, and an
adopter's will carry whatever they put there.

- Merge **only** the two keys. Every other key is preserved byte-for-byte.
- If `extraKnownMarketplaces` already defines `apache-magpie`, leave the
  existing definition alone — an adopter pinning `apache/magpie@0.2.0` has made
  a deliberate choice.
- If `enabledPlugins` exists, **add** missing floor members and **remove
  nothing**. A project that has enabled other plugins, Magpie's or anyone
  else's, keeps them.
- If the file does not exist, create it with those two keys and nothing else.
- If the file exists but is not valid JSON, stop and say so. Do not rewrite it.

### Harness reach

Only Claude Code can express this. #1193 verified the constraint against the
shipping clients: per-family plugins are Claude Code-only, so Codex could only
default-install all ten families, and Gemini has no workspace-extension
mechanism at all.

Setup must therefore make the offer **only** when the detected agent is Claude
Code, and on the others say plainly that the harness has no equivalent — rather
than writing a file that does nothing. This is the same detection Step M2
already performs.

### Verify, uninstall, pre-flight

- **`setup verify`** gains one check. Block absent → reported as fine, with one
  line noting it is available; this is not a fault and must not be counted as
  one. Block present but missing a floor member, or naming a plugin the current
  marketplace no longer ships → reported as drift with the repair offer.
- **`setup uninstall`** removes only the keys it added, leaving the rest of
  `.claude/settings.json` intact, and follows the existing convention of
  preserving `.apache-magpie-overrides/` by default.
- **The pre-flight is unchanged by this subsystem.** It must never treat a
  missing block as an unadopted repo — that would convert an optional
  convenience into a de-facto requirement, contradicting decision 2.

## Subsystem B — the per-skill first-run wizard

### Declaring what a skill needs

Each of the 65 skills that carry the pre-flight gains a `requires_config:`
frontmatter key — the short list of config files without which the skill
cannot do its job correctly, typically one to three entries:

```yaml
requires_config:
  - project.md
  - pr-management-config.md
```

Required means: absent, the skill would act on a guess. Everything else a skill
reads is optional and degrades, which is already how skills are written —
`pr-management-triage` states that missing config files "degrade to post the
comment, skip the label". That behaviour does not change.

### The generated map and its drift hook

The optional set is **derived, never hand-written**. New tooling greps each
skill for `<project-config>/*` references and emits
`tools/dev/skill-config-map.json`:

```json
{
  "pr-management-triage": {
    "required": ["project.md", "pr-management-config.md"],
    "optional": ["scope-labels.md", "pr-management-triage-comment-templates.md"]
  }
}
```

`optional` is the derived set minus `required`. A new
`tools/dev/check-skill-config-map.py --fix` regenerates it and a pre-commit
hook prevents drift, mirroring the `check-skill-preflight` pattern #1193
established. The check also validates that every file named in either list
exists in `projects/_template/`, so a skill cannot require config the framework
cannot scaffold.

### Firing the wizard

The shared pre-flight block (`tools/dev/preflight-block.md`, propagated into 65
of the 74 skills — the nine setup-family skills are excluded, since they are
what fixes the problem) gains **one** cheap check appended to its existing
three:

> Are this skill's `requires_config` files present in
> `.apache-magpie-overrides/`? If any are missing, hand off to
> `/magpie-setup configure <skill>`.

The same 65-skill exclusion set applies. This is the only pre-flight change in
this design; the block-staleness check from Subsystem A deliberately stays out
of it, so the pre-flight keeps its "silent on the happy path" property.

### What the wizard does

The wizard lives in **one place** — a new `configure` sub-action in the setup
skill, documented in a new `skills/setup/configure.md` — not propagated into 65
skill bodies. #1193 already paid the cost of propagating a 40-line block into
every skill; propagating a full interview would multiply it.

It reuses the three-beat pattern `install.md` Step 4b and Step 9 already
implement:

1. **Auto-detect first.** Read what the repo already reveals — the upstream
   remote, label taxonomy, milestones, release trains, existing CI checks.
2. **Batch the rest into one structured question.** Prefer the harness's
   structured-question tool. One question, not a per-field interrogation.
3. **Write and stage.** Copy the required templates from `projects/_template/`
   with detected and answered values filled in, `git add` them, and say what
   was written.

Then **return control so the invoking skill continues** into the work the user
asked for. The wizard is an interruption, not a destination.

Further contract points:

- **Optional config is never asked about.** It degrades as it does today.
- **Idempotence needs no state file.** The config file existing is the marker;
  a second invocation of the same skill sees the file and stays silent.
- **`configure` with no argument** walks every installed family, for a
  maintainer who would rather configure everything in one sitting.
- **`configure <skill>` is directly invocable**, so a maintainer can prepare
  config ahead of first use.
- The wizard writes only into `.apache-magpie-overrides/`. It never edits skill
  files, never commits, and never touches `.claude/settings.json` — that is
  Subsystem A's surface.

## Subsystem C — documentation and screenshots

### Prose

- **[`docs/quick-start.md`](../quick-start.md)** gains a subsection under
  Step 1 describing the optional committed default set, led by the
  optional-not-required framing, and a first-run wizard shot in *What happens
  next*.
- **[`docs/setup/marketplaces.md`](../setup/marketplaces.md)** — the
  `Claude Code: the default set` section gains a pointer that setup will write
  the block on request, with the same optionality framing, and finally carries
  `claude-code-default-install.png`.
- **Family READMEs** each gain a wizard screenshot beside their existing
  install shot.

### The screenshot set: 14 to 25

| Added | Count |
|---|---|
| `assets/quickstart/families/<family>-wizard.png` | 10 |
| `assets/quickstart/first-run-wizard.png` | 1 |
| `assets/quickstart/claude-code-default-install.png` (already documented as optional) | 1 |

`tools/dev/capture-screenshot.sh` gains `<family>-wizard` targets with their own
briefs. `tools/dev/check-quickstart-screenshots.py` extends to expect the new
paths, and its family-geometry consistency rule applies **per set** — wizard
shots are checked against each other, not against the install shots, since the
two sets are captured in different sittings. `assets/quickstart/README.md`
documents what each wizard shot must frame.

Wizard shots can only be captured once B ships.

## Sequencing

1. **A**, with its slice of C's prose. Self-contained: `install.md` Step M5,
   `verify.md`, `uninstall.md`, the two docs pages, and the spec-loop
   acceptance criteria.
2. **B**, as its own implementation plan. It touches 65 frontmatters, adds a
   generated map, a pre-commit hook, a setup sub-action, and one pre-flight
   line.
3. **C's screenshots**, after B is real.

## Acceptance criteria

These land in `tools/spec-loop/specs/adoption-and-setup.md`, which is how setup
behaviour is specified and validated in this repository — the spec-loop is the
test surface, not a unit-test suite.

- A marketplace install on Claude Code offers, once, to commit the default-set
  block and scaffold the config store; the offer defaults to no and states that
  both are optional.
- Declining leaves a working install, and neither setup's recap nor `verify`
  describes the result as incomplete.
- Writing the block preserves every other key in an existing
  `.claude/settings.json`, adds only missing floor members to an existing
  `enabledPlugins`, and removes nothing.
- The offer is not made on harnesses that cannot express it; those are told
  why.
- `verify` reports a stale committed block and repairs it on confirmation;
  an absent block is not a fault.
- A skill whose `requires_config` files are missing hands off to the wizard,
  which auto-detects, asks the gaps in one batched question, writes and stages
  the files, and returns control so the skill proceeds in the same turn.
- A skill whose required config is present runs with no additional output.
- `skill-config-map.json` regenerates identically from the skill sources; the
  hook fails on drift and on any config file absent from `projects/_template/`.

## Alternatives considered

- **Commit whatever the maintainer installed.** The literal reading of the
  original request. Rejected: it auto-enables maintainer-only families such as
  `magpie-security` for every contributor who trusts the repo.
- **Sync the block on every plugin install.** Not implementable — no code runs
  on plugin install or upgrade on most harnesses (#1193) — and made moot by the
  fixed floor.
- **Put the staleness check in the pre-flight.** Rejected: it would nag every
  invocation in repos that deliberately declined an optional feature.
- **Hand-written skill-to-config map.** Rejected: drifts the moment a
  `<project-config>` reference is added without updating it.
- **Propagate the wizard into every skill body.** Rejected on token cost and
  on the maintenance burden of 74 copies of one interview.
- **One wizard screenshot per skill (74).** Rejected: roughly 15 MB of PNG
  files, 74 manual re-captures whenever config questions change, and it would bury the
  two commands the quick start exists to show.

## Risks

- **The committed block changes what a contributor's agent loads on clone.**
  Mitigated by keeping it opt-in, restricting it to a three-plugin floor whose
  members are either inert (`magpie-setup`) or deny-only
  (`magpie-agent-guard`), and by Claude Code still letting a contributor
  disable any plugin enabled this way.
- **`requires_config` is a judgement call per skill.** Marking too much
  required turns a first run into an interrogation; too little defeats the
  purpose. The rule — required means the skill would otherwise act on a guess —
  needs applying skill by skill during B, not mechanically.
- **The wizard interrupts a skill mid-invocation.** Keeping it to one batched
  question and returning control in the same turn is what keeps it a wizard
  rather than a wall.
