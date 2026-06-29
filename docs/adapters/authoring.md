<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Authoring an adapter](#authoring-an-adapter)
  - [Two homes for an adapter](#two-homes-for-an-adapter)
  - [Authoring a tool adapter](#authoring-a-tool-adapter)
  - [Authoring an organization](#authoring-an-organization)
  - [After authoring](#after-authoring)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Authoring an adapter

When Magpie ships no [adapter](../vendor-neutrality.md#tool-adapters) for
your backend — a forge, a CNA tool, a chat system, a mail archive, a VCS,
or a whole [organization](../../organizations/README.md) profile — you
author one. The skills stay agnostic: they target a *capability*, and
your adapter supplies the concrete backend. This guide is the how-to; the
[registry](registry.md) is the index of what already exists.

## Two homes for an adapter

| | Contribute to Magpie | Keep it external |
|---|---|---|
| **Where it lives** | a PR into `apache/magpie` | your own repository |
| **License** | Apache-2.0 ([§17](../../PRINCIPLES.md#17-contributions-land-under-apache-license-20)) | yours |
| **Who reuses it** | every adopter on that backend | you (and anyone you share it with) |
| **Discovery** | shipped in-tree | optionally listed in the [registry](registry.md) |
| **Install** | part of the snapshot | you wire it in deliberately — never auto-fetched ([§13](../../PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies)) |

Both are first-class. Contributing upstream is preferred when the backend
is one other projects share; an external adapter is right when it is
specific to you or you are not ready to upstream.

## Authoring a tool adapter

A tool adapter fulfils a capability *contract* for one backend.

1. **Find the contract.** Pick the `tools/<contract>/` whose capability
   you are implementing (e.g. [`tools/cve-tool/`](../../tools/cve-tool/)
   for a CNA tool, [`tools/mail-archive/`](../../tools/mail-archive/) for
   an archive). Its README enumerates the methods/verbs your adapter must
   provide. If no contract exists for the capability, propose one first.
2. **Create the adapter directory** — `tools/<contract>-<backend>/` (in
   tree) or a directory in your own repo (external). Implement the
   contract's operations.
3. **Declare the metadata** the validator requires (see
   [`tools/AGENTS.md`](../../tools/AGENTS.md)):
   - a `**Capability:** capability:NAME` line in the README;
   - a `## Prerequisites` section (runtime, CLIs, credentials, network);
   - optionally an `**Organization:** <org>` line if the adapter belongs
     to a specific organization.
4. **Wire it in.** Point your `<project-config>/project.md` *Tools
   enabled* manifest (or the relevant capability key, e.g.
   `cve_authority.tool`) at the adapter. Skill bodies never change.
5. **Add an eval** ([§8](../../PRINCIPLES.md#8-eval-is-a-release-blocking-discipline))
   under `tools/skill-evals/evals/` so the adapter's behaviour is graded,
   not just demoed.

The [`write-skill`](../../skills/write-skill/SKILL.md) flow and
[`CONTRIBUTING.md`](../../CONTRIBUTING.md) walk the conventions in detail;
`skill-and-tool-validate` enforces the capability + prerequisites lines.

## Authoring an organization

An organization groups governance vocabulary + capability→adapter
selections + identity for every project under one governing body. To add
one, copy [`organizations/_template/`](../../organizations/_template/) to
`organizations/<org>/`, fill in `organization.md` (identity incl. `logo`,
governance vocabulary, and the backend bundle), and point projects at it
with `organization: <org>`. See
[`organizations/README.md`](../../organizations/README.md).

## After authoring

- **Contributing upstream?** Open the PR; once it merges and adopters run
  `/magpie-setup upgrade`, the adapter is available to everyone.
- **Keeping it external?** Optionally add a row to the
  [registry](registry.md#community--external-adapters) so others can
  discover it — discovery only, no install.
