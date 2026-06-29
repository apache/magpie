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
    default, first hit wins; skills never branch on the organization.
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
- Path exempted from placeholder / asf-coupling lint via
  `ALLOWLIST_PATHS += "organizations/"` in `skill-and-tool-validator`.

## Behaviour & contract

- A project names its organization once: `organization: <org>` in
  `<project-config>/project.md` (default `independent`).
- Every placeholder and dotted config key resolves
  `project.md → organizations/<org>/organization.md → framework default`,
  first hit wins. This is the only inheritance in the config model.
- Skills do **not** read the `organization:` key to branch behaviour;
  they read capability keys (`cve_authority.tool`, `archive_system.kind`,
  `<governance-body>`, …) and take the first value the chain yields.
- An organization declares only org-wide values. Per-project
  values (security-list address, scope labels, product name, roster,
  tracker label/body-field vocabulary) stay in `project.md`.
- The `organizations/ASF/organization.md` keys mirror the namespaces of
  the project manifest's *Security workflow configuration* section so
  resolution is mechanical.

## Out of scope

- Removing the ASF default *values* from `projects/_template/project.md`
  (the reflow to actually inherit) — a follow-up change.
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
  first hit wins; no skill branches on the organization.
- A new organization can be authored from `organizations/_template/` with
  no skill edits.

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

## Known gaps

- The reflow of `projects/_template/` + `projects/non-asf-example/` to
  set `organization:` and drop the now-inherited values is not yet done
  (tracked as the next change); until then the ASF defaults exist in both
  `projects/_template/project.md` and `organizations/ASF/`.
- No structural validator check yet enforces required files in
  `organizations/<org>/` (currently README + organization.md by
  convention).
- The family-level `organization:` scope (replacing `asf: true/false`)
  and the external-adapter discovery index are separate follow-ups.
