<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Software Foundation — organization](#apache-software-foundation--organization)
  - [Organization identity](#organization-identity)
  - [Governance vocabulary](#governance-vocabulary)
  - [CVE authority](#cve-authority)
  - [Governance gate](#governance-gate)
  - [Security inbox](#security-inbox)
  - [Forwarders](#forwarders)
  - [Mail provider](#mail-provider)
  - [Archive system](#archive-system)
  - [Project metadata](#project-metadata)
  - [Release process](#release-process)
  - [Roster](#roster)
  - [Tracker conventions](#tracker-conventions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Software Foundation — organization

The **ASF organization**: the default governance vocabulary,
backend selections, and infrastructure values shared by every Apache
project that adopts Magpie. A project under the ASF sets
`organization: ASF` in [`<project-config>/project.md`](../../projects/_template/project.md)
and inherits everything below; it overrides a key only where it genuinely
differs (and supplies its own per-project values — security list address,
scope labels, product name, roster — which are *not* org-level and stay in
`project.md`).

Resolution: `project.md` → **this file** → framework default. See
[`organizations/README.md`](../README.md) and
[`AGENTS.md`](../../AGENTS.md#configuration-resolution-order).

The adapter contracts these blocks bind to live under
[`tools/cve-tool/`](../../tools/cve-tool/),
[`tools/mail-archive/`](../../tools/mail-archive/),
[`tools/forwarder-relay/`](../../tools/forwarder-relay/), and
[`tools/mail-source/`](../../tools/mail-source/); the shipping ASF
backends are [`tools/cve-tool-vulnogram/`](../../tools/cve-tool-vulnogram/),
[`tools/ponymail/`](../../tools/ponymail/),
[`tools/apache-projects/`](../../tools/apache-projects/), and the
ASF-security forwarder shape in
[`tools/gmail/asf-relay.md`](../../tools/gmail/asf-relay.md).

## Organization identity

Brand / display metadata, surfaced by the website (and any skill that
shows which organization a project belongs to). `logo` is the asset the
site renders for projects under this organization.

```yaml
organization_identity:
  id: ASF                              # matches the organizations/<id>/ dir name
  name: "Apache Software Foundation"   # full name, longer than the id; shown on the website
  url: https://www.apache.org/
  logo: https://www.apache.org/foundation/press/kit/asf_logo.svg
```

## Governance vocabulary

How the ASF names the roles and rules the skills speak about abstractly.
These resolve the `<governance-body>` / `<project-stage>` placeholders and
the contributor-intake mechanism flag.

```yaml
governance_vocabulary:
  governance_body: "PMC"              # <governance-body> — Project Management Committee
  governance_body_full: "Project Management Committee"
  member_role: "PMC member"
  committer_role: "committer"
  contributor_intake: icla            # ICLA on file before first commit (vs dco / none)
  project_stage_vocab: [incubating, top-level]   # <project-stage> — podling vs TLP
  private_governance_list: "private@<project>.apache.org"
```

## CVE authority

```yaml
cve_authority:
  tool: vulnogram                     # adapter under tools/cve-tool/ → tools/cve-tool-vulnogram/
  allocate_url: https://cveprocess.apache.org/allocatecve
  record_url_template: https://cveprocess.apache.org/cve5/<CVE-ID>
  source_tab_url_template: https://cveprocess.apache.org/cve5/<CVE-ID>?tab=source
  email_preview_url_template: https://cveprocess.apache.org/cve5/<CVE-ID>?tab=email
  states: [allocated, review-ready, publish-ready, public]   # Vulnogram DRAFT/REVIEW/READY/PUBLIC
  publication_propagation: poll        # Vulnogram has no webhook
  emits_allocation_email: true         # Vulnogram auto-emails the assigner list
  reviewer_channel: mailing-list       # PMC reviews on the private list
  # Resolves the <cve-tool-url> placeholder used in agnostic skills:
  cve_tool_url: https://cveprocess.apache.org
```

## Governance gate

```yaml
governance:
  cve_allocation_gate: pmc-member      # ASF PMC membership via OAuth into Vulnogram
  gate_label: "PMC"
  release_vote_gating: true            # ASF release process gates on outstanding security work
  roster_url: https://projects.apache.org/committee.html?<project>
```

## Security inbox

```yaml
security_inbox:
  kind: mailing-list
  foundation_security_address: security@apache.org   # ASF security team forwards reports here
  has_forwarder_relay: true
  list_filter_query: "list:<security-list-domain>"
```

## Forwarders

```yaml
forwarders:
  enabled: [asf-security]              # ASF security team relays reports onto project lists
  asf-security:
    contact_handle: security@apache.org
    preamble_match: "^Dear PMC,\\s+The security vulnerability report"
    credit_extraction_rule: "first-line-matching:^Reported by:\\s+(.+)$"
```

## Mail provider

```yaml
mail_provider:
  primary: gmail-mcp                   # triager Gmail account via tools/gmail/
  fallback: ponymail                   # read-only ASF archive backstop
```

## Archive system

```yaml
archive_system:
  kind: ponymail                       # lists.apache.org
  list_domain: <project>.apache.org
  search_url_template: "https://lists.apache.org/list?{list}:{year}-{month}:{query}"
  api_query_url_template: "https://lists.apache.org/api/thread.lua?list={list}&domain={list_domain}&id={thread_id}"
  advisory_publication_signal_url: "https://lists.apache.org/list.html?<users-list>"
  # Resolves the <mail-archive-url> placeholder used in agnostic skills:
  mail_archive_url: https://lists.apache.org
```

## Project metadata

```yaml
project_metadata:
  kind: apache-projects-mcp            # comdev MCP wrapping projects.apache.org/json
  mandatory: true                      # for ASF projects the MCP is a pre-flight prerequisite
  install_source: "apache/comdev @ main (mcp/apache-projects-mcp)"
```

## Release process

```yaml
release_process:
  release_manager_lookup_cascade:
    - kind: roster_file
      path: "release-trains.md"
    - kind: wiki_url
      url: "https://cwiki.apache.org/confluence/display/<PROJECT>/Release+Managers"
    - kind: mailing_list_vote_thread
      list: "<dev-list>"
  artifact_registries: [pypi, artifacthub]
  # Resolves agnostic-skill placeholders:
  release_dist: https://dist.apache.org/repos/dist          # <release-dist>
  project_wiki: https://cwiki.apache.org/confluence/display/<PROJECT>   # <project-wiki>
  announce_list: announce@apache.org                         # <announce-list>
```

## Roster

```yaml
roster:
  source: roster-file:release-trains.md   # canonical security-team / RM source for ASF projects
```

## Tracker conventions

```yaml
tracker:
  visibility: private                  # ASF security tracker existence is itself confidential
  board: github-projects-v2
```
