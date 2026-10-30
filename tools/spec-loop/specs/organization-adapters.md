<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Organizations (governance + backend defaults grouped per org)
status: experimental
kind: feature
mode: infra
source: >
  Extends project-agnosticism.md and adapters.md. An organization groups the governance vocabulary and capability→backend
  defaults shared by every project under one governing body (foundation,
  company, maintainer collective), so those defaults live once instead of
  being copied into each project's manifest. Implemented under
  organizations/ (organizations/ASF/, organizations/independent/,
  organizations/_template/).
acceptance:
  - An organization's shared defaults (governance vocabulary + capability
    bundle + infra values) live in organizations/<org>/organization.md,
    not duplicated across each project's project.md.
  - A project selects its organization with a single key
    (organization:<org> in project.md) and inherits the rest.
  - Config resolves project.md -> organizations/<org>/ -> framework
    default, first hit wins; skills never branch on the organization,
    except to gate a surface marked as one organization's own.
  - A new organization can be authored from
    organizations/_template/ without editing any skill body.
---

## What it does

Introduces a configuration layer **between** a single project's
`<project-config>/` and the framework defaults. An **organization** captures what a governing organization makes default for all
its projects:

- **governance vocabulary** — what the governing body is called
  (`<governance-body>`), how contributors are admitted
  (`contributor_intake`: ICLA / DCO / none), the project-lifecycle
  stages (`<project-stage>`), role names; and
- **capability→backend bundle + infrastructure values** — which tool
  adapter fulfils each capability (CVE authority, mail archive, project
  metadata, forwarder, …) and the concrete URLs / addresses those
  backends use.

This removes the duplication whereby every ASF project re-declared the
identical "ASF default" values in its own `project.md`.

## Where it lives

- `organizations/README.md` — the entity overview.
- `organizations/ASF/` — the reference organization (Apache Software
  Foundation defaults: PMC governance, Vulnogram, PonyMail,
  `apache-projects-mcp`, ASF-security forwarder, `*.apache.org` infra).
- `organizations/independent/` — the no-formal-org baseline (DCO, GHSA,
  GitHub Releases, no list/forwarder/metadata backends); inherited by
  `projects/non-asf-example/`.
- `organizations/_template/` — authoring skeleton.
- Resolution contract: `AGENTS.md` §"Configuration resolution order".
- The project-manifest template that names the organization,
  `plugins/magpie-setup/templates/project.md` (`projects/_template/` links to
  that directory since #1410), marks the org-level rows (CVE authority,
  project metadata, …) as inherited from `organizations/<org>/organization.md`.
