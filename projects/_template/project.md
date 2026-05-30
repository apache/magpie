<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — project manifest](#todo-project-name--project-manifest)
  - [Identity](#identity)
  - [Repositories](#repositories)
  - [Mailing lists](#mailing-lists)
  - [Tools enabled](#tools-enabled)
  - [CVE tooling](#cve-tooling)
  - [GitHub project board](#github-project-board)
  - [Mail sources](#mail-sources)
    - [Backend declaration](#backend-declaration)
    - [Per-backend config](#per-backend-config)
  - [Issue-template fields](#issue-template-fields)
  - [Security workflow configuration](#security-workflow-configuration)
    - [CVE authority](#cve-authority)
    - [Governance](#governance)
    - [Security inbox](#security-inbox)
    - [Forwarders](#forwarders)
    - [Mail provider](#mail-provider)
    - [Archive system](#archive-system)
    - [Tracker](#tracker)
    - [Scope detection](#scope-detection)
    - [Release process](#release-process)
    - [Roster](#roster)
    - [Product](#product)
  - [Pointers to sibling files](#pointers-to-sibling-files)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — project manifest

This is the **project configuration** for `TODO: <project-name>`.
Every skill under [`../../.claude/skills/`](../../.claude/skills/)
reads the project name from `<project-config>/project.md` and then loads this manifest to resolve project-specific identity,
repositories, mailing lists, and references to the other files in
this directory.

Grep for `TODO` to see every field you still need to fill in:

```bash
grep -n TODO projects/<name>/project.md
```

## Identity

| Key | Value |
|---|---|
| `project_name` | TODO: e.g. `Apache Foo` |
| `vendor` | TODO: e.g. `Apache Software Foundation` |
| `short_name` | TODO: e.g. `Foo` |
| `product_family_url` | TODO: e.g. `https://foo.apache.org/` |

The `vendor` / `project_name` pair is what lands in the `vendor` and
`product` fields of the CVE 5.x record the CVE-JSON generator
produces.

## Repositories

| Key | Value | Purpose |
|---|---|---|
| `tracker_repo` | TODO: e.g. `foo-s/foo-s` | Private security tracker (this repo) |
| `tracker_repo_url` | TODO | |
| `tracker_default_branch` | TODO: e.g. `main` | Default PR target for the tracker repo |
| `tracker_project_board_url` | TODO: URL of the GitHub Project V2 board, if any | Security board |
| `upstream_repo` | TODO: e.g. `apache/foo` | Public codebase where fixes land |
| `upstream_repo_url` | TODO | |
| `upstream_default_branch` | TODO: e.g. `master` (older default) or `main` | Upstream's default branch — what `<default-branch>` resolves to. Distinct from `tracker_default_branch` (the security tracker repo's PR target) |
| `upstream_agents_md_url` | TODO: `https://github.com/<upstream>/blob/main/AGENTS.md` | Conventions this repo mirrors |
| `upstream_contributing_docs_url` | TODO | |
| `upstream_genai_disclosure_anchor` | TODO: URL + anchor for the project's Gen-AI disclosure guideline | |
| `upstream_security_policy_url` | TODO: `https://github.com/<upstream>/security/policy` | |

## Mailing lists

| Key | Value | Notes |
|---|---|---|
| `security_list` | TODO: e.g. `security@foo.apache.org` | Inbound reports; **not** publicly archived |
| `private_list` | TODO: e.g. `private@foo.apache.org` | PMC escalation; **not** publicly archived |
| `users_list` | TODO: e.g. `users@foo.apache.org` | Public advisories end up here; publicly archived |
| `dev_list` | TODO: e.g. `dev@foo.apache.org` | Release `[RESULT][VOTE]` threads; publicly archived |
| `announce_list` | TODO: e.g. `announce@apache.org` | Cross-project announcement list; publicly archived |
| `commits_list` | TODO: e.g. `commits@foo.apache.org` | Publicly archived |
| `asf_security_list` | `security@apache.org` | ASF-wide security team; relays some inbound reports |

**Public archives** typically live at
`https://lists.apache.org/list.html?<list>`. **Private** lists on
`lists.apache.org/thread/<id>` 404 for non-members. Only URLs on
publicly archived lists may appear in CVE `references[]` as
`vendor-advisory`; see `../../AGENTS.md` and
[`security-model.md`](security-model.md).

## Tools enabled

| Capability | Tool | Adapter directory | Config knobs declared here |
|---|---|---|---|
| Issue tracking + source control + project board | `github` | [`../../tools/github/`](../../tools/github/) | `tracker_repo`, `upstream_repo`, `github_project_board_*`, `issue_template_fields` |
| Inbound email / drafts | `<one or more mail-source backends>` | [`../../tools/mail-source/contract.md`](../../tools/mail-source/contract.md) (abstract) + per-backend adapter dirs (`tools/gmail/`, `tools/ponymail/`, `tools/mail-source/imap/`, `tools/mail-source/mbox/`, ...) | See [Mail sources](#mail-sources) below — declare each backend's role (primary / preferred-for-`<op>` / fallback / optional) and `mandatory` flag |
| CVE allocation + record mgmt | `vulnogram` | [`../../tools/cve-tool-vulnogram/`](../../tools/cve-tool-vulnogram/) | see [CVE tooling](#cve-tooling) below |
| Release voting / announce | TODO: ASF mailing lists — or replace with the project's release-comms backend | — | via `dev_list` / `announce_list` / `users_list` |

To replace a tool (e.g. swap GitHub issues for JIRA), declare an
alternate tool in the table above, add a `tools/<name>/` adapter
directory, and make sure the values the generic skills need are still
reachable from this manifest.

## CVE tooling

TODO: describe which CNA tool the project uses. For ASF projects the
default is ASF's Vulnogram; other CNAs will substitute their own
equivalents. The Vulnogram-side mechanics live under
[`../../tools/cve-tool-vulnogram/`](../../tools/cve-tool-vulnogram/); the per-project
values below are what the generic recipes substitute in.

| Key | Value |
|---|---|
| `cve_tool` | TODO: e.g. `vulnogram` (ASF-hosted) |
| `cve_tool_allocate_url` | TODO: e.g. `https://cveprocess.apache.org/allocatecve` |
| `cve_tool_record_url_template` | TODO: e.g. `https://cveprocess.apache.org/cve5/<CVE-ID>` |
| `cve_tool_source_tab_url_template` | TODO |
| `cve_allocation_gated_by` | TODO: e.g. `Foo PMC membership (ASF OAuth)` |
| `asf_org_id` | TODO: project's CNA org UUID (for ASF projects: `f0158376-9dc2-43b6-827c-5f631a4d8d09`) |
| `cna_private_owner` | TODO: e.g. `foo` (CNA_private.owner — identifies the project slug inside the ASF CNA queue) |
| `cna_private_projecturl` | TODO: e.g. `https://foo.apache.org/` |
| `cna_private_userslist` | TODO: e.g. `users@foo.apache.org` |

## GitHub project board

If the project uses a Projects V2 board for its security-issue view,
declare the node IDs below. Fetch with the introspection query in
[`../../tools/github/project-board.md`](../../tools/github/project-board.md#introspection--re-fetch-the-option-ids).
If the project does not run a board, leave the table blank — skills
treat missing board config as *"no board reconciliation"*.

| Key | Value |
|---|---|
| `project_board_url` | TODO |
| `project_board_number` | TODO |
| `project_board_node_id` | TODO |
| `status_field_node_id` | TODO |

**`Status` column → option-ID mapping** (re-fetch if any write
returns `not found`):

| Column | Option ID |
|---|---|
| `Needs triage` | TODO |
| `Assessed` | TODO |
| `CVE allocated` | TODO |
| `PR created` | TODO |
| `PR merged` | TODO |
| `Fix released` | TODO |
| `Announced` | TODO |

## Mail sources

The skills treat every supported mail backend the same way —
through the abstract operations defined in
[`../../tools/mail-source/contract.md`](../../tools/mail-source/contract.md).
The adopter declares which backends are configured, what *role*
each plays, and whether any are *mandatory*. The skill's resolution
rule (see the contract) then picks the right backend per operation
at run time.

### Backend declaration

One row per configured backend. **Exactly one** row carries
`role: primary`. Multiple rows may carry `preferred for <op>` to
override the primary for specific operations. `fallback` rows are
tried in order when no preferred / primary backend supports the op.
`mandatory: yes` means the skill **refuses to run** when that
backend is unavailable; `no` means the skill continues with the
remaining backends (and skips ops that no available backend supports).

| Backend | Role | Mandatory | Notes |
|---|---|---|---|
| TODO: `gmail` | TODO: e.g. `primary` | TODO: `yes` / `no` | TODO: e.g. "Triager Gmail account subscribed to `<security-list>` and `<private-list>`" |
| TODO: `ponymail` | TODO: e.g. `fallback` or `preferred for thread_url` | TODO | TODO: e.g. "Read-only archive backstop; PMC LDAP session required for private-list reads" |
| TODO: *(add more rows as needed — `imap`, `mbox`, project-specific adapter)* | | | |

Reference adapter docs:
[`tools/gmail/tool.md`](../../tools/gmail/tool.md) (full read+write),
[`tools/ponymail/tool.md`](../../tools/ponymail/tool.md) (read-only ASF archive),
[`tools/mail-source/imap/README.md`](../../tools/mail-source/imap/README.md) (stub),
[`tools/mail-source/mbox/README.md`](../../tools/mail-source/mbox/README.md) (read-only offline archive — stub).

### Per-backend config

Per-backend values the generic recipes substitute in. Only fill in
the rows for backends declared above; leave the rest blank or
remove the row.

| Key | Backend | Value |
|---|---|---|
| `security_list_domain` | `gmail` | TODO: e.g. `security.foo.apache.org` — Gmail `list:` operator uses the domain form |
| `ponymail_private_search_url_template` | `ponymail` | TODO |
| `ponymail_public_search_url_template` | `ponymail` | TODO |
| `ponymail_api_url_template` | `ponymail` | TODO |
| `ponymail_thread_url_template` | `ponymail` | `https://lists.apache.org/thread/<hash>?<list>` |
| `imap_host` | `imap` | TODO: e.g. `imap.example.org` |
| `imap_account` | `imap` | TODO: e.g. `security-triage@example.org` |
| `imap_security_list_folder` | `imap` | TODO: e.g. `INBOX.security-list` |
| `imap_drafts_folder` | `imap` | TODO: e.g. `Drafts` (or leave blank to declare `create_draft` unsupported on this adapter) |
| `mbox_archive_path` | `mbox` | TODO: e.g. `/srv/audit/security-list-2024.mbox` |

## Issue-template fields

The skills' body-field roles map to the following concrete `###`
headings in the project's issue template (the concrete YAML file lives in the
adopter's `<upstream>` repo; the generic role → field contract is in The generic role → GitHub-field
contract lives in
[`../../tools/github/issue-template.md`](../../tools/github/issue-template.md);
the concrete names below are what skills read and write for this
project.

| Role (generic) | Field name | Template type | Required? |
|---|---|---|---|
| `issue-description` | TODO | `textarea` | TODO |
| `public-summary` | TODO | `textarea` | TODO |
| `affected-versions` | TODO | `input` | TODO |
| `security-thread` | TODO | `input` | TODO |
| `public-advisory-url` | TODO | `input` | TODO |
| `reporter-credit` | TODO | `input` | TODO |
| `pr-with-fix` | TODO | `input` | TODO |
| `cwe` | TODO | `input` | TODO |
| `severity` | TODO | `dropdown` | TODO |
| `cve-tool-link` | TODO | `input` | TODO |

## Security workflow configuration

This block declares the **plug-points** that drive every ASF-coupled
assumption in the skills. The defaults shipped here reproduce the
current Apache Airflow security-team behaviour byte-for-byte: an
adopter who copies `projects/_template/` into a fresh `<project-config>/`
and changes nothing in this section ends up with the same workflow
that runs in `airflow-s/airflow-s` today. Non-ASF adopters override
individual fields (CNA tool, mail backend, archive system, governance
gate, etc.) without touching skill bodies — skills resolve these knobs
at run time. Each field carries a `#` comment stating *what it
controls*, the *ASF default*, *when a non-ASF adopter would override
it*, and the *consuming skills* (1-3 most relevant names).

The adapter contracts these blocks reference live under:

- [`../../tools/cve-tool/README.md`](../../tools/cve-tool/README.md) — CNA tool interface (ASF default adapter: `tools/cve-tool-vulnogram/`)
- [`../../tools/mail-archive/README.md`](../../tools/mail-archive/README.md) — public-archive interface (ASF default adapter: `tools/ponymail/`)
- [`../../tools/forwarder-relay/README.md`](../../tools/forwarder-relay/README.md) — inbound-relay interface (ASF default adapter: the ASF-security forwarder shape in `tools/gmail/asf-relay.md`)

### CVE authority

```yaml
cve_authority:
  # Which CNA tool the project uses to allocate, edit, and publish CVE
  # records. Selects the adapter under tools/cve-tool/.
  # ASF default: vulnogram (ASF-hosted Vulnogram instance at
  # cveprocess.apache.org). Non-ASF adopters running their own MITRE
  # CNA pick `mitre-form` or `cve-org-direct`; GHSA-only projects pick
  # `ghsa`; pre-CNA projects pick `none`.
  # Consumed by: security-cve-allocate, security-issue-sync,
  # generate-cve-json.
  tool: vulnogram

  # Front-door allocation URL. Skill prints this and waits for the
  # operator to paste the allocated ID back.
  # ASF default: Vulnogram's ASF allocation endpoint.
  # Override when: pointing at a non-ASF Vulnogram tenant, or any
  # other CNA tool's allocation UI.
  # Consumed by: security-cve-allocate.
  allocate_url: https://cveprocess.apache.org/allocatecve

  # Template for the per-record edit/view URL. `<CVE-ID>` is the
  # placeholder the skill substitutes.
  # ASF default: Vulnogram's cve5 record view.
  # Override when: any non-Vulnogram CNA tool.
  # Consumed by: security-cve-allocate, security-issue-sync.
  record_url_template: https://cveprocess.apache.org/cve5/<CVE-ID>

  # Template for the "Source" tab inside the CNA tool — used when the
  # skill needs to inspect raw CNA_private state.
  # ASF default: Vulnogram cve5 source tab.
  # Override when: the adapter exposes raw record state via a
  # different URL (or leave null if the adapter has no equivalent).
  # Consumed by: security-issue-sync, generate-cve-json.
  source_tab_url_template: https://cveprocess.apache.org/cve5/<CVE-ID>?tab=source

  # Template for the "preview the allocation email" tab in the CNA
  # tool. The Vulnogram default emits an allocation email visible
  # under this URL; null for adapters that don't preview email.
  # ASF default: Vulnogram email preview tab.
  # Consumed by: security-cve-allocate.
  email_preview_url_template: https://cveprocess.apache.org/cve5/<CVE-ID>?tab=email

  # Generic state machine the adapter exposes. Adapters map their
  # tool-native states to this 4-stop sequence; the rest of the
  # workflow speaks only in these terms.
  # ASF default mapping: Vulnogram's DRAFT -> allocated,
  # REVIEW -> review-ready, READY -> publish-ready, PUBLIC -> public.
  # Override when: the adapter has a different state machine — the
  # adapter declares its own mapping in its README.md.
  # Consumed by: security-issue-sync, security-cve-allocate,
  # generate-cve-json.
  states: [allocated, review-ready, publish-ready, public]

  # How "record is now PUBLIC" propagates back to the workflow.
  # `poll` = skill re-fetches the record on a sweep; `webhook` =
  # adapter pushes; `manual` = operator flips a label by hand.
  # ASF default: poll (Vulnogram has no webhook).
  # Override when: a CNA tool offers a webhook (`webhook`) or only a
  # human-driven publication signal (`manual`).
  # Consumed by: security-issue-sync.
  publication_propagation: poll

  # Whether the CNA tool emits an allocation email of its own that
  # the skills should expect to see on the security mailing list.
  # ASF default: true (Vulnogram auto-emails the assigner list).
  # Override when: the adapter is silent on allocation — skills then
  # skip the "wait for Vulnogram email" step.
  # Consumed by: security-cve-allocate.
  emits_allocation_email: true

  # Where the human review of the draft CVE record happens before
  # publication. `mailing-list` = an off-system thread; `github-pr`
  # = a PR on the tracker repo; `none` = no formal review gate.
  # ASF default: mailing-list (PMC reviews on private@).
  # Override when: an adopter wires review into a tracker-repo PR.
  # Consumed by: security-cve-allocate, security-issue-sync.
  reviewer_channel: mailing-list
```

### Governance

```yaml
governance:
  # Who has authority to allocate a CVE on behalf of the project.
  # `pmc-member` = an ASF-style governance committee membership gate;
  # `security-team-member` = looser, anyone on the security team;
  # `maintainer` = any committer; `none` = no formal gate.
  # ASF default: pmc-member (ASF PMC membership via OAuth into
  # Vulnogram).
  # Override when: non-ASF projects with their own authority model.
  # Consumed by: security-cve-allocate, security-issue-sync.
  cve_allocation_gate: pmc-member

  # Label the tracker applies to mark "this account is governance-
  # authorised" — distinct from "security-team member". Skills use
  # this to gate the allocation step.
  # ASF default: "PMC" (matches the existing airflow-s label).
  # Override when: a non-ASF adopter uses a different label name.
  # Consumed by: security-cve-allocate, pr-management-triage.
  gate_label: "PMC"

  # Whether release votes block on outstanding security work. When
  # true, release-manager skills check the security tracker for
  # un-fixed-but-public CVEs before greenlighting a vote.
  # ASF default: true (ASF release process gates on this).
  # Override when: projects with no formal release-vote gate.
  # Consumed by: security-issue-sync, generate-cve-json.
  release_vote_gating: true

  # Private mailing list the governance body uses for escalation,
  # PMC discussions, and "this is bigger than security@" routing.
  # ASF default: private@<project>.apache.org.
  # Override when: non-ASF — point at the equivalent private list
  # or leave null if no such list exists.
  # Consumed by: security-issue-sync, security-issue-invalidate.
  private_governance_list: private@<project>.apache.org

  # GitHub handle (or external contact) the skills cc / @-mention
  # when escalating beyond the security team.
  # ASF default: the PMC chair or designated escalation contact —
  # filled in per-project. Use the `@<handle>` form for GitHub
  # surfaces; an email is acceptable for off-GitHub escalation.
  # Override when: non-ASF — point at the equivalent role-holder.
  # Consumed by: security-issue-sync, pr-management-triage.
  escalation_contact: "@<escalation-contact>"

  # URL of the public committee roster, used for "is this person
  # authorised" checks in the allocation flow.
  # ASF default: ASF committee URL (whimsy/projects/.../committee).
  # Override when: non-ASF — link to the equivalent roster page.
  # Consumed by: security-cve-allocate.
  roster_url: https://projects.apache.org/committee.html?<project>
```

### Security inbox

```yaml
security_inbox:
  # The inbound channel reports land on. `mailing-list` = an SMTP
  # address; `ghsa-inbox` = GitHub Security Advisories private
  # reports; `hackerone` = a HackerOne program inbox;
  # `chat-channel` = e.g. a private Slack; `intake-form` = a
  # web form posting into a tracker.
  # ASF default: mailing-list.
  # Override when: non-ASF projects on GHSA / HackerOne / etc.
  # Consumed by: security-issue-import, security-issue-sync.
  kind: mailing-list

  # The concrete address / channel ID / form URL the inbound channel
  # uses. For `mailing-list`, this is the SMTP address.
  # ASF default: security@<project>.apache.org.
  # Override when: non-ASF — replace with the adopter's inbox.
  # Consumed by: security-issue-import, security-issue-sync,
  # canned-responses templating.
  address: <security-list>

  # The foundation-wide security address that gates the
  # "don't exclude this sender" rule in the inbound importer.
  # Null for non-ASF adopters with no foundation-level inbox.
  # ASF default: security@apache.org (the ASF security team
  # forwards reports here onto project security@ lists).
  # Override when: non-ASF — set to null (or your foundation's
  # equivalent address if one exists).
  # Consumed by: security-issue-import.
  foundation_security_address: security@apache.org

  # Whether reports arrive via a forwarder/relay (an upstream party
  # that triages and re-sends, rather than the reporter mailing the
  # project list directly). When true, the forwarders block below
  # declares the enabled adapters.
  # ASF default: true (the ASF security team relays many reports).
  # Override when: non-ASF projects with no forwarder layer.
  # Consumed by: security-issue-import, gmail/asf-relay (adapter).
  has_forwarder_relay: true

  # Optional Gmail/IMAP search filter used by the inbound importer to
  # scope which threads count as "security inbox messages".
  # ASF default: `list:<security-list-domain>` (Gmail's list-id
  # filter for the project security list).
  # Override when: the mail backend uses a different scoping
  # mechanism (folder, label, etc.).
  # Consumed by: security-issue-import.
  list_filter_query: "list:<security-list-domain>"
```

### Forwarders

```yaml
forwarders:
  # Enabled forwarder/relay adapters. Each name must match an
  # adapter directory under tools/ that conforms to
  # tools/forwarder-relay/README.md.
  # ASF default: [asf-security] — the ASF security team relays
  # reports onto project security@ lists with a known preamble and
  # credit line.
  # Override when: non-ASF — set to [] if no forwarder layer
  # exists, or add the adopter's relay adapter name(s) here.
  # Consumed by: security-issue-import, gmail/asf-relay (adapter).
  enabled: [asf-security]

  # Per-adapter configuration. Keys must match `enabled` entries.
  asf-security:
    # Handle / address the forwarder sends from. Skills use this to
    # detect "this is a relayed message, not a direct report".
    # ASF default: security@apache.org.
    # Override when: a different upstream relay address.
    # Consumed by: gmail/asf-relay, security-issue-import.
    contact_handle: security@apache.org

    # Regex matched against the message body to confirm a message
    # really is a relay (not just a CC'd address).
    # ASF default: the ASF preamble — "Dear PMC, The security
    # vulnerability report..."
    # Override when: a different relay's preamble shape.
    # Consumed by: gmail/asf-relay, security-issue-import.
    preamble_match: "^Dear PMC,\\s+The security vulnerability report"

    # Rule the adapter uses to lift the original reporter's credit
    # line out of the relayed body. Adapters define their own
    # extraction shape; see tools/forwarder-relay/README.md.
    # ASF default: the existing ASF-security credit extraction (the
    # "Reported by: <name> <<email>>" line near the top of the
    # forwarded body).
    # Override when: a different relay shape.
    # Consumed by: gmail/asf-relay, security-issue-import.
    credit_extraction_rule: "first-line-matching:^Reported by:\\s+(.+)$"
```

### Mail provider

```yaml
mail_provider:
  # Primary mail backend the skills read inbound mail from and write
  # drafts into. Adapters live under tools/<backend>/.
  # ASF default: gmail-mcp (triager Gmail account via the Gmail MCP
  # adapter at tools/gmail/).
  # Override when: a non-ASF adopter uses an IMAP triager mailbox
  # (`imap`), an Outlook inbox (`outlook`), or a forum-style
  # inbound channel (`discourse`).
  # Consumed by: security-issue-import, security-issue-sync,
  # security-issue-invalidate (draft replies).
  primary: gmail-mcp

  # Read-only fallback backend used when the primary can't reach a
  # thread (e.g. message older than the Gmail retention window).
  # `none` means no fallback — operations that fail on the primary
  # surface a hard error instead of trying a secondary.
  # ASF default: ponymail (read-only ASF archive backstop).
  # Override when: non-ASF adopters typically set this to `none`
  # or to their own archive adapter (hyperkitty, mbox, ...).
  # Consumed by: security-issue-sync, security-issue-import.
  fallback: ponymail
```

### Archive system

```yaml
archive_system:
  # Public mailing-list / forum archive the project's advisories
  # eventually surface on. Adapter selection — drives URL shapes
  # and thread-fetch verbs.
  # ASF default: ponymail (lists.apache.org).
  # Override when: non-ASF adopters on hyperkitty (Mailman 3),
  # discourse, google-groups, github-discussions, or none.
  # Consumed by: security-issue-sync, generate-cve-json.
  kind: ponymail

  # Domain the public lists live under — used to assemble per-list
  # URLs (`<list>@<list_domain>`) when the archive search needs
  # qualified addresses.
  # ASF default: <project>.apache.org (e.g. airflow.apache.org).
  # Override when: non-ASF — the adopter's public-list domain.
  # Consumed by: security-issue-sync, generate-cve-json.
  list_domain: <project>.apache.org

  # Template the search-thread verb assembles. Placeholders:
  # `{list}` (list short name), `{year}`, `{month}`, `{query}`.
  # ASF default: ponymail's `list?` search endpoint.
  # Override when: a different archive's search URL shape.
  # Consumed by: security-issue-sync (search before announce),
  # generate-cve-json (references[] assembly).
  search_url_template: "https://lists.apache.org/list?{list}:{year}-{month}:{query}"

  # Template for the archive's programmatic thread-fetch endpoint
  # (used by the mail-archive adapter's fetch_thread_by_url).
  # ASF default: ponymail's thread.lua API.
  # Override when: a different archive — hyperkitty has a different
  # API shape; discourse exposes JSON on `/t/<id>.json`; etc.
  # Consumed by: tools/ponymail (adapter), security-issue-sync.
  api_query_url_template: "https://lists.apache.org/api/thread.lua?list={list}&domain={list_domain}&id={thread_id}"

  # The URL the skill polls to detect "advisory has been announced
  # publicly" — i.e. the archive page where the announcement thread
  # appears once published.
  # ASF default: lists.apache.org `users` list page.
  # Override when: the announcement surfaces on a different list /
  # forum.
  # Consumed by: security-issue-sync.
  advisory_publication_signal_url: "https://lists.apache.org/list.html?<users-list>"
```

### Tracker

```yaml
tracker:
  # Platform the tracker repo lives on. Selects the API adapter
  # (gh CLI today; gitlab CLI / forgejo / jira REST in the future).
  # ASF default: github (airflow-s/airflow-s).
  # Override when: non-ASF adopters on gitlab, gitea, jira, forgejo.
  # Consumed by: every skill that touches the tracker.
  platform: github

  # Project-board backend on the tracker platform. Drives the
  # board-reconciliation step in the triage skills.
  # ASF default: github-projects-v2.
  # Override when: gitlab-board for a GitLab tracker, or `none`
  # if the adopter doesn't run a board at all.
  # Consumed by: pr-management-triage, security-issue-sync,
  # security-issue-triage.
  board: github-projects-v2

  # Visibility of the tracker repo. Drives "may this URL leak
  # publicly" guards in the canned-responses + CVE-JSON references.
  # ASF default: private (tracker existence is itself secret per
  # the AGENTS.md rules).
  # Override when: a project that runs its security tracker openly.
  # Consumed by: every skill that emits URLs to outside surfaces.
  visibility: private

  # Whether the reporter can see the tracker issue once opened.
  # ASF default: false (private tracker — reporter never gets a
  # link).
  # Override when: a public tracker where the reporter is added as
  # a collaborator.
  # Consumed by: security-issue-import, canned-responses templating.
  reporter_has_access: false

  # Whether the tracker drives a board / kanban view. When false,
  # skills skip column transitions entirely.
  # ASF default: true.
  # Override when: an adopter using only labels + milestones.
  # Consumed by: pr-management-triage, security-issue-sync.
  project_board_enabled: true

  # Template the skills use to compose a "link back to the skill
  # docs as seen in this repo" URL. `<skill>` is the slug under
  # .claude/skills/.
  # ASF default: tracker default branch on github.com.
  # Override when: a non-GitHub tracker — replace with the platform's
  # equivalent file-view URL shape.
  # Consumed by: pr-management-mentor, canned-responses (footer link).
  skill_url_template: "https://github.com/<tracker>/blob/main/.claude/skills/<skill>/SKILL.md"

  # Tracker body-field heading names — the literal `###` headings
  # the skills read and write under in the tracker's issue
  # template. The skill code refers to these by *role*; this map
  # binds role -> concrete heading.
  # ASF default: the existing airflow-s headings.
  # Override when: an adopter with a different issue-template shape
  # — change the headings here, not the skills.
  # Consumed by: every skill that reads/writes the issue body.
  body_fields:
    cve_link: "CVE tool link"
    mailing_thread: "Mailing list thread URL"
    affected_versions: "Affected versions"

  # Tracker labels — role -> concrete label name. Skills speak in
  # roles; this map binds role -> literal label.
  # ASF default: the airflow-s label set.
  # Override when: a tracker with a different label vocabulary.
  # Consumed by: security-issue-triage, security-issue-sync,
  # pr-management-triage.
  labels:
    security_marker: "security"
    needs_triage: "needs triage"
    pr_open: "pr created"
    pr_merged: "pr merged"
    cve_allocated: "cve allocated"
    not_cve_worthy: "not cve worthy"
```

### Scope detection

```yaml
scope_detection:
  # Whether the project distinguishes scope sub-products (e.g.
  # airflow vs providers vs chart). When false, every issue maps
  # to the single product declared in the `product` block.
  # ASF/Airflow default: true.
  # Override when: a single-artifact project — set to false and
  # drop the labels map.
  # Consumed by: security-issue-triage, generate-cve-json,
  # security-issue-sync.
  enabled: true

  # Scope label -> sub-product mapping. Each entry binds a tracker
  # label to the CVE `product` field value, the package-name shape
  # the advisory will use, and the upstream path prefix the skill
  # uses to confirm a PR really touches that scope.
  # ASF/Airflow default: the three existing scope labels.
  # Override when: a project with different scope axes — keep the
  # `product`/`packageName`/`path_prefix` triad shape.
  # Consumed by: security-issue-triage, generate-cve-json.
  labels:
    airflow:
      product: "Apache Airflow"
      packageName: "apache-airflow"
      path_prefix: "^(airflow-core/|airflow/(?!providers/)|airflow-ctl/)"
    providers:
      product: "Apache Airflow"
      packageName: "apache-airflow-providers-<provider>"
      path_prefix: "^providers/"
    chart:
      product: "Apache Airflow Helm Chart"
      packageName: "apache-airflow-helm-chart"
      path_prefix: "^chart/"
```

### Release process

```yaml
release_process:
  # Cascade of sources skills consult to resolve "who is RM for
  # version X". First match wins; later entries are tried only if
  # earlier entries fail to surface a handle.
  # ASF default: the project's release-trains.md roster file, then
  # the wiki release-managers page, then the dev@ mailing-list
  # VOTE/RESULT threads.
  # Override when: non-ASF — collapse to whatever roster source the
  # project keeps. Drop entries that don't apply.
  # Consumed by: security-issue-sync, security-issue-fix (PR
  # reviewer assignment).
  release_manager_lookup_cascade:
    - kind: roster_file
      path: "release-trains.md"
    - kind: wiki_url
      url: "https://cwiki.apache.org/confluence/display/<PROJECT>/Release+Managers"
    - kind: mailing_list_vote_thread
      list: "<dev-list>"

  # Artifact registries where the project publishes releases — the
  # skills cross-check that a fix has shipped here before flipping
  # the issue to "fix released".
  # ASF default: [pypi, artifacthub] (Python wheels + Helm chart).
  # Override when: non-Python projects (`maven`, `npm`, ...) or
  # projects that publish elsewhere.
  # Consumed by: security-issue-sync, generate-cve-json
  # (references[] population).
  artifact_registries: [pypi, artifacthub]

  # Milestones the skills treat as "stale" — i.e. anything still
  # pinned to one of these is overdue for re-targeting. Listed as
  # exact milestone-name matches.
  # ASF/Airflow default: the current airflow-s stale-milestone list.
  # Override when: replace with the adopter's stale-milestone names.
  # Consumed by: security-issue-sync, pr-management-triage.
  stale_milestones:
    - "Airflow 2.x"
    - "Airflow 2.10.x"
    - "Airflow 3.0.x"

  # Whether the upstream repo uses a newsfragments / changelog
  # fragment tool, and which one. Skills hook this when proposing
  # a fix — the fix PR must include a fragment.
  # ASF/Airflow default: enabled with towncrier.
  # Override when: projects without a fragment tool (`enabled:
  # false`) or with a different tool (reno, changie, ...).
  # Consumed by: security-issue-fix, issue-fix-workflow.
  newsfragments:
    enabled: true
    tool: towncrier
```

### Roster

```yaml
roster:
  # Source of truth for the security team membership and the
  # bare-name -> handle mapping. Selects how the skills resolve
  # "is X on the security team".
  # `tracker-collaborators` = read the tracker repo's collaborator
  # list; `roster-file:<path>` = read a checked-in file (path
  # relative to <project-config>/); `inline:<list>` = a literal
  # list spelled out below.
  # ASF default: roster-file:release-trains.md (the canonical
  # source for the Airflow security team).
  # Override when: non-ASF — pick whichever shape matches the
  # adopter's source of truth.
  # Consumed by: security-issue-sync, security-cve-allocate,
  # security-issue-triage.
  source: roster-file:release-trains.md

  # Bare-name -> @handle mapping. Mailing-list threads frequently
  # reference contributors by first name only; this map binds
  # those bare names to GitHub handles so the skills can produce
  # @-mentions on the tracker.
  # ASF/Airflow default: the existing airflow-s bare-name map.
  # Override when: adapt to the adopter's roster — add/remove
  # entries as needed.
  # Consumed by: security-issue-sync, pr-management-mentor.
  bare_name_handles:
    Jarek: "@potiuk"
    Ash: "@ashb"
    Kaxil: "@kaxil"
    Ephraim: "@ephraimbuddy"
    Jed: "@jedcunningham"

  # Release-manager handles, ordered by recency of train ownership.
  # First handle is the current default RM; the rest are the
  # historical RMs the skill falls back to when assigning legacy
  # trains.
  # ASF/Airflow default: the current RM order from release-trains.md.
  # Override when: keep in sync with `release-trains.md`.
  # Consumed by: security-issue-sync, security-issue-fix.
  release_managers:
    - "@ephraimbuddy"
    - "@jedcunningham"
    - "@potiuk"
    - "@kaxil"
```

### Product

```yaml
product:
  # Human-readable product name — what lands in the CVE record's
  # `product` field and what canned responses address the product
  # as.
  # ASF/Airflow default: Airflow.
  # Override when: any other project — replace with the canonical
  # short name.
  # Consumed by: generate-cve-json, canned-responses templating.
  name: Airflow

  # Package name shape for the primary artifact — used by the
  # advisory templating and the CVE JSON `affected[].packageName`.
  # ASF/Airflow default: apache-airflow (PyPI distribution).
  # Override when: any other project — use the package-registry
  # name (PyPI / npm / Maven / ...).
  # Consumed by: generate-cve-json, canned-responses templating.
  package_name: apache-airflow

  # Regex matched against changed paths in an upstream PR to
  # confirm "this PR really touches the product". Used as a
  # backstop sanity check in the fix flow.
  # ASF/Airflow default: starts with `airflow` (matches
  # airflow/, airflow-core/, airflow-ctl/, etc.).
  # Override when: any other repo layout.
  # Consumed by: security-issue-fix, pr-management-triage.
  code_pointer_path_prefix: "^airflow"

  # Prefixes the title-normalization skill strips when normalising
  # an inbound subject line into a CVE title. Matched at the start
  # of the subject, case-insensitively, in order; the first match
  # wins and is removed.
  # ASF/Airflow default: the existing airflow-s strip cascade.
  # Override when: any other project — replace with the adopter's
  # subject-prefix conventions.
  # Consumed by: title-normalization, generate-cve-json,
  # canned-responses templating.
  subject_prefix_strip:
    - "[SECURITY]"
    - "[Security Report]"
    - "Re:"
    - "Fwd:"
    - "Airflow:"
    - "Apache Airflow:"

  # Prefix the affected-versions extractor looks for in mailing-list
  # bodies — reporters typically write "Airflow 2.10.0 is affected".
  # Skill strips this prefix to leave the bare version literal.
  # ASF/Airflow default: "Airflow".
  # Override when: any other product — the literal product token
  # reporters use in version expressions.
  # Consumed by: security-issue-sync, generate-cve-json.
  affected_version_extract_prefix: "Airflow"
```

## Pointers to sibling files

- [`release-trains.md`](release-trains.md) — fast-moving release state, release-manager attribution, security-team roster.
- [`milestones.md`](milestones.md) — milestone naming conventions.
- [`scope-labels.md`](scope-labels.md) — scope label → CVE product mapping.
- [`security-model.md`](security-model.md) — Security-Model URL + anchors.
- [`title-normalization.md`](title-normalization.md) — CVE title strip cascade.
- [`fix-workflow.md`](fix-workflow.md) — fork / toolchain / commit-trailer specifics.
- [`naming-conventions.md`](naming-conventions.md) — project-specific editorial rules.
- [`canned-responses.md`](canned-responses.md) — reporter-facing reply templates.
- [`README.md`](README.md) — project file index + onboarding checklist.
