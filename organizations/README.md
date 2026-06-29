<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Organizations](#organizations)
  - [Membership — what can belong to an organization](#membership--what-can-belong-to-an-organization)
  - [Why this exists](#why-this-exists)
  - [Resolution order](#resolution-order)
  - [What ships here](#what-ships-here)
  - [Authoring a new organization](#authoring-a-new-organization)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Organizations

An **organization** in Magpie groups everything a governing body — a
foundation, a company, or an informal maintainer collective — makes
*default* for the projects that belong to it:

- its **identity** (`organization_identity`: `id`, full `name`, `url`,
  and `logo`) — the brand the website renders for projects under it;
- its **governance vocabulary** (what the governing body is called, how
  contributors are admitted, the project-lifecycle stages); and
- its **default backend selections + infrastructure values** — which
  tool [adapter](../docs/vendor-neutrality.md#tool-adapters) fulfils each
  capability (CVE authority, mail archive, project metadata, …) and the
  concrete URLs / addresses those backends use.

It is the layer between a single project's
[`<project-config>/`](../projects/_template/) and the framework
defaults. A project names its organization once
(`organization: <org>` in `<project-config>/project.md`) and inherits
the rest.

## Membership — what can belong to an organization

Beyond a *project*, four framework entities can declare that they
**belong to** an organization (and so assume its stack); the value names
a directory here, and absence means organization-agnostic:

| Entity | How it declares membership |
|---|---|
| **Skill** | `organization:` key in the `SKILL.md` frontmatter |
| **Skill family** | `organization:` scope banner in `docs/<family>/README.md` |
| **Tool** | `**Organization:** <org>` line in the tool `README.md` |
| **Tool adapter** | same as a tool — the adapter directory's README |

For example the ASF release-management and contributor-growth families,
their skills, and the `cve-tool-vulnogram` / `ponymail` /
`apache-projects` tools all declare `organization: ASF`. The validator
rejects a declared organization that has no directory here.

## Why this exists

Skills are vendor- and project-agnostic: they target *capabilities* and
resolve concrete values from configuration (see
[`docs/vendor-neutrality.md`](../docs/vendor-neutrality.md) and
[`PRINCIPLES.md` §12](../PRINCIPLES.md#12-the-framework-is-project-agnostic-concrete-names-live-in-adopter-config)).
Most of those concrete values are **the same for every project under one
organization** — every ASF project allocates CVEs through the same
Vulnogram instance, reads the same `lists.apache.org` archive, and gates
on PMC membership. Without this layer each project would re-declare the
identical "ASF defaults". The organization holds them once.

## Resolution order

Every placeholder and dotted config key resolves in this order
(first hit wins):

```text
<project-config>/project.md
  →  organizations/<org>/organization.md     (org named by project.md → organization:)
    →  framework default
```

A project overrides only what differs from its organization; an
organization overrides only what differs from the framework baseline.
The contract is stated once in
[`AGENTS.md`](../AGENTS.md#configuration-resolution-order) — skills do
not branch on the organization.

## What ships here

| Organization | What it is |
|---|---|
| [`ASF/`](ASF/) | The **Apache Software Foundation** organization — the reference organization; the default values that reproduce ASF project behaviour. |
| [`independent/`](independent/) | The **no-formal-organization** baseline — DCO sign-off, GitHub-native security/releases, no mailing-list/forwarder/metadata backends. Used by [`projects/non-asf-example/`](../projects/non-asf-example/). |
| [`_template/`](_template/) | Authoring skeleton for a **new** organization. |

## Authoring a new organization

Copy [`_template/`](_template/) to `organizations/<org>/`, fill in the
governance vocabulary and the capability→adapter bundle, and point your
project at it with `organization: <org>`. You can then either
**contribute it back** to `apache/magpie` under Apache-2.0 (so other
projects in your organization reuse it) or keep it local. See
[`docs/adapters/authoring.md`](../docs/adapters/authoring.md) (and
[`docs/vendor-neutrality.md` § Authoring your own adapter](../docs/vendor-neutrality.md#authoring-your-own-adapter)).
