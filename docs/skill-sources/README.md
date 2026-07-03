<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Trusted external skill sources](#trusted-external-skill-sources)
  - [The trust model — three layers](#the-trust-model--three-layers)
  - [Source descriptor](#source-descriptor)
  - [Pointer file — the redirect](#pointer-file--the-redirect)
  - [How a trusted skill is installed](#how-a-trusted-skill-is-installed)
  - [Layout contract — skills, evals, tests](#layout-contract--skills-evals-tests)
  - [Security model](#security-model)
  - [Discovery index](#discovery-index)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Trusted external skill sources

A **skill source** is a repository — other than `apache/magpie` — that
ships Magpie-shaped skills (and their evals and tests). This page defines
how an adopter pulls a skill or whole skill-family from such a source and
wires it in so it behaves **exactly like an in-tree skill**: same
`magpie-`-prefixed symlink relay, same override layer, same eval binding.

Per [`PRINCIPLES.md` §13](../../PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies),
installation is permitted **only from a *trusted* source** — one the
adopter has explicitly vouched for by committing its pin (method + URL +
ref + verification anchor) to the repo. A trusted install obeys the same
snapshot-plus-pin discipline the framework uses for itself: a gitignored
snapshot, a committed lock, a verified and deliberate fetch by the one
[`setup`](../../skills/setup/SKILL.md) skill — never a git submodule, and
never an unpinned or unverified auto-fetch. The full rationale and threat
model are in [`RFC-AI-0006`](../rfcs/RFC-AI-0006.md).

## The trust model — three layers

Trust is layered so an organization can *curate* candidate sources while
the *adopter* keeps the final say. Nothing is fetched until the adopter
opts in.

| Layer | File | Home | Role |
|---|---|---|---|
| **Discovery** | [`registry.md`](registry.md) | in-tree | The framework's index of known sources — curated **and** community. Editorial only; lists a source, never installs it. |
| **Org-curated** | `organizations/<org>/skill-sources.md` | in-tree (or adopter-local org override) | An organization vouches for a set of sources its projects may draw from. Inherited by naming `organization: <org>`. Still not an install. |
| **Adopter opt-in** | `<project-config>/skill-sources.md` | committed in the adopter repo | **The install gate.** The adopter lists the source ids it trusts and commits each pin. *Only sources listed here are ever fetched.* |

An adopter may trust a source their org did **not** curate (list it
directly with a full descriptor), or decline one the org did. The org
layer is a convenience default, never a mandate — the same
`project → organization → framework` precedence the rest of the config
model uses (see [`AGENTS.md`](../../AGENTS.md#configuration-resolution-order)).

## Source descriptor

A **descriptor** identifies one source and enumerates what it `provides`.
It appears in the org-curated file and/or the adopter opt-in file; the
[registry](registry.md) links to the canonical one. Fields reuse the
[install-method](../setup/install-recipes.md) and lock vocabulary the
framework snapshot already uses, so resolution is mechanical.

```yaml
id: <source-id>                 # unique, kebab-case — the handle pointers reference
organization: <org>             # owning org; must name a directory under organizations/
name: "<human-readable name>"
maintainer: "<who — handle / team / org>"
method: <git-tag | git-branch | svn-zip>   # same three install methods as the framework
url: <git repo URL | svn/dist archive URL>
ref: <tag | branch | version>
# Verification anchor — the re-fetch guard, per method:
#   git-tag : commit: <SHA the tag resolved to>
#   svn-zip : sha512: <released archive SHA-512>
#   git-branch has no cryptographic anchor — it tracks the branch tip
layout:                         # where things live inside the source repo
  skills_root: skills           # default: skills
  evals_root: tools/skill-evals/evals   # default: tools/skill-evals/evals
provides:
  - skill: <name>               # one unprefixed skill directory name
  - family: <prefix>-*          # or a family prefix — pulls every skill matching it
```

`method`, `url`, `ref`, and the per-method anchor are exactly the keys the
framework's own [`.apache-magpie.lock`](../../skills/setup/SKILL.md) carries;
`svn-zip` is the only method with cryptographic verification (SHA-512 +
optional GPG against the source's `KEYS`), `git-tag` pins a resolved
`commit`, and `git-branch` tracks a tip (WIP only, no frozen anchor).

## Pointer file — the redirect

Where a skill directory would sit, a **pointer file** names its source.
It is the "redirect link": the skill body, evals, and tests are **not**
committed here — they are fetched into the gitignored snapshot at
adopt/upgrade time. The file is `skills/<name>/source.md` (deliberately
**not** `SKILL.md`, so the skill validator's `SKILL.md`-gated checks do
not fire on a stub).

```markdown
---
source: <source-id>            # references a descriptor above
organization: <org>            # must name a directory under organizations/
skill_path: skills/<name>      # subpath of the skill within the source repo
evals_path: tools/skill-evals/evals/<name>   # subpath of its eval suite
---

<!-- SPDX-License-Identifier: Apache-2.0 -->

# <name> — redirect to a trusted external source

This skill is provided by the trusted external source `<source-id>`
(`organization: <org>`). Its `SKILL.md`, eval suite, and tests are fetched
into the gitignored snapshot at `.apache-magpie-sources/<source-id>/` by
`/magpie-setup` and symlinked in exactly like an in-tree skill. This file
is a pointer only — do not add skill logic here; contribute it to the
source repo instead.
```

`source:` is already an allowed optional key in the skill validator's
frontmatter set, so nothing about the pointer is a special case for the
common-path validation — only the additional pointer-specific checks in
[the validator](../../tools/skill-and-tool-validator/) apply (the `source:`
resolves to a known descriptor; the `organization:` is a known org; the
directory draws no eval-coverage advisory because its evals are external).

## How a trusted skill is installed

The [`setup`](../../skills/setup/SKILL.md) skill drives the fetch — the
[`skill-sources`](../../skills/setup/skill-sources.md) sub-action
(`/magpie-setup skill-sources`). In outline:

1. Read `<project-config>/skill-sources.md` — the trust list. Sources not
   listed there are never fetched.
2. For each trusted source, **fetch + verify** into
   `.apache-magpie-sources/<source-id>/` (gitignored) reusing the framework
   [install recipes](../setup/install-recipes.md) verbatim — `git clone
   --depth=1 --branch <ref>` for git methods; download + `sha512sum -c` +
   optional `gpg --verify` for `svn-zip`.
3. Record the pins: committed `.apache-magpie.sources.lock` (per-source
   `method`/`url`/`ref` + anchor) and gitignored
   `.apache-magpie.sources.local.lock` (what this machine fetched + when) —
   the same two-lock drift model as the framework snapshot.
4. For each provided skill, create the canonical + relay symlinks
   (`.agents/skills/magpie-<name>` → `../../.apache-magpie-sources/<id>/skills/<name>/`,
   with per-agent relays back through the canonical entry) — identical to
   how framework-family skills are wired.

Drift detection, `upgrade`, and `verify` extend to the source locks: a
committed-vs-local mismatch surfaces the gap and proposes
`/magpie-setup upgrade`, which re-fetches per the committed pins.

## Layout contract — skills, evals, tests

A skill's eval suite lives **outside** its directory, at
`tools/skill-evals/evals/<name>/`, bound to the skill by directory name and
a repo-relative `skill_md:` path in each step's `fixtures/step-config.json`
(see [`tools/skill-evals/README.md`](../../tools/skill-evals/README.md)).
For that binding to resolve after a fetch, a source repo must keep the same
two-tree layout the framework uses — `skills/<name>/` for the body and
`tools/skill-evals/evals/<name>/` for the evals — declared via the
descriptor's `layout:` block. Fetching a source pulls **both** trees plus
any tool `tests/` the skill depends on, so the pulled skill is testable and
eval-able exactly as it is in its home repo.

## Security model

- **Adopter-vouched, always.** The `<project-config>/skill-sources.md`
  trust list is the only thing that authorizes a fetch. An org curating a
  source, or the registry listing one, never triggers an install.
- **Pinned + verified.** Every trusted source carries a pin with a
  verification anchor (`commit` / `sha512`). `git-branch` (tip-tracking, no
  anchor) is WIP-only, exactly as for the framework snapshot.
- **Untrusted stays discovery-only.** The [registry](registry.md) and org
  curation are editorial pointers for humans to evaluate — not
  supply-chain hooks.
- **External content is data.** Skills pulled from a source are still
  subject to the framework's injection-guard discipline; a fetched skill is
  reviewed like any other before it runs.

The full threat model (source-repo compromise, eval provenance, unpinned
fetch) is in [`RFC-AI-0006`](../rfcs/RFC-AI-0006.md#security-model).

## Discovery index

The known sources — framework-curated and community-maintained — are
listed in [`registry.md`](registry.md). Listing is editorial discovery
only; it makes no guarantee and triggers no install.

## See also

- [`RFC-AI-0006`](../rfcs/RFC-AI-0006.md) — the design + trust + threat model.
- [`docs/extending.md`](../extending.md) — the full extension model (what / where / who).
- [`organizations/README.md`](../../organizations/README.md) — the organization layer and its `skill-sources.md` curation.
- [`skills/setup/SKILL.md`](../../skills/setup/SKILL.md) — the adopt/upgrade/verify flow that fetches and pins sources.
- [`docs/adapters/registry.md`](../adapters/registry.md) — the sibling discovery index for tool adapters and organizations.
