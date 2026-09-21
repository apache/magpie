<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Reconciliation tracking for marketplace installs](#reconciliation-tracking-for-marketplace-installs)
  - [What is wrong](#what-is-wrong)
  - [Decisions](#decisions)
  - [The stamp](#the-stamp)
  - [What the fingerprint covers](#what-the-fingerprint-covers)
  - [The pre-flight check](#the-pre-flight-check)
  - [The three numbers, and where each comes from](#the-three-numbers-and-where-each-comes-from)
  - [Who writes the stamp](#who-writes-the-stamp)
  - [Suggesting `verify`](#suggesting-verify)
  - [Alternatives considered](#alternatives-considered)
  - [Risks](#risks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Reconciliation tracking for marketplace installs

| | |
|---|---|
| **Status** | Proposed. Nothing below is built yet. |
| **Scope** | The `setup` family, the shared pre-flight block, and one generated frontmatter field on every skill. |

## What is wrong

A marketplace install has no memory of what it was last set up against.

The snapshot methods do. `.apache-magpie.lock` pins a version,
`.apache-magpie.local.lock` fingerprints what this machine fetched, the two
are compared at the top of every skill run, and `/magpie-setup upgrade`
walks every override file and flags the ones whose target skill vanished or
whose anchors moved — the flow
[`docs/setup/agentic-overrides.md`](../setup/agentic-overrides.md#reconciliation-on-framework-upgrade)
calls *reconciliation on framework upgrade*.

The marketplace method has none of it, by design:
[`locks.md`](../../plugins/magpie-setup/skills/setup/locks.md) says a
marketplace install has no local lock "because the agent's plugin manager
already knows what is installed". That is true of the *installed version*
and false of everything else. The plugin manager does not know which version
the project's configuration was written against, so nothing notices when a
plugin moves underneath a configuration that was reconciled against an older
build. An override anchored to a step heading that has since been renamed
keeps being applied, partially and silently, until someone reads the skill
and works out why it no longer does what it says.

The gap widens as the marketplace becomes the default install. Plugins
update on the user's own `/plugin update`, on their own schedule, with no
relationship to when the project was configured — and the configuration is
the thing that goes stale.

## Decisions

1. **The stamp records what was reconciled, not merely when.** A version
   alone cannot answer "does this matter to me?", because this repository
   ships a dev build most days. The stamp carries a per-skill fingerprint of
   the surface the project actually resolves, so the check can name what
   changed or stay quiet.
2. **The fingerprint is shipped, never computed at runtime.** A prek hook
   writes `surface_hash:` into each skill's frontmatter. An agent cannot
   hash prose from its context reliably, and in a sandboxed session it
   cannot read the plugin files to hash them either.
3. **Adopted projects commit the stamp; unadopted ones keep it local.**
   Committed configuration is a shared fact, so its staleness is shared.
4. **The check a skill performs on itself is the always-on one.** It costs
   nothing and works inside the sandbox. The project-wide sweep lives in
   `verify` and a new `reconcile`.
5. **Absence is silence.** No stamp entry means "unknown", never "stale".
6. **A declined prompt stays declined** until the fingerprint moves again.

## The stamp

One block, written only by `setup`:

```yaml
reconciled:
  version: 0.2.0.dev202609211315     # what setup last ran against
  at:      2026-09-21
  skills:
    magpie-pr-management/code-review:  sha256:9f1c4e…
    magpie-security/issue-triage:      sha256:4ab70d…
```

It lists only the skills the project actually configures or overrides — a
handful, not the ~75 that exist.

**Adopted** → the block goes in `.apache-magpie.lock`, beside the floor it
already records. Pre-flight opens that file as its first step, so reading
the stamp costs no extra file access on any skill run, and `setup` already
owns the file exclusively. The lock thereby states two things rather than
one — what the project expects, and what state its configuration is in — and
[`locks.md`](../../plugins/magpie-setup/skills/setup/locks.md) has to say so
plainly.

**Configured but not adopted** → the identical block in
`.apache-magpie-local/reconciled.json`, beside the personal configuration it
describes.

**Neither** → no stamp. There is no committed or personal configuration to
go stale, so there is nothing to reconcile.

## What the fingerprint covers

Two inputs, because they are what reconciliation is about:

- the skill's `requires_config:` list — a change means the project may now
  need a configuration value it does not have;
- the skill's structural anchors — step headings and golden-rule names, the
  things an override file anchors to, and whose movement
  `agentic-overrides.md` already defines as a ⚠ to re-anchor.

Deliberately **not** the file's content. A typo fix, a reworded paragraph or
a new cross-reference must not move the hash; a renamed step must. Hashing
the whole file would reproduce the "any version delta" behaviour this design
exists to avoid, one prompt per dev build, none of them actionable.

A prek hook generates the value and CI enforces it, exactly as
`skill-token-count` maintains the measured figures in
[`docs/mode-economics.md`](../mode-economics.md). It is generated state in a
hand-written file, and like every other such field it is never hand-edited.

## The pre-flight check

Three steps added to [`tools/dev/preflight-block.md`](../../tools/dev/preflight-block.md),
all of them free:

1. read this skill's own `surface_hash` from its own frontmatter — already
   in context, no read;
2. read this skill's entry from the stamp — the lock is already open;
3. compare.

Equal → silent. Missing → silent. Different → say which of the two inputs
moved and propose the matching fix: `/magpie-setup config` for a
`requires_config` change, override re-anchoring for an anchor change.

**Why a missing entry is silent.** Every project adopted before this ships
has no stamp. Treating that as staleness would greet each of them with a
prompt whose question they cannot answer — nothing is known to have drifted,
only that nothing is known. The sweep in `verify` reports it; the next
`config` or `adopt` writes it.

**Why a decline is remembered.** The prompt is worth showing once per change.
Showing it on every invocation until acted on is precisely the failure the
prompt-fatigue principle ([apache/magpie#1291](https://github.com/apache/magpie/pull/1291))
exists to forbid. A decline writes `acknowledged: <hash>` into the *local*
state — never the committed lock, because declining is one person's call on
one machine — and suppresses the prompt until the hash moves again.

## The three numbers, and where each comes from

| Number | Source | Readable in a sandboxed session |
|---|---|---|
| last reconciled | the stamp | yes — it is in the repository |
| installed | the running skill's own base directory path | yes — the agent is handed it |
| latest available | `~/.claude/plugins/marketplaces/apache-magpie` | **no** — the sandbox denies the plugin cache |

The middle row is why the check is free. Every plugin skill is invoked with a
base directory of the form
`~/.claude/plugins/cache/apache-magpie/<plugin>/<version>/skills/<name>`; the
installed version is in the path, with no CLI call and no file read. This
matters beyond economy: inside the sandbox `claude plugin list --json`
returns `[]`, because the plugin cache is read-denied, and a check built on
that call would read "nothing installed" — which today's pre-flight step 3
would act on by proposing to install the entire floor. That is a defect in
the current block and is fixed alongside this work: an unreadable plugin
manager is *unknown*, never *absent*.

The last row is best-effort. Where the clone is readable and a newer version
exists, the fact is mentioned **only if the reconciliation check is already
speaking**; there is no standalone "an update is available" line. Where it is
unreadable, nothing is said at all.

## Who writes the stamp

| Action | Does |
|---|---|
| `setup config` | writes the entries for the skills it configures |
| `setup adopt` | writes the block into the committed lock |
| `setup reconcile` (new) | the project-wide pass: walks every configured skill and override, re-anchors what moved, rewrites the block |
| `setup verify` | reports the same sweep read-only, and is the one surface that also compares against the marketplace clone |

## Suggesting `verify`

`verify` is the only place the latest-version comparison can happen for a
sandboxed user, and it is the only whole-project answer. It therefore needs
to be suggested, and suggested rarely.

- **Stored locally, never committed** — `verified_at` lives in
  `.apache-magpie-local/reconciled.json` even for an adopted project, where
  the rest of the stamp is committed. Running `verify` is a per-machine act,
  and a committed timestamp would dirty the working tree every fortnight for
  every contributor, turning a health check into commit noise.
- **Counted from the last thing that inspected the setup** — `verified_at`
  if present, else the stamp's `at:`, so a project configured yesterday is
  not told to verify today.
- **Surfaced at the end of the run, not in pre-flight**, following the
  precedent of the shared block's step 8: an end-of-run item that lives in
  the pre-flight block only because that block is the one thing every skill
  carries. Interrupting the work the user asked for to propose a health
  check is the wrong trade.
- **Shown at most once per interval, whether or not it is taken** —
  displaying it writes `verify_suggested_at`, re-arming the clock. Someone
  who ignores it sees it twenty-six times a year rather than twenty-six
  times a day.
- **Configurable** through the existing project → organization → framework
  chain, `setup.verify_interval_days`, default 14, `0` disabling it.

The line says why it is worth taking: *"`/magpie-setup verify` has not run in
three weeks — it also checks whether newer plugin versions are available,
which a sandboxed session cannot."*

## Alternatives considered

**Compare versions, not surfaces.** Simplest, and what the literal
description of the problem suggests: installed newer than reconciled →
propose. Rejected because this repository ships `0.2.0.devYYYYMMDDHHMM`
most days, so anyone tracking the tip would be prompted after every update,
almost always about changes to skills they do not use. A feature that cries
wolf daily is uninstalled mentally in a week.

**Ignore the `.devN` suffix and react only to release-segment bumps.** Quiet
by construction and needs no fingerprint. Rejected because this project
ships real behaviour in dev builds — the renamed step that strands an
override arrives in one — so the check would stay silent through exactly the
events it exists to catch.

**Diff the two plugin trees at check time.** Precise, and needs no shipped
hash. Rejected because the old tree is gone: the plugin manager replaces it
on update, so the comparison would need a git fetch of the marketplace and a
tree diff on a skill invocation — network and seconds, in a step that must
cost neither.

**Keep the stamp in `~/.config/apache-magpie/`, keyed by project path.** One
file per machine, works for unadopted projects. Rejected on two counts: it
decouples the stamp from the configuration it describes, so deleting the
config leaves the stamp behind; and the sandbox denies that directory, so a
sandboxed session could not read its own stamp — losing the property that
makes the whole check viable.

**Put the stamp in `.claude/settings.local.json`.** It is already gitignored
and already written by the framework. Rejected: it belongs to the harness,
the framework's own deny rules guard it, and framework state in a harness
file mixes two owners in one place.

**Sweep the whole project on every pre-flight.** One run would report
everything stale at once. Rejected because it must read every plugin
manifest and override on every skill invocation — denied in the sandbox, and
paid for on every run whether or not anything changed.

## Risks

- **A generated frontmatter field on ~75 skills is a large mechanical diff.**
  It lands as its own commit inside the implementing PR, so the behavioural
  change stays readable in review.
- **The anchor set is a judgement call.** Too broad and the hash moves on
  cosmetic edits, reintroducing the noise; too narrow and a real re-anchoring
  need slips through. The hook's definition of an anchor is the thing to get
  right, and the thing to revisit if prompts turn out to be unactionable.
- **The stamp can lie after a hand-edit.** Nothing stops someone editing
  `.apache-magpie.lock` by hand, as nothing stops it today. `verify` is the
  detector.
- **Version in the base path is a harness detail.** It holds for Claude Code
  plugin installs today. Where a harness does not encode the version in the
  path, the check degrades to unknown-and-silent rather than breaking.
