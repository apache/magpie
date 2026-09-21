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
  - [When nothing is stamped](#when-nothing-is-stamped)
  - [The three numbers, and where each comes from](#the-three-numbers-and-where-each-comes-from)
  - [Who writes the stamp](#who-writes-the-stamp)
  - [Suggesting `verify`](#suggesting-verify)
  - [Where the build departed from the design](#where-the-build-departed-from-the-design)
  - [Alternatives considered](#alternatives-considered)
  - [Risks](#risks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Reconciliation tracking for marketplace installs

| | |
|---|---|
| **Status** | Built. [Where the build departed from the design](#where-the-build-departed-from-the-design) records seven places it did. |
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
5. **Absence is a sweep, not silence.** No stamp means the project has never
   been reconciled, which is resolved once — by a full sweep with a
   best-effort baseline — rather than carried indefinitely.
6. **A declined prompt stays declined** until the fingerprint moves again.
7. **A dev build is a version like any other.** Nothing strips `.devN`,
   rounds to the release segment, or treats a dev-to-dev move as a
   non-event. Running a dev version is accepting that it changes often;
   the design owes that user accurate comparisons, not protection from
   their own choice.

## The stamp

One block, written only by `setup`:

```yaml
reconciled:
  version: 0.2.0.dev202609211315     # what setup last ran against
  at:      2026-09-21
  skills:
    magpie-pr-management-code-review:  sha256:9f1c4e…
    magpie-security-issue-triage:      sha256:4ab70d…
```

Keyed by the skill's frontmatter `name:`, not `<plugin>/<skill>` — the shape
above was the design's original guess, and the build revised it (see
[Where the build departed from the design](#where-the-build-departed-from-the-design)).

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

**Anchors are not confined to `SKILL.md`.** A multi-file skill (`setup`,
`pr-management-triage`, `security-issue-sync`, …) keeps steps and
golden rules in sibling detail files, not only in `SKILL.md` itself, and an
override can anchor to a heading there just as easily. The shipped
fingerprint spans the skill's whole directory — `SKILL.md` plus every `*.md`
file directly inside it, no recursion into subdirectories such as `guards/`
or `fixtures/` — and tags each anchor with the file it came from, so a
heading moving between two files in that set changes the hash even though
the heading text itself did not. This widened after the first cut shipped
scoped to `SKILL.md` alone; see
[Where the build departed from the design](#where-the-build-departed-from-the-design).
`requires_config:` still comes from `SKILL.md`'s frontmatter alone — detail
files carry no frontmatter of their own.

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

Equal → silent. Different → say which of the two inputs moved and propose
the matching fix: `/magpie-setup config` for a `requires_config` change,
override re-anchoring for an anchor change. Missing → the sweep below.

## When nothing is stamped

Every project adopted before this ships has no stamp, and so does every
project whose configuration predates it. That state is resolved once, by
proposing a **full sweep reconciliation** — not carried as a permanent
blind spot.

**The sweep needs no baseline, because it validates the present rather than
a delta.** With no stamp there is nothing to diff against, but the useful
questions do not require one:

- does every override file's anchor still resolve in the skill it targets?
- does every `requires_config` entry of every configured skill resolve
  through the lookup chain?

Both are answered from the current tree alone. A missing baseline costs
precision in the *report*, not the check.

**The baseline is a best guess, used only for wording.** In order: the
lock's `min_version`; else the date of the last commit touching
`.apache-magpie.lock` or `.apache-magpie-overrides/`, mapped to a version
through the marketplace clone's own git history; else the mtimes of
`.apache-magpie-local/`; else nothing, and the report says so rather than
inventing a number. It is phrased as an estimate — *"your configuration
looks like it was written around 0.1.x"* — because that is what it is.

**Sandboxed sessions sweep what they can reach and say what they could
not.** Reading another skill's `SKILL.md` to resolve its anchors needs the
plugin cache, which the sandbox denies. There the sweep covers the
repository side — which overrides exist, which skills they name, whether
the config files they need are present — reports that the anchor
resolution could not be checked here, and names `/magpie-setup reconcile`
outside the sandbox as the way to finish it. A partial answer with its
limits stated beats silence.

**It is proposed once, and a decline is remembered.** On confirmation the
sweep runs, re-anchors what moved, and writes the stamp — after which the
cheap per-skill comparison takes over and this path never runs again for
that project. On a decline, `acknowledged` is written to local state and
the proposal does not return until the configuration or the plugin set
changes. This is a one-time cost per project, not a recurring prompt.

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

The last row is best-effort, and the pre-flight check never performs it at
all. The design's first cut planned to mention a newer version only when the
reconciliation check was already speaking — a piggyback on the free
comparison. The build dropped that: the pre-flight block never reads the
marketplace clone, on any branch, because a sandboxed session cannot read it
either, and a comparison that silently never fires on the machines that run
pre-flight most often is worse than one that plainly does not live there.
`verify` owns this comparison exclusively — see
[Who writes the stamp](#who-writes-the-stamp) and
[Where the build departed from the design](#where-the-build-departed-from-the-design).

All three are compared as PEP 440, dev segment included — the rule the
current pre-flight block already states, where `0.2.0` is newer than
`0.2.0.dev202609110041`. A newer dev build *is* a newer version:
`0.2.0.dev202609211315` over `0.2.0.dev202609180100` is an available update
and is reported as one by `verify`, and the stamp records whatever version
`setup` actually ran against, dev or not, verbatim.

**This is a different axis from the reconciliation gate, and the two must
not be confused.** Version comparison answers *is there something newer*,
and dev builds count. The fingerprint answers *does it affect this
project's configuration*, and gates the **prompt**. A newer dev build with
no surface change is an update that `verify` will report and that no
pre-flight will interrupt anyone about — which is the correct pair of
answers, not a suppression of the first.

## Who writes the stamp

| Action | Does |
|---|---|
| `setup config` | **Not adopted** — writes the skill's entry into the local `skills` map, whether or not this run had to do anything for it. **Already adopted** — never touches the committed lock's `skills` map; only for a skill whose missing configuration this run actually wrote does it record the per-machine `acknowledged.skills` fact, so an unattended pre-flight-triggered run never stages a committed-file write. |
| `setup adopt` | writes the block into the committed lock for every skill its own configuration/override scope covers, and first migrates any pre-existing local stamp's `skills` map into the lock so the same skill is never named in both stores at once. |
| `setup upgrade` | reconciles the narrower slice `.apache-magpie-overrides/` names (not every configured skill), and writes the stamp only for an override that passes its target-skill, anchor, and `requires_config` checks — never a false clean. |
| `setup reconcile` (new) | the project-wide pass: walks every configured skill and override, re-anchors what moved, rewrites the block. This is what the shared pre-flight check proposes when a skill is named in neither store at all. |
| `setup verify` | reports the same sweep read-only, and is the one surface that also compares against the marketplace clone — the pre-flight check never does, on any branch. |

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
  precedent of the shared block's step 9 (the vetted-ops-read proposal):
  an end-of-run item that lives in the pre-flight block only because that
  block is the one thing every skill carries. Interrupting the work the
  user asked for to propose a health check is the wrong trade.
- **Shown at most once per interval, whether or not it is taken** —
  displaying it writes `verify_suggested_at`, re-arming the clock. Someone
  who ignores it sees it twenty-six times a year rather than twenty-six
  times a day.
- **Configurable** through the existing project → organization → framework
  chain, `setup.verify_interval_days`, default 14, `0` disabling it.

The line says why it is worth taking: *"`/magpie-setup verify` has not run in
three weeks — it also checks whether newer plugin versions are available,
which a sandboxed session cannot."*

## Where the build departed from the design

Several places, all deliberate, found in review during the implementing
plan rather than anticipated here.

**The stamp is keyed by the skill's frontmatter `name:`, not
`<plugin>/<skill>`.** This document's own first draft of the `reconciled:`
example used the plugin-qualified form (`magpie-pr-management/code-review`).
That key is not derivable on a snapshot install, which wires
`skills/<name>/` with no plugin component at all — exactly the install shape
a method-agnostic stamp has to work under. `name:` is already in the running
skill's own context, unique across the framework, and identical under every
install method.

**The fingerprint's scope widened from `SKILL.md` alone to `SKILL.md` plus
its sibling detail files.** The first cut hashed only a skill's own
`SKILL.md`. Review found 18 of the framework's ~75 skills keep steps and
golden rules in sibling `*.md` files instead — `setup`, `pr-management-
triage`, and `pr-management-code-review` among the largest — so an override
anchored to a heading in one of those files could drift with the check
staying silent. The generator, `reconcile`'s anchor check, and `upgrade`'s
override walk all now read the whole directory and tag each anchor with the
file it came from.

**The pre-flight block never reads the marketplace clone, on any branch.**
The design's first cut mentioned a newer version only when the
reconciliation check was already speaking, piggybacking on a read the check
was doing anyway. That read does not exist in the shipped check: the
per-skill comparison is entirely local (this skill's own hash against the
stamp), so there was nothing to piggyback on, and reading the clone would
have added exactly the sandbox-denied, unsandboxed-only cost the design
otherwise avoids. `verify` is the one surface that performs it.

**The stamp applies to every adopted or configured project, any install
method — not a marketplace-only gap-closer.** The motivating gap is
marketplace-specific, but the mechanism (a skill's own hash against a
stamped one) is not, and a snapshot-install branch in every consumer would
have bought nothing: a snapshot adopter simply carries a stamp that stays
silent, which is inert rather than harmful.

**A per-skill pre-flight finding is recorded when shown, not when
declined; a `reconcile` or `upgrade` finding still records on decline.**
The design's "Why a decline is remembered" section assumed one rule for
both surfaces. The shared pre-flight check never blocks for an answer — it
prints its proposal and continues into the work the user asked for in the
same turn — so there is no decline event to hook, and recording on show is
the only way the suppression can fire at all. `reconcile` and `upgrade`
genuinely block for a real per-item and whole-sweep confirmation, so their
decline event is real and is what they record against.

**`config` never writes the committed lock's `skills` map, on any branch.**
The design's summary table said `config` "writes the entries for the skills
it configures", without saying into which store on an adopted project.
Because the shared pre-flight block auto-runs `config` unattended, an
adopted project's committed lock could otherwise be staged for a `git add`
from a worktree pre-flight never meant to touch it. `config` writes to the
committed lock never; on an adopted project it writes only the always-local
`acknowledged.skills` fact, and only for a skill whose missing
configuration this run actually filled in.

**The pre-flight comparison is conditional on the floor check's own
outcome, not unconditional.** [The pre-flight check](#the-pre-flight-check)
above describes the fingerprint comparison as three free steps that
always run. The shipped check adds one more condition, found only once
an agent had to decide what to say when both the floor check and the
reconciliation check have something to report in the same breath: it
is skipped — along with the reconciliation proposal it would otherwise
make — when the floor check is itself stopping the session for a
restart (a plugin installed or updated, commands only printed because
there is no CLI, or nothing run because of an untrusted marketplace
`url`). A reconciliation proposal stacked onto a restart notice is
exactly the prompt pile-up this design set out to avoid elsewhere, and
the session is about to restart anyway, so the check costs nothing to
repeat on the next invocation. An *unreadable* plugin manager is not
such a stop — it says nothing about the project's own configuration,
and everything this check needs (the skill's own `surface_hash`, the
lock, the local file) is readable whether or not the plugin manager
is — so the check still runs through that case, exactly as designed.

## Alternatives considered

**Prompt on any version delta, not on surface change.** Simplest, and what
the literal description of the problem suggests: installed newer than
reconciled → propose reconciling. Rejected for what it does to the
*prompt*, not for what it says about the versions: this repository ships
`0.2.0.devYYYYMMDDHHMM` most days, so anyone tracking the tip would be
interrupted after every update, almost always about skills they do not
configure. A feature that cries wolf daily is mentally uninstalled in a
week. The delta is still real and still reported — by `verify`, which
answers *what is newer*, rather than by a prompt that claims *you need to
act*.

**Ignore the `.devN` suffix and react only to release-segment bumps.** Quiet
by construction and needs no fingerprint. Rejected twice over. It would stay
silent through exactly the events the check exists to catch, because this
project ships real behaviour in dev builds — the renamed step that strands
an override arrives in one. And it would lie to the dev-build user about
what they are running: choosing a dev version is choosing frequent change,
and the design owes that user an honest comparison rather than a rounded
one.

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
paid for on every run whether or not anything changed. The sweep runs once,
when there is no stamp, and then never again for that project.

**Treat a missing stamp as silence.** The first draft of this design did:
nothing is known to have drifted, only that nothing is known, so say
nothing. Rejected because it makes the blind spot permanent — every project
adopted before this ships would keep exactly the gap the design exists to
close, and the one population certain to need reconciling is the one that
would never be offered it. Sweeping once is a bounded cost that ends with a
stamp; silence has no end.

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
- **The per-skill check is not free at the token level, even though it is
  free at the read level.** The rule text the shared pre-flight block carries
  for it is roughly +1,100 tokens (measured, ~+34% on the smallest skills) on
  every invocation of every non-`setup` skill in every adopting project — an
  accepted, ongoing cost, not a rounding error. The one real lever — moving
  the rule text behind a pointer into `locks.md` — was rejected: that file
  lives in the framework snapshot or the plugin cache, which a sandboxed
  session cannot read, and would silently disable the check on exactly the
  setups this design was written for. What is left in the block is rules,
  not prose; trimming further is the maintainer's call, made explicitly
  rather than by omission.
- **`verify` is the only surface that can compare against the marketplace
  clone**, because it is the only one run deliberately and unsandboxed often
  enough to read it. A permanently sandboxed user learns about a newer
  plugin version only when they run `verify` — never from the pre-flight
  block, on any branch — which is a real gap for that population, accepted
  rather than closed (see [The three numbers](#the-three-numbers-and-where-each-comes-from)).
- **The widened fingerprint (`SKILL.md` plus sibling detail files) still
  stops at the skill's own directory.** An override anchored to a heading in
  a cross-referenced file outside that directory — a shared doc under
  `docs/`, a tool adapter's `operations.md` — is not covered and can drift
  silently. No skill does this as of this writing; it is a boundary to watch
  for, not a known gap today.
