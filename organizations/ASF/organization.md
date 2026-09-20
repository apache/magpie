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
  - [Inference endpoint](#inference-endpoint)
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
  reporter_response_timeout_days: 14   # ASF policy: a silent reporter must not block the team
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

## Inference endpoint

The Foundation-wide sanctioned-inference gateway, **LLMAO**
(`llm.apache.org`), live since September 2026. A committer authenticates
with a personal access token; spend is attributed per key. Projects
inherit this as the ASF-hosted option for the vendor-neutrality
requirement in
[RFC-AI-0004 § Principle 3](../../docs/rfcs/RFC-AI-0004.md); it does not
displace whatever agent harness a maintainer already runs.

```yaml
inference:
  gateway: https://llm.apache.org
  auth: pat                            # committer personal access token
  status: pilot                        # not GA — see privacy_class and limitations
  # Privacy classification for the approved-LLM gate. LLMAO is NOT
  # default-approved for foundation private data: it serves from rented
  # third-party GPU hardware and pilot traffic is visible to llmao admins.
  # See tools/privacy-llm/models.md — "Carve-outs from the *.apache.org rule".
  privacy_class: project-internal      # public + project-internal only
  recommended_model: gemma4-26b        # reasoning off by default — see note below
  models:
    - id: gemma4-26b
      context_tokens: 131072
      modalities: [text, vision]
      tools: true
      reasoning_on_by_default: false
    - id: qwen3.8-27b
      context_tokens: 131072
      modalities: [text, vision]
      tools: true
      reasoning_on_by_default: true
    - id: qwen3-8b
      context_tokens: 40960
      modalities: [text]
      tools: true
      reasoning_on_by_default: true
  known_limitations:
    # Tool use over the Anthropic-compatible path is broken upstream:
    # LiteLLM routes it to vLLM's /v1/responses with a tool_choice shape
    # vLLM rejects. Plain conversation is unaffected. Magpie skills are
    # tool-driven, so they cannot run against this gateway until it lands.
    - anthropic_tool_use_broken
    # spend_usd reports 0.00 for self-hosted models — no cost map yet, so
    # budget-based routing decisions cannot be made from gateway data.
    - budgets_do_not_meter_self_hosted
    # No automatic restart: a host restart leaves the box up, model down.
    - no_automatic_model_restart
```

**Pick a model whose reasoning is off by default.** A reasoning model
emits nothing while it thinks; agent clients abandon the stream and
retry, so the box runs the same generation twice for a response nobody
reads. `gemma4-26b` is the default for that reason.

**Connecting an agent.** Claude Code talks to the gateway with
environment variables alone — LiteLLM exposes `/v1/messages`, so no shim
is needed:

```bash
export ANTHROPIC_BASE_URL=https://llm.apache.org
export ANTHROPIC_AUTH_TOKEN=<your PAT>
export ANTHROPIC_MODEL=gemma4-26b
```

Throughput is single-stream and memory-bandwidth bound, so the models sit
closer together than their parameter counts suggest (~128 tok/s for
`gemma4-26b`, ~46–54 tok/s for the others). The difference shows up under
concurrency, where `qwen3.8-27b` reaches 20+ simultaneous requests and
`gemma4-26b` reaches 4. All published figures come from synthetic load;
recorded real usage is still only a few hundred requests.

Source: Andrew Musselman, *"llmao progress Sep 14"*,
`discuss@rai.apache.org`, 2026-09-14.

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
  # Automated (CI) release signing — ASF-specific option, offered by
  # `release-prepare automated-signing` only under this organization.
  # Policy: https://infra.apache.org/release-signing.html#automated-release-signing
  automated_signing:
    policy_url: https://infra.apache.org/release-signing.html#automated-release-signing
    key_request_channel: infra-jira            # https://issues.apache.org/jira/projects/INFRA
    key_request_background: INFRA-23996
    approval_body: security@apache.org        # Security Team approves the workflow before use
    key_spec: "4096-bit RSA, signing-only, private half held by infra-root only"
    trusted_publishing_action: apache/tooling-actions/upload-to-atr   # pin by commit SHA
    validation: "every signed artefact rebuilt bit-by-bit identical on trusted hardware before publication"
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
