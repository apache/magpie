<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [tools/forwarder-relay/ — adapter contract](#toolsforwarder-relay--adapter-contract)
  - [Prerequisites](#prerequisites)
  - [What "a relay message" means](#what-a-relay-message-means)
  - [Today's adapters](#todays-adapters)
    - [Sub-skill consumers](#sub-skill-consumers)
  - [Interface](#interface)
    - [`detect(message) -> adapter_name | null`](#detectmessage---adapter_name--null)
    - [`extract_credit(body) -> {name, kind, raw_string} | null`](#extract_creditbody---name-kind-raw_string--null)
    - [`contact_handle` (attribute)](#contact_handle-attribute)
    - [`preamble_match` (attribute)](#preamble_match-attribute)
    - [`reporter_addressing_block(...) -> string`](#reporter_addressing_block---string)
    - [`via_forwarder_question_mode` (attribute)](#via_forwarder_question_mode-attribute)
  - [Skills that consume this contract](#skills-that-consume-this-contract)
  - [ASF default — ASF Security forwarder](#asf-default--asf-security-forwarder)
    - [Why `@raboof` is the contact handle today](#why-raboof-is-the-contact-handle-today)
  - [Configuration](#configuration)
  - [Cross-references](#cross-references)
  - [What this contract does NOT cover](#what-this-contract-does-not-cover)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# tools/forwarder-relay/ — adapter contract

**Capability:** contract:report-relay

**Kind:** interface

**Vendor:** agnostic

A forwarder-relay adapter is a pluggable seam that teaches the
security skills how to recognise an inbound report that arrived
**through a relay** (someone else forwarded the original
reporter's message to the project), how to extract the
original-reporter credit from the relayed body, and how to route
reporter-facing drafts back through the same relay channel. This
file defines what the skills expect from an adapter, what the
single shipping adapter (ASF Security relay) does today, and how
adopters declare which adapters are enabled in
[`<project-config>/project.md`](../../projects/_template/project.md).

The framework default is the ASF Security relay adapter, which is
the only one shipping in the tree today. The contract exists so
that adopters whose security inbox sits behind huntr.com,
HackerOne, GitHub Security Advisories, an internal SOC, or any
other forwarding service can plug in an adapter without
patching the skill bodies.

## Prerequisites

- **Runtime:** None — this is a prose adapter *contract*; no executable
  ships in this directory. The interface is implemented by the security
  skills that dispatch through it.
- **CLIs:** None.
- **Credentials / auth:** None directly; consuming skills authenticate
  through the mail-source layer (e.g. Gmail) for inbound reads and drafts.
- **Network:** None directly — the contract performs no I/O. Mail
  fetch/draft happens in the [`tools/mail-source`](../mail-source/contract.md) layer.

## What "a relay message" means

Many security reports never reach the project's security inbox
directly. The original reporter files with a third-party broker —
the ASF Security team at `security@apache.org`, huntr.com,
HackerOne, GHSA — and the broker forwards the report to the
project. On the inbound thread, the broker is the visible
correspondent; the actual reporter is one hop away, reachable
only by asking the broker to relay messages back.

This matters for three skill behaviours:

1. **Credit extraction.** The `From:` header of a relay message
   names the broker, not the reporter. Per the bot/AI credit
   policy in
   [`tools/cve-tool-vulnogram/bot-credits-policy.md`](../cve-tool-vulnogram/bot-credits-policy.md)
   the tracker's *Reporter credited as* field must name the
   external reporter, so the skill has to pull the name from the
   message body (the broker's preamble convention) instead of
   from the header.
2. **Reply routing.** Drafts intended for the reporter must go
   through the broker — but addressed to the broker, with the
   reporter-facing content folded inside as a paste-ready block
   the broker can copy verbatim into their reply to the reporter.
   See [`tools/gmail/asf-relay.md`](../gmail/asf-relay.md) for
   the paste-ready-block convention introduced in PR #375.
3. **Question batching.** The project should not pester the
   broker with every workflow chatter event. The
   [`docs/security/forwarder-routing-policy.md`](../../docs/security/forwarder-routing-policy.md)
   policy doc — which consumes this contract — defines which
   milestones get relayed and which stay on the project side.

A forwarder-relay adapter is the seam that lets each skill ask
the right adapter "is this a relay message? whose credit is in
it? how do I draft back through it?" without hard-coding the
ASF preamble or the `@apache.org` sender pattern.

## Today's adapters

| Adapter | Status | Inbound channel | Reference doc |
|---|---|---|---|
| `asf-security` | shipping | Mail from `security@apache.org` or a personal `@apache.org` address with the ASF forwarding preamble | [`tools/gmail/asf-relay.md`](../gmail/asf-relay.md) |
| `huntr-relay` | placeholder | Mail from huntr.com's notification address with the huntr disclosure preamble | not implemented — contract slot only |
| `hackerone-relay` | placeholder | Mail from HackerOne's notification address with the HackerOne handoff preamble | not implemented — contract slot only |
| `ghsa-relay` | placeholder | Mail forwarded from a GHSA private report by the GitHub notification system | not implemented — contract slot only |
| `custom` | escape hatch | Adopter-specific broker (internal SOC, third-party VRP, mailing-list relay) | adopter ships their own adapter dir |

Only `asf-security` is wired in. The other rows are reserved
contract slots: when an adopter needs huntr.com or HackerOne
support, they implement an adapter directory under
`tools/forwarder-relay/<name>/` that satisfies the interface
below, and add `<name>` to the `forwarders.enabled` list in
their `<project-config>/project.md`.

The ASF-security adapter's `preamble_match` regex,
`credit_extraction_rule`, `contact_handle` (the `@raboof`
default, lifted into project.md
`forwarders.asf-security.contact_handle`), and
`reporter_addressing_block` convention all live in
[`tools/gmail/asf-relay.md`](../gmail/asf-relay.md). This is
the only forwarder adapter shipping today; the contract above
describes the interface for additional adapters.

### Sub-skill consumers

ASF adopters install the optional sub-skill
[`security-issue-import-via-forwarder`](../../skills/security-issue-import-via-forwarder/SKILL.md)
to enable forwarder-aware handling. The sub-skill consumes the
`forwarders.enabled` config knob from
[`<project-config>/project.md`](../../projects/_template/project.md)
and runs after the main classification cascade in
`security-issue-import`, `security-issue-invalidate`, and
`security-issue-sync`. Generic skill bodies no longer carry
the ASF-relay row inlined in their main classification tables
— they reference the sub-skill as the *"follow this if
forwarder mode is enabled"* extension instead.

## Interface

A forwarder-relay adapter exposes the following operations. Skills
dispatch through this interface; they do not import adapter
internals directly.

### `detect(message) -> adapter_name | null`

Given a fetched mail-source message (`From`, `Subject`,
`Body`, `Date`, `Message-ID`, headers), return the adapter's
own name if the message is a relay message handled by this
adapter, or `null` if not.

Detection is the OR of two signals:

* **Sender pattern.** A regex or set-membership check against
  the `From:` address. ASF Security: `security@apache.org` OR
  any `*@apache.org` address. huntr: huntr.com's outbound
  notification address. HackerOne: HackerOne's notification
  address.
* **Preamble match.** A regex against the first ~400 characters
  of the message body, anchored to the broker's standard
  forwarding header. ASF Security: *"Dear PMC, The security
  vulnerability report has been received by the Apache Security
  Team …"*.

Both signals are evaluated; either one matching is sufficient,
but the adapter MAY require both for higher-confidence cases.
The skill calls each enabled adapter's `detect()` in the order
listed under `forwarders.enabled`; first non-null wins.

**Lifecycle:** called by `security-issue-import` Step 3
(classification), and by `security-issue-sync` Step 2b when
re-reading an existing tracker's inbound thread for routing
decisions.

### `extract_credit(body) -> {name, kind, raw_string} | null`

Given the relay-message body, extract the original reporter's
credit. Returns:

* `name` — the human-readable reporter name as it appears in
  the body. Used verbatim in the tracker's *Reporter credited
  as* field unless the reporter later requests a different
  rendering through a credit-preference exchange.
* `kind` — one of `human` (named individual), `tool`
  (automated scanner like `bugbunny.ai`, `protectai/modelscan`),
  `service` (a broker / VRP / SOC operating on someone else's
  behalf). Drives the bot-credit policy gate in
  [`tools/cve-tool-vulnogram/bot-credits-policy.md`](../cve-tool-vulnogram/bot-credits-policy.md).
* `raw_string` — the exact substring lifted from the body
  (e.g. *"This vulnerability was discovered and reported by
  bugbunny.ai"*). Stored so a later sync can diff against the
  current tracker field and detect that the reporter has been
  manually overridden.

Returns `null` when the body does not contain a credit line in
the adapter's expected shape. The skill then surfaces a "credit
unknown — please confirm before drafting the receipt" prompt
rather than guessing.

**Lifecycle:** called by `security-issue-import` Step 4 (field
population for the new tracker body), and by
`security-issue-sync` Step 2b when reconciling the tracker
field against the latest read of the thread.

### `contact_handle` (attribute)

The GitHub-style handle (or back-channel identifier) of the
relay contact the skills should `@mention` when proposing a
draft. For ASF Security this is currently `@raboof` (Arnout
Engelen, the on-duty ASF Security liaison); for huntr the
handle would be huntr's program-issued contact. Lifted into
config now so the skill body never hard-codes a name.

The handle MAY be a list of fallbacks (`[@raboof,
@securityasf-rota]`) for adapters whose contact rotates; the
skill picks the first available one and surfaces the chosen
handle in the proposal recap.

### `preamble_match` (attribute)

The regex used by `detect()`. Exposed as a read-only attribute
so that:

* `security-issue-import` can print the matched preamble in its
  Step 3 classification proposal ("detected as ASF Security
  relay because the body starts with `<matched snippet>`"),
  giving the human reviewer a one-line "yes this looks right"
  affordance;
* the test harness in
  [`tools/skill-and-tool-validator/`](../skill-and-tool-validator/)
  can replay sample bodies through the adapter and assert the
  detect outcome.

### `reporter_addressing_block(...) -> string`

Render the paste-ready block convention introduced in
[`tools/gmail/asf-relay.md`](../gmail/asf-relay.md) — the
fenced block addressed to the reporter in the project's voice,
signed *"<project> security team"*, inside a wrapper addressed
to the forwarder asking them to forward it verbatim. The
adapter owns the exact wrapper wording; the inner reporter
block is built by the calling skill and passed in.

Parameters:

* `forwarder_first_name` — for the *"Hi <name>"* salutation
  on the wrapper.
* `reporter_first_name` — for the *"Hello <name>"* salutation
  on the inner block, when known.
* `links` — list of `(label, url)` pairs (GHSA URL, CVE
  record URL, advisory URL) the wrapper prints near the top
  so the forwarder can one-click context-switch on their side.
* `inner_body` — the project's reporter-facing text. The
  adapter wraps it in the paste-ready block; it does not
  modify the inner content.

The adapter's responsibility is the wrapper shape: where the
links go, how the inner block is fenced, how the signature
attaches. The reason this is in the adapter rather than in
the skill is that different brokers have different forwarding
conventions — huntr.com expects the inner block to be a
markdown comment that pastes back into their UI; ASF Security
expects a `---`-fenced plaintext block. One skill body, many
adapter renderings.

**Lifecycle:** called by `security-issue-import` Step 7
(receipt-of-confirmation draft), by `security-cve-allocate`
Step 4 (CVE-allocation notification draft), by
`security-issue-sync` Step 2b (status-update drafts), and by
`security-issue-invalidate` Step 5d (invalidation notice draft).

### `via_forwarder_question_mode` (attribute)

A boolean signalling how the adapter prefers credit-preference
questions to be handled:

* `true` — fold the credit-preference question into the
  **same** receipt-of-confirmation draft, addressed to the
  reporter via the paste-ready block. The forwarder makes one
  forward-and-paste action total. This is the right default
  for adapters where the broker prefers not to be a question
  router (ASF Security: yes).
* `false` — send the credit-preference question on a
  **separate** draft, framed as a back-channel request to the
  forwarder (*"please ask the reporter their credit
  preference"*). This is appropriate for adapters where the
  broker actively reviews each exchange (some HackerOne
  programs).

The skill body branches on this attribute in
`security-issue-import` Step 7 and `security-cve-allocate`
Step 4 instead of carrying an `if asf_relay:` check inline.

## Skills that consume this contract

| Skill | Step | What the skill calls |
|---|---|---|
| [`security-issue-import`](../../skills/security-issue-import/SKILL.md) | Step 3 — classification | `detect()` on every enabled adapter; the first non-null return classifies the candidate as a relay import |
| `security-issue-import` | Step 4 — field population | `extract_credit()` for the *Reporter credited as* field |
| `security-issue-import` | Step 7 — receipt-of-confirmation draft | `reporter_addressing_block()` + `via_forwarder_question_mode` to fold the credit-preference question |
| [`security-issue-sync`](../../skills/security-issue-sync/SKILL.md) | Step 2b — draft routing | `contact_handle` + `reporter_addressing_block()` for any reporter-facing draft (CVE-allocated, fix-merged, advisory-shipped) on a relay tracker |
| [`security-issue-invalidate`](../../skills/security-issue-invalidate/SKILL.md) | Step 5d — ASF-relay branch | `reporter_addressing_block()` for the polite-but-firm invalidation notice routed through the forwarder |
| [`security-cve-allocate`](../../skills/security-cve-allocate/SKILL.md) | Step 4 — dual-mode draft | `via_forwarder_question_mode` to decide whether the CVE-allocation draft folds in the credit-preference ask or sends it separately |
| [`tools/gmail/asf-relay.md`](../gmail/asf-relay.md) | reference doc for the shipping adapter | this whole file is the formal contract that `asf-relay.md` documents prose-style |

## ASF default — ASF Security forwarder

The ASF Security adapter is the one shipping today. Its
parameter values, lifted out of skill bodies and into
`<project-config>/project.md`, are:

```yaml
forwarders:
  enabled:
    - asf-security
  asf-security:
    sender_pattern: '(security@apache\.org|.+@apache\.org)'
    preamble_match: 'Dear PMC,\s+The security vulnerability report has been received by the Apache Security Team'
    credit_extraction_rule:
      # The ASF forwarding template ends with a credit line in one of these shapes.
      patterns:
        - 'This vulnerability was discovered and reported by (?P<credit>.+?)\.'
        - 'Credit:\s+(?P<credit>.+?)$'
        - 'Reported by:\s+(?P<credit>.+?)$'
      kind_hints:
        # Substring matches on the extracted name to classify kind.
        tool: ['\.ai\b', 'bot\b', 'scanner\b']
        service: ['security team\b', 'soc\b']
        # default: human
    contact_handle: '@raboof'   # ASF Security on-duty liaison; lift to a rota when one exists
    via_forwarder_question_mode: true
    reporter_addressing_block:
      wrapper_salutation: 'Hi <forwarder-first-name>,'
      links_section: true        # GHSA / CVE / advisory URLs on their own lines near the top
      fence: '---'               # `---`-fenced plaintext block
      inner_salutation: 'Hello <reporter-first-name>,'
      inner_signature: '<project> security team'
      wrapper_signoff: 'Thanks,\n<sender>'
```

The exact shape of the paste-ready block is defined in
[`tools/gmail/asf-relay.md`](../gmail/asf-relay.md) under the
*"Reporter-facing content goes as a ready-to-paste block, not as
a third-person ask"* rule, with the worked GHSA / CVE example.

### Why `@raboof` is the contact handle today

Arnout Engelen (`@raboof`, `engelen@apache.org`) is the ASF
Security team member who currently triages relayed reports for
the projects this framework's reference adopter belongs to. The
handle is lifted into config rather than hard-coded so that:

* a future on-duty rota can declare a list (`[@raboof,
  @next-on-duty, @asf-security-rota]`) without touching skill
  bodies;
* adopters whose ASF Security liaison is a different individual
  declare their own handle locally;
* the handle is reviewable in one place during a security-team
  rotation hand-off instead of being scattered across draft
  templates.

## Configuration

The adopter declares enabled adapters in
[`<project-config>/project.md`](../../projects/_template/project.md)
under the `forwarders` block:

```yaml
forwarders:
  enabled:
    - asf-security           # default; ships with framework
    # - huntr-relay          # placeholder — uncomment when implemented
    # - hackerone-relay      # placeholder — uncomment when implemented
  asf-security:
    contact_handle: '@raboof'
    via_forwarder_question_mode: true
    # sender_pattern / preamble_match / credit_extraction_rule
    # inherit framework defaults unless the adopter overrides
```

The framework ships sensible defaults for every key under
`asf-security`. An adopter typically only overrides
`contact_handle` (their liaison) and possibly the
`sender_pattern` (if they accept relays from a wider set of
addresses than just `*@apache.org`).

## Cross-references

* **Policy** —
  [`docs/security/forwarder-routing-policy.md`](../../docs/security/forwarder-routing-policy.md)
  defines *when* via-forwarder mode applies on a tracker and
  *which* milestones get relayed. The adapter contract here is
  the mechanism; that doc is the policy that drives it.
* **Drafting convention** —
  [`tools/gmail/asf-relay.md`](../gmail/asf-relay.md) carries
  the prose explanation of the paste-ready block, the clickable
  external-reference URL rule, and the threading semantics for
  relay drafts. The contract surfaces those rules as an
  interface; the prose file remains the human-readable
  reference for the shipping adapter.
* **Bot-credit gate** —
  [`tools/cve-tool-vulnogram/bot-credits-policy.md`](../cve-tool-vulnogram/bot-credits-policy.md)
  reads the `kind` field returned by `extract_credit()` to
  decide whether a CVE record should list the credit as a tool
  / organisation rather than an individual.
* **Mail-source layer** — this contract sits on top of the
  abstract mail operations defined in
  [`tools/mail-source/contract.md`](../mail-source/contract.md);
  the forwarder-relay adapter consumes a message returned by
  the mail-source layer and produces routing metadata. It does
  not itself fetch or send mail.

## What this contract does NOT cover

* **Detection of GHSA / private-reporting trackers without an
  inbound relay message.** Those are handled by the
  `<!-- apache-magpie: routing-mode via-forwarder -->` marker
  documented in
  [`docs/security/forwarder-routing-policy.md`](../../docs/security/forwarder-routing-policy.md).
  The contract is for adapters that recognise a message; the
  marker is for trackers with no message at all.
* **Send semantics.** Drafts produced via
  `reporter_addressing_block()` are handed back to the
  mail-source layer's `create_draft` operation; this contract
  does not send mail. The framework rule remains *draft, never
  send*.
* **Tracker field schema.** The names of the tracker body
  fields (*Reporter credited as*, *Security mailing list
  thread*, etc.) are declared in
  [`<project-config>/project.md`](../../projects/_template/project.md)
  under the `tracker.body_fields` block. The adapter returns
  values; the tracker decides where to write them.
* **Multi-thread reconciliation.** When a tracker records both
  a direct reporter thread and a separate relay thread, the
  primary-vs-relay selection rule lives in
  [`tools/gmail/threading.md`](../gmail/threading.md) —
  *Selecting the inbound thread when multiple are recorded*.
  The adapter contract assumes one inbound message at a time
  and lets the threading layer decide which message to ask
  about.
