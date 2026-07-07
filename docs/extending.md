<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Extending Magpie](#extending-magpie)
  - [What you can extend](#what-you-can-extend)
  - [Where an extension can live (the three homes)](#where-an-extension-can-live-the-three-homes)
    - [How each entity resolves across homes](#how-each-entity-resolves-across-homes)
  - [Who extends what](#who-extends-what)
    - [A project (adopter)](#a-project-adopter)
    - [An organization (foundation / company / collective)](#an-organization-foundation--company--collective)
    - [An individual](#an-individual)
  - [Contributing an extension back](#contributing-an-extension-back)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Extending Magpie

Magpie is built to be extended without forking it. This page is the map:
**what** you can extend, **where** an extension can live, and **who**
typically owns each kind.

If you only remember one rule: extensions are **discovered and wired in
deliberately, never auto-installed** — per
[`PRINCIPLES.md` §13](../PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies),
indexes and catalogs exist for discovery, not installation.

## What you can extend

| Entity | What it is | Reference |
|---|---|---|
| **Skill** | a workflow the agent follows | [`PRINCIPLES.md` §14](../PRINCIPLES.md#14-skills-are-the-unit-of-authorship), [`write-skill`](../skills/write-skill/SKILL.md) |
| **Skill source** | a trusted external repo a skill/family is *pulled* from | [`docs/skill-sources/`](skill-sources/README.md), [`RFC-AI-0006`](rfcs/RFC-AI-0006.md) |
| **Tool / tool adapter** | the only layer that knows a vendor — a backend behind a capability contract | [vendor-neutrality § Tool adapters](vendor-neutrality.md#tool-adapters), [`adapters/authoring.md`](adapters/authoring.md) |
| **Capability contract** | the stable verb set a skill depends on; the seam adapters plug into | [`tools/cve-tool/`](../tools/cve-tool/) and siblings |
| **Organization** | governance vocabulary + backend bundle + identity, shared by an org's projects | [`organizations/README.md`](../organizations/README.md) |
| **Project config** | one adopter's concrete values | [`projects/_template/`](../projects/_template/) |
| **User config** | one person's preferences (handle, governance membership, local clone paths) | [`AGENTS.md` § user.md](../AGENTS.md#usermd-resolution-order) |

## Where an extension can live (the three homes)

Every extension — a skill, an adapter, or a whole organization — has the
same three possible homes. They are not mutually exclusive: start local,
upstream later.

| Home | Where | Travels with | Licence | Best when |
|---|---|---|---|---|
| **In-tree** (upstream) | a PR into `apache/magpie` | the framework, to every adopter | Apache-2.0 ([§17](../PRINCIPLES.md#17-contributions-land-under-apache-license-20)) | the extension is broadly useful — other projects share the backend/org |
| **In your adopter repo** | `<project-config>/` + `<project-config>/.apache-magpie-overrides/` (committed) | your repo | yours | it is specific to your project, or not ready to upstream |
| **External** (another repo) | a repo you (or a community) maintain, **referenced** from config | nothing automatically — you vendor/clone it in deliberately | the author's | a third party maintains it, or it is shared across your repos but not in Magpie |

The middle home is the framework's **snapshot + override** model
([§13](../PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies)):
the framework is a gitignored snapshot; your additions and tweaks are
committed agent-readable markdown alongside it. The external home is the
same act of wiring-in as the middle one — you just keep the source in
another repo and the [registry](adapters/registry.md) lists it for
discovery.

### How each entity resolves across homes

- **Skills** — framework skills come from the snapshot; project tweaks
  live in `.apache-magpie-overrides/<skill>.md` (consulted at run time);
  a wholly new skill you keep can live in your repo's agent-skill dir.
  A skill or skill-family maintained in **another repo** can also be
  *pulled in* from a **trusted external source** — a `skills/<name>/source.md`
  redirect that names a pinned, verified source the adopter has vouched
  for, fetched into the snapshot and wired in like a framework skill. This
  is the one external home that *installs* rather than merely being
  referenced (see [`PRINCIPLES.md` §13](../PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies)
  and [`docs/skill-sources/`](skill-sources/README.md)).
- **Tools / adapters** — selected per capability in
  `<project-config>/project.md` *Tools enabled*. The selected adapter may
  be an in-tree `tools/<name>/`, a directory you keep in your adopter
  repo, or one you vendored from an external repo. Skills never branch on
  the choice. See [`adapters/authoring.md`](adapters/authoring.md).
- **Organizations** — `organization: <org>` in `project.md` resolves to
  an in-tree [`organizations/<org>/`](../organizations/README.md) first;
  if your organization is not in-tree, it resolves to an adopter-local
  org adapter you keep under `<project-config>/.apache-magpie-overrides/organizations/<org>/`
  (copied from your own or another repo). Either way the resolution chain
  is `project.md → organization → framework default`.

## Who extends what

### A project (adopter)

Owns its `<project-config>/`: identity, per-skill config, and
`.apache-magpie-overrides/` for behaviour tweaks. A project may also
keep a **local organization or adapter** in its override layer when no
in-tree one fits — and upstream it later with
[`setup-override-upstream`](../skills/setup-override-upstream/SKILL.md).

### An organization (foundation / company / collective)

Owns an **organization adapter** — the defaults every project under it
inherits (CVE authority, mail/forwarder/archive backends, governance
vocabulary, identity + logo). It can ship that adapter **in-tree**
(contributed to `apache/magpie`, so all its projects and others reuse it)
or maintain it **in the organization's own repo** and have member
projects point at it. See [`organizations/README.md`](../organizations/README.md).

### An individual

Owns their `user.md` (per-user preferences, resolved first-match across
`$APACHE_MAGPIE_USER_CONFIG` → `~/.config/apache-magpie/user.md` →
`<project-config>/user.md`). An individual can also **author** any skill,
adapter, or organization above and choose a home for it — contribute it
upstream, keep it in their project's override layer, or maintain it in a
personal repo and link it.

## Contributing an extension back

Whatever the home you start with, upstreaming is one PR away and benefits
every adopter:

- a **skill** — [`write-skill`](../skills/write-skill/SKILL.md) +
  [`CONTRIBUTING.md`](../CONTRIBUTING.md);
- a **tool/adapter or organization** —
  [`adapters/authoring.md`](adapters/authoring.md);
- an **override you have been running** —
  [`setup-override-upstream`](../skills/setup-override-upstream/SKILL.md).

## See also

- [`docs/vendor-neutrality.md`](vendor-neutrality.md) — the skills / tools / capabilities / organizations architecture.
- [`docs/adapters/registry.md`](adapters/registry.md) — discovery index of in-tree and external adapters.
- [`organizations/README.md`](../organizations/README.md) — the organization entity and its resolution order.
