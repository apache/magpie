<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [RFC-AI-0007: Selective snapshot — fetch only the chosen skill families](#rfc-ai-0007-selective-snapshot--fetch-only-the-chosen-skill-families)
  - [Abstract](#abstract)
  - [Status of this document](#status-of-this-document)
  - [Motivation](#motivation)
  - [Proposal](#proposal)
    - [Fetch model — sparse checkout of a computed path set](#fetch-model--sparse-checkout-of-a-computed-path-set)
    - [Runtime dependencies vs documentation links](#runtime-dependencies-vs-documentation-links)
    - [Granularity — family, not skill](#granularity--family-not-skill)
    - [Lock format](#lock-format)
    - [`svn-zip` method](#svn-zip-method)
    - [`setup`-skill integration](#setup-skill-integration)
  - [Drawbacks](#drawbacks)
  - [Alternatives considered](#alternatives-considered)
  - [Out of scope](#out-of-scope)
  - [References](#references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# RFC-AI-0007: Selective snapshot — fetch only the chosen skill families

## Abstract

Today the [`setup`](../../skills/setup/SKILL.md) skill fetches the **whole**
`apache/magpie` framework into the gitignored `.apache-magpie/` snapshot —
all ten skill families, every tool, the full `docs/` tree, and the
`projects/` templates — even when the adopter opts into only one or two
families. This RFC proposes a **selective (family-scoped) snapshot**: fetch
only the chosen families' skills, the two always-on families, and the
**runtime closure** those skills execute against, using `git sparse-checkout`
with a partial clone. Documentation cross-links that are not runtime
dependencies resolve to the canonical `apache/magpie` URL rather than local
files. The committed lock records the chosen families so `upgrade` and
`verify` reproduce the same sparse set. No change to the symlink model, the
override model, or PRINCIPLES §13.

## Status of this document

**Proposed.** Design lands in two phases. **Phase A** — this RFC and the
selection/closure/lock-format definitions — is the review checkpoint.
**Phase B** — the `setup`-skill and `install-recipes.md` wiring
(`git sparse-checkout` recipes, the `families:` lock field, and the
`adopt`/`upgrade`/`verify` integration) plus a worked example — follows on
approval. This RFC changes only *how much* is fetched; the agent-marketplace
distribution (the plugin/extension trial channel) ships separately.

## Motivation

The snapshot is a build artefact, so its size is pure overhead for the
adopter: clone time, disk, and review surface for the `.gitignore` +
lock diff. An adopter that wants only `security` pulls the other nine
families, all of `docs/`, and every `tools/` bridge regardless. The
`skills/` tree alone is ~3 MB across 70 skills; `docs/` and `tools/`
multiply that. As the framework grows, the whole-repo fetch scales with the
framework, not with what the adopter uses.

The 0.2.0 marketplace path already offers a lean *trial* channel. Full
adoption should be lean too: fetch what you opted into, plus exactly what
those skills need to run.

## Proposal

### Fetch model — sparse checkout of a computed path set

For the `git-tag` and `git-branch` install methods, replace the full
extract with a cone-mode `git sparse-checkout` over a partial clone:

```bash
git clone --filter=blob:none --no-checkout --depth 1 <ref> .apache-magpie
git -C .apache-magpie sparse-checkout set --cone <path> <path> ...
git -C .apache-magpie checkout
```

The path set is the union of:

1. **Chosen families' skills** — `skills/<skill>` for each skill whose
   `family:` frontmatter is an opted-in family.
2. **Always-on families** — `setup` and `utilities` skills, always fetched.
3. **Runtime closure** — the files the fetched skills *execute against*:
   `AGENTS.md`, `PRINCIPLES.md`, `projects/_template/`, and each
   `tools/<tool>` a fetched skill invokes. Opted-in MCP servers
   (`ponymail`, `apache-projects`, `gmail-plaintext`) are fetched when
   selected.

### Runtime dependencies vs documentation links

A `SKILL.md` reference is a **runtime dependency** only when the skill reads
or executes the target at run time (a `tools/<x>` CLI, a
`projects/_template/<x>` config, `AGENTS.md`/`PRINCIPLES.md` conventions).
These are fetched. All other `../../…` references — the ~319 `docs/…` and
prose `README`/`MISSION` links — are **documentation links**; they are
rewritten to absolute `https://github.com/apache/magpie/blob/<ref>/…` URLs
so they resolve without a local copy. The rewrite is deterministic (the
snapshot knows its own `<ref>`) and applied at fetch time.

The per-family runtime closure is **declared, not guessed**: each skill
gains an optional `runtime_deps:` frontmatter list (tool + template paths it
executes). `skill-and-tool-validator` enforces that every non-`docs`
`../../` path a skill references at runtime appears in `runtime_deps` — so
the closure cannot silently drift out of date.

### Granularity — family, not skill

Selection is per **family**, matching the existing opt-in prompt. Per-skill
selection was rejected (see *Alternatives*): the closure computation is far
more fragile and the saving over per-family is marginal, because a family's
skills share most of their runtime closure.

### Lock format

`.apache-magpie.lock` gains a `families:` list recording the opted-in
families. `upgrade` re-derives the identical sparse path set from
`families:` + the always-on set + the declared closure; `verify` checks the
on-disk sparse set matches. Adding a family later is an `upgrade` that
extends the sparse-checkout path set (no re-clone).

### `svn-zip` method

The `svn-zip` recipe downloads a **single signed zip** of the whole source
release, which cannot be sparse-fetched. Two options, decided in Phase A:
(a) keep `svn-zip` a whole-release fetch (sparse applies to the git methods
only), documenting the trade-off; or (b) add an `svn checkout --depth empty`
+ per-path `svn up` variant against `dist`/repo. Recommendation: **(a)** for
Phase B — `svn-zip` adopters are the "frozen, signed, whole-release"
audience for whom completeness matters most; revisit (b) only on demand.

### `setup`-skill integration

`adopt` already asks which families to opt into *before* wiring symlinks; it
will ask *before* the fetch and drive the sparse checkout. `upgrade`
re-derives the sparse set from the lock. `verify` adds a check that the
sparse set on disk equals the lock-derived set. The symlink and override
steps are unchanged — they already operate per selected skill.

## Drawbacks

- **Documentation links go remote.** Rewritten `docs/…` links need network
  to open and pin to `<ref>`; an offline adopter loses local doc browsing.
  Mitigated: runtime never depends on them.
- **`svn-zip` stays whole.** The signed-zip method does not benefit under
  recommendation (a).
- **A declared closure to maintain.** `runtime_deps` must be accurate or a
  skill breaks on a lean install; the validator enforces it, adding a small
  authoring cost.
- **Adding a family is a fetch, not free.** Opting into a new family later
  requires an `upgrade` to extend the checkout.

## Alternatives considered

- **Per-skill granularity.** Finer, but the closure is fragile and the
  saving over per-family is marginal (shared closure). Rejected.
- **Everything-referenced closure.** Fetch the transitive closure of *all*
  referenced files. Safe but barely smaller than the whole repo, since
  `docs/` is large and densely cross-linked. Rejected.
- **Marketplace-only.** The 0.2.0 plugin path is a trial channel; it does
  not set up the snapshot/override/drift machinery that full adoption needs.
  Complementary, not a replacement.
- **Status quo (whole-repo snapshot).** Simple and offline-complete, but
  scales with the framework rather than with adopter usage. This RFC exists
  to fix that.

## Out of scope

- Marketplace/plugin distribution (shipped separately for 0.2.0).
- Any change to the symlink relay model, the agentic-override protocol, or
  PRINCIPLES §13.
- `svn-zip` sparse fetch (deferred unless demanded).
- Selective fetch of *external* skill sources
  ([RFC-AI-0006](RFC-AI-0006.md)) — a follow-up once this lands for the
  first-party snapshot.

## References

- [`skills/setup/SKILL.md`](../../skills/setup/SKILL.md),
  [`install.md`](../../skills/setup/install.md),
  [`upgrade.md`](../../skills/setup/upgrade.md) — the flow this RFC rewires.
- [`docs/setup/install-recipes.md`](../setup/install-recipes.md) — the
  fetch recipes that gain the sparse variant.
- [`PRINCIPLES.md` §13](../../PRINCIPLES.md) — the snapshot-plus-override
  principle, unchanged by this RFC.
- [RFC-AI-0006](RFC-AI-0006.md) — the external-source model this
  generalizes toward.
- Agent-marketplace distribution (plugin/extension manifests) — the
  complementary trial channel, shipping separately.
- [git sparse-checkout](https://git-scm.com/docs/git-sparse-checkout) and
  [partial clone](https://git-scm.com/docs/partial-clone) — the mechanism.
