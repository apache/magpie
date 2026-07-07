<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Independent — organization (no formal governing body)](#independent--organization-no-formal-governing-body)
  - [Organization identity](#organization-identity)
  - [Governance vocabulary](#governance-vocabulary)
  - [CVE authority](#cve-authority)
  - [Governance gate](#governance-gate)
  - [Security inbox](#security-inbox)
  - [Forwarders / mail / archive / metadata — all off](#forwarders--mail--archive--metadata--all-off)
  - [Release process](#release-process)
  - [Roster / tracker](#roster--tracker)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Independent — organization (no formal governing body)

The **baseline** organization for a project that belongs to no
foundation: an informal maintainer collective or a single-vendor team
using GitHub-native security and releases. It is the `organization:`
value a project sets when it is not part of a larger organization, and
the profile [`projects/non-asf-example/`](../../projects/non-asf-example/)
inherits from.

Everything here is the *generic* path — no mailing lists, no forwarder
relay, no foundation CNA, no project-metadata service. A project may
still override any key.

## Organization identity

```yaml
organization_identity:
  id: independent
  name: "Independent (no formal organization)"
  url: null
  logo: null   # no organization logo; the website falls back to the project's own
```

## Governance vocabulary

```yaml
governance_vocabulary:
  governance_body: "maintainers"      # <governance-body> — no formal committee
  governance_body_full: "maintainer team"
  member_role: "maintainer"
  committer_role: "maintainer"
  contributor_intake: dco             # DCO sign-off (no ICLA)
  project_stage_vocab: []             # no lifecycle stages
  private_governance_list: null
```

## CVE authority

```yaml
cve_authority:
  tool: mitre-form                    # direct MITRE CNA form (vs ASF Vulnogram)
  allocate_url: https://cveform.mitre.org/
  record_url_template: https://www.cve.org/CVERecord?id=<CVE-ID>
  source_tab_url_template: null
  email_preview_url_template: null
  states: [allocated, public]
  publication_propagation: manual
  emits_allocation_email: false
  reviewer_channel: github-pr
  cve_tool_url: https://www.cve.org
```

## Governance gate

```yaml
governance:
  cve_allocation_gate: security-team-member
  gate_label: "security-team"
  release_vote_gating: false
  roster_url: null
```

## Security inbox

```yaml
security_inbox:
  kind: ghsa-inbox                    # GitHub Security Advisories private reports
  foundation_security_address: null
  has_forwarder_relay: false
  list_filter_query: null
```

## Forwarders / mail / archive / metadata — all off

```yaml
forwarders:
  enabled: []
mail_provider:
  primary: none
  fallback: none
archive_system:
  kind: none
  mail_archive_url: null
project_metadata:
  kind: none
  mandatory: false
  install_source: null
```

## Release process

```yaml
release_process:
  release_manager_lookup_cascade:
    - kind: roster_file
      path: "release-trains.md"
  artifact_registries: []
  release_dist: null                  # GitHub Releases (no svn dist area)
  project_wiki: null
  announce_list: null                 # announcements via GitHub Releases / Discussions
```

## Roster / tracker

```yaml
roster:
  source: roster-file:release-trains.md
tracker:
  visibility: private
  board: none
```
