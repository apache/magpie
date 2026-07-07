<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Skill-source registry](#skill-source-registry)
  - [Org-curated sources](#org-curated-sources)
  - [Community / external sources](#community--external-sources)
    - [Adding a source to this index](#adding-a-source-to-this-index)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Skill-source registry

A **discovery** index of the external [skill sources](README.md) Magpie
knows about — repositories other than `apache/magpie` that ship
Magpie-shaped skills. It is the skills counterpart to the
[adapter registry](../adapters/registry.md).

> **Discovery, then adopter-vouched install.** Listing a source here is
> **editorial only** — it makes no guarantee about the source and triggers
> no install. Per [`PRINCIPLES.md` §13](../../PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies),
> a source is installed only after the *adopter* trusts it explicitly by
> committing its pin to `<project-config>/skill-sources.md`. An entry here
> is a pointer for humans to evaluate, not a supply-chain hook. See
> [`README.md`](README.md) for the trust model and the descriptor format.

## Org-curated sources

Sources an organization vouches for, declared in
`organizations/<org>/skill-sources.md` and inherited by projects that set
`organization: <org>`. Curation is still not installation — the adopter
opts each one in.

| Organization | Curated sources | File |
|---|---|---|
| Apache Software Foundation | *(none listed yet)* | [`organizations/ASF/skill-sources.md`](../../organizations/ASF/skill-sources.md) |
| Independent (no formal governing body) | *(none listed yet)* | [`organizations/independent/skill-sources.md`](../../organizations/independent/skill-sources.md) |

## Community / external sources

Sources maintained **outside** any in-tree organization curation — kept in
their authors' own repos and linked here for discovery. An adopter wires
one in by writing a full descriptor into their
`<project-config>/skill-sources.md` (see the trust model above); the
framework never fetches them unprompted.

| Source id | Owning org | Maintainer | Repository | Notes |
|---|---|---|---|---|
| *(none listed yet)* | | | | Open a PR to add a row — see below. |

### Adding a source to this index

Open a PR against `apache/magpie` that adds one row with: the source id,
the owning organization (a directory under `organizations/`), the
maintainer, a link to the source repository, and a one-line note. If the
source belongs to an in-tree organization, add its descriptor to that
org's `skill-sources.md` and reference it from the *Org-curated* table
instead. Listing here is **editorial discovery only** — it makes no
guarantee and triggers no install.

## See also

- [`README.md`](README.md) — the trust model, descriptor, and pointer-file formats.
- [`RFC-AI-0006`](../rfcs/RFC-AI-0006.md) — design and threat model.
- [`docs/adapters/registry.md`](../adapters/registry.md) — the sibling discovery index for tool adapters and organizations.
- [`docs/extending.md`](../extending.md) — the full extension model.