- The framework's own published configuration,
  `.apache-magpie-overrides/project.md`, declares `organization: ASF` and so
  exercises the ASF profile on this repository (#1412).
- Path exempted from placeholder / asf-coupling lint via
  `ALLOWLIST_PATHS += "organizations/"` in `skill-and-tool-validator`.

## Behaviour & contract

- A project names its organization once: `organization: <org>` in
  `<project-config>/project.md` (default `independent`).
- Every placeholder and dotted config key resolves
  `project.md → organizations/<org>/organization.md → framework default`,
  first hit wins. This is the only inheritance in the config model.
- Skills do **not** read the `organization:` key to pick a backend or a
  value; they read capability keys (`cve_authority.tool`,
  `archive_system.kind`, `<governance-body>`, …) and take the first value
  the chain yields.
- **The one exception is a surface that exists only for one
  organization's services (#1796, #1798).** Such a surface is marked
  (`**Organization:** ASF` on the tool, or a *Scope — `organization: ASF`*
  note on the doc) and gated on an explicit `organization: ASF` in the
  resolved `project.md`, never inferred from a capability value:
  `security-issue-sync`'s dashboard mode (Step D0) and the
  `magpie-asf-security-dash` CLI (exit `3` otherwise, before the cookie or
  network is touched; HTML comments and fenced examples are ignored when
  reading the key), `permission-audit --organization` (PonyMail,
  apache-projects and Vulnogram recommendations only for `ASF`, as passed
  by setup verify), `dependency-license-audit`'s `asf` default policy
  (`allowlist` for every other project), `workflow-optimization`'s
  GitHub Actions Policy / `.asf.yaml` / `creation_cap` checks (or, with no
  project config, an `apache` repository owner), and the `asf-security`
  forwarder, `tools/gmail/asf-relay.md` and `ponymail-archive.md`.
  An unset or `TODO` organization is not `ASF`.
- **Setup settles the organization before sourcing its values (#1779).**
  It proposes `ASF` only on evidence — a GitHub remote under `apache/`, a
  root `.asf.yaml`, or a Subversion URL under `https://svn.apache.org/`
  from `magpie-vcs probe` — and otherwise asks, never defaulting to `ASF`;
  a non-ASF project inherits no `apache.org` address, no `cna_private_*`
  field and never the ASF CNA's UUID.
- **Org-wide security values live in the organization (#1745, #1779).**
  The ASF manifest carries the ASF CNA's single UUID
  (`cve_authority.vulnogram.asf_org_id`, the `assignerOrgId` of every
  Apache record, used only by the generated CVE JSON and never for
  allocation), which replaced the per-project `asf_org_id` row of the
  project template, and `security_inbox.cve_tool_senders:
  [security@apache.org]`, the organization-wide CVE bookkeeping sender.
  A project list replaces, never merges with, an organization list, so a
  project override repeats the inherited entries.
- An organization declares only org-wide values. Per-project
  values (security-list address, scope labels, product name, roster,
  tracker label/body-field vocabulary) stay in `project.md`.
- The `organizations/ASF/organization.md` keys mirror the namespaces of
  the project manifest's *Security workflow configuration* section so
  resolution is mechanical.
- Organization smoke coverage should exercise more than one family. At
  minimum, a non-ASF profile must be able to drive security intake
  backend selection, release backend selection, and contributor-governance
  defaults without editing skill bodies.

## Out of scope

- Removing the ASF default *values* from the project-manifest template
  (now `plugins/magpie-setup/templates/project.md`; the reflow to actually
  inherit) — a follow-up change.
- Making the `asf:false` skill families fully agnostic (moving residual
  PMC/ICLA/incubator vocabulary behind placeholders) — a follow-up.
- Replacing the per-family `asf: true/false` metadata with an optional
  family-level `organization:` scope — a follow-up.
- Any runtime fetch/install of externally-defined adapters (discovery
  only; see PRINCIPLES §13).

## Acceptance criteria

- An organization's shared defaults live in
  `organizations/<org>/organization.md`, not duplicated per project.
- `organization: <org>` in `project.md` selects the adapter.
- Resolution is `project.md → organization → framework default`,
  first hit wins; no skill branches on the organization except to gate a
  surface marked as that organization's own, and such a gate stops for an
  unset or `TODO` organization.
- A new organization can be authored from `organizations/_template/` with
  no skill edits.
- Smoke fixtures cover security intake, release backend, and contributor
  governance defaults for at least one non-ASF profile.

## Validation

```bash
# Validator passes; organizations/ is allowlisted so ASF terms inside
# organizations/ASF/ do not trip the placeholder / asf-coupling checks.
uv run --project tools/skill-and-tool-validator skill-and-tool-validate

# Doc + link + placeholder hooks green on the new files.
prek run --files organizations/**/*.md docs/vendor-neutrality.md AGENTS.md
```

Manual resolution check: a `project.md` with `organization: ASF` and a
key omitted resolves to the ASF adapter value; `organization: independent`
resolves to the baseline.

Adapter layout is enforced: `validate_organization_structure` in
`tools/skill-and-tool-validator` requires every `organizations/<org>/`
directory except `_template` to contain `README.md` and `organization.md`.
Omitting either results in a HARD violation, so an incomplete adapter fails
the validator before any skill can resolve against it. It is not a separate
command — the check runs inside the top-level `skill-and-tool-validate`
sweep above.

Organization *references* are enforced alongside it: every `organization:`
value — in a skill's `SKILL.md` frontmatter, a tool README's
`**Organization:**` line, a skill-source descriptor, and a
`skills/<name>/source.md` pointer — must name a directory under
`organizations/` (`known_organizations()`, which excludes `_template`).
A typo or a dangling adapter name is therefore a HARD violation rather than
a silent fall-through to the framework default.

## Known gaps

- **The structural check verifies file presence, not manifest content.**
  `validate_organization_structure` requires `README.md` and
  `organization.md` to exist; nothing validates what `organization.md`
  actually declares. A present-but-empty manifest passes, and the keys it
  omits then resolve silently to framework defaults instead of failing
  loudly. Every other organization check in `skill-and-tool-validator` is
  referential ("is this org name known?"), not schema-level.
- **`skill-sources.md` is outside the required set.** All three in-tree
  adapters carry one, `organizations/_template/skill-sources.md` tells
  authors to keep the file with an empty list when the organization curates
  nothing, and the validator globs `organizations/*/skill-sources.md` when
  collecting source descriptors — but the filename is absent from
  `_ORG_REQUIRED_FILES`, so an adapter that drops it is still structurally
  valid.
- **The `_template` authoring path is not covered by an eval.** `ASF` and
  `independent` are the only adapters in the tree, and no eval exercises
  authoring a fresh organization from `organizations/_template/`, so the
  "new organization with no skill edits" criterion rests on the two in-tree
  examples rather than on a test.
