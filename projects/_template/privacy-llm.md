<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Privacy-LLM configuration](#privacy-llm-configuration)
  - [Currently configured LLM stack](#currently-configured-llm-stack)
  - [Approved third-party endpoints (opt-in)](#approved-third-party-endpoints-opt-in)
  - [Private mailing lists for this project](#private-mailing-lists-for-this-project)
  - [Redaction configuration](#redaction-configuration)
    - [Collaborator source](#collaborator-source)
    - [Collaborator exemption](#collaborator-exemption)
    - [Redaction field types](#redaction-field-types)
    - [How the knobs are applied](#how-the-knobs-are-applied)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

<!-- Adopter template — copy this file into <project-config>/privacy-llm.md
     and customise per the recipes in
     ../../docs/setup/privacy-llm.md.

     The default below (Variant 1 — Claude Code only) is the
     starting state for a fresh adoption. Adopting projects that
     wire in additional LLMs (Ollama, Bedrock, Anthropic direct,
     etc.) replace the *Currently configured LLM stack* section
     and populate *Approved third-party endpoints* per the recipe
     for that variant. -->

# Privacy-LLM configuration

This file declares which LLM endpoints this project's framework
skills are allowed to route private data through, and which
mailing lists count as private.

The contract behind these declarations lives in the framework at
[`tools/privacy-llm/models.md`](../../tools/privacy-llm/models.md);
the per-variant setup recipes are at
[`docs/setup/privacy-llm.md`](../../docs/setup/privacy-llm.md).

## Currently configured LLM stack

- Claude Code (the agent running framework skills)

<!-- Add additional LLMs here, one per line, with the endpoint URL
     or provider name and the model name in parentheses. Example:

       - Local Ollama at http://127.0.0.1:11434/  (model: llama3.1:8b)

     For a Claude-Code-only deployment (Variant 1), leave this
     section as-is.  -->

## Approved third-party endpoints (opt-in)

(none — Claude Code is the only LLM)

<!-- Populate this section when adding any LLM that is NOT in
     the framework's default-approved set
     (Claude Code itself / *.apache.org / 127.0.0.1 or localhost
     local inference). Each entry needs:

       - Endpoint URL or provider product name
       - Data-residency contract: <link or short identifier>
       - Approved-by: <PMC-member-initials> <YYYY-MM-DD>

     A `<project-config>/privacy-llm.md` that lists an opt-in
     endpoint without the Approved-by line will be flagged as
     incomplete by the privacy-llm-check helper. -->

## Private mailing lists for this project

- `<private-list>`

<!-- List every PMC-private foundation list this project's
     security team reads. The framework's privacy-llm gate
     refuses to fetch from these lists unless the active LLM
     stack above is fully approved.

     `<security-list>` (the project's security@ list) is **not**
     listed here — its body is treated as non-private; only
     third-party PII (non-reporter, non-collaborator individuals
     named in the body) is redacted (per
     ../../tools/privacy-llm/pii.md). -->

## Redaction configuration

These knobs tune how skills apply the PII redactor (per
[`../../tools/privacy-llm/wiring.md`](../../tools/privacy-llm/wiring.md))
when reading `<security-list>` content. Defaults are listed in
parentheses; uncomment a row to override.

### Collaborator source

```text
# collaborator_source: <tracker>
```

(default: read from `<project-config>/project.md → tracker_repo`).
The repository whose collaborator list is treated as "already
public/known" and therefore NOT redacted. Override here if your
project tracks security-team membership in a different repo
(e.g. a parent-org roster repo).

### Collaborator exemption

```text
# collaborator_exemption: enabled
```

(default: `enabled` — collaborators are NOT redacted; their
identity is already public via the tracker's collaborator list).

Set to `disabled` for a stricter posture: every non-reporter
individual gets redacted, including collaborators. Use when
your PMC has decided that even public collaborator identity
should not flow through LLMs as a defence-in-depth measure.

### Redaction field types

```text
# redaction_field_types: name, email, phone, ip, handle, address
```

(default: all six types are redacted). Remove a type from this
list to disable redaction for that field type. Rare — most
projects keep all six on. Examples of when an adopter might
narrow:

- A project whose security reports never include phone numbers
  (and where redacting phone-shaped strings might cause false
  positives in code excerpts) might drop `phone`.
- A project with a strict "treat public IPs as non-PII" policy
  might drop `ip`. The framework already excludes IPs that
  identify a vulnerable production server (see
  [`../../tools/privacy-llm/pii.md`](../../tools/privacy-llm/pii.md))
  but this knob is the broader override.

### How the knobs are applied

The redactor itself reads no config file — these knobs are
applied by **the skill** at filter time (Step 3 of the
[redact-after-fetch protocol](../../tools/privacy-llm/wiring.md#redact-after-fetch-protocol)),
before `pii-redact --field` arguments are constructed. A skill
that does not respect a knob is a framework bug; report it on
[`apache/magpie`](https://github.com/apache/magpie).
