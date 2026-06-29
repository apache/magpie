<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Organization Name>` — organization](#todo-organization-name--organization)
  - [Organization identity](#organization-identity)
  - [Governance vocabulary](#governance-vocabulary)
  - [Capability-to-backend bundle](#capability-to-backend-bundle)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Organization Name>` — organization

Authoring skeleton for a new [organization](../README.md). Copy
this directory to `organizations/<org>/`, fill in the values, and point
projects at it with `organization: <org>` in their `project.md`.

Only declare keys that are **the same for every project under this
organization**. Per-project values (security-list address, scope labels,
product name, roster) belong in each project's `project.md`, not here.
Any key you omit falls through to the framework default. Start from
[`organizations/independent/organization.md`](../independent/organization.md)
(the generic baseline) and change only what your organization mandates;
[`organizations/ASF/organization.md`](../ASF/organization.md) is a fully
worked example.

## Organization identity

Brand / display metadata used by the website. `logo` is the asset the
site renders for projects under this organization.

```yaml
organization_identity:
  id: <org>                            # must match this directory's name
  name: "<Organization full name>"     # longer than the id; shown on the website
  url: <homepage URL>
  logo: <URL or path to the organization's logo, shown on the website>
```

## Governance vocabulary

```yaml
governance_vocabulary:
  governance_body: "<governance-body>"        # what your governing body is called
  governance_body_full: "<full name>"
  member_role: "<member role>"
  committer_role: "<committer role>"
  contributor_intake: <icla | dco | none>
  project_stage_vocab: []                      # lifecycle stages, or [] if none
  private_governance_list: <address | null>
```

## Capability-to-backend bundle

Declare each capability your organization standardizes. Use the same key
namespaces as the project manifest's *Security workflow configuration*
section so resolution is mechanical — see
[`projects/_template/project.md`](../../projects/_template/project.md)
for the full set of keys and their per-field documentation, and
[`organizations/ASF/organization.md`](../ASF/organization.md) for a
filled-in example. Typical blocks: `cve_authority`, `governance`,
`security_inbox`, `forwarders`, `mail_provider`, `archive_system`,
`project_metadata`, `release_process`, `roster`, `tracker`.

```yaml
# cve_authority: { tool: <adapter under tools/cve-tool/>, ... }
# archive_system: { kind: <adapter under tools/mail-archive/>, ... }
# project_metadata: { kind: <metadata backend | none>, ... }
# ...
```
