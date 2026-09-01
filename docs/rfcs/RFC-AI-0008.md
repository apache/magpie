<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [RFC-AI-0008: The coordinator role — multi-hop relay of security reports](#rfc-ai-0008-the-coordinator-role--multi-hop-relay-of-security-reports)
  - [Abstract](#abstract)
  - [Status of this document](#status-of-this-document)
  - [Motivation](#motivation)
  - [Proposal](#proposal)
    - [CVD vocabulary, not level names](#cvd-vocabulary-not-level-names)
    - [The coordinator profile](#the-coordinator-profile)
    - [Provenance fields — carried across hops](#provenance-fields--carried-across-hops)
    - [The handling-identifier exchange](#the-handling-identifier-exchange)
    - [Forwarder adapters become bidirectional](#forwarder-adapters-become-bidirectional)
    - [Coordinator-mode skills](#coordinator-mode-skills)
    - [Classification cascade becomes config-driven](#classification-cascade-becomes-config-driven)
    - [Hardening conversion — exactly one hop](#hardening-conversion--exactly-one-hop)
    - [Deduplication composes per hop](#deduplication-composes-per-hop)
    - [Tools](#tools)
    - [Reference adopter and migration](#reference-adopter-and-migration)
  - [Security model](#security-model)
  - [Drawbacks](#drawbacks)
  - [Alternatives considered](#alternatives-considered)
  - [Out of scope](#out-of-scope)
  - [References](#references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# RFC-AI-0008: The coordinator role — multi-hop relay of security reports

## Abstract

Every security-family skill assumes the adopter is the party that **owns the code and the verdict** —
what coordinated vulnerability disclosure (CVD) literature calls the *vendor*.
Real disclosure chains have a second kind of participant:
the **coordinator**,
who receives reports,
triages them on behalf of others,
and forwards them to the owning vendor.
Coordinators, established and newly created, include:

- the **ASF Security team**, operating `security@apache.org` for ~200 PMCs;
- **CERT/CC**, coordinating multi-party disclosure through its VINCE platform;
- **JPCERT/CC**, coordinating disclosure for reports received through Japan's national reporting scheme,
  published as Japan Vulnerability Notes (JVN);
- **CNCERT/CC**, coordinating disclosure of the reports behind China's national
  vulnerability database (CNVD);
- **ZDI** (Trend Micro Zero-Day Initiative),
  a commercial bug-bounty broker coordinating its researchers' findings with vendors;
- **AWS Security**, relaying findings from its internal security reviews
  to the upstream projects it depends on;
- **Akrites** (Linux Foundation),
  a clearinghouse that deduplicates AI-generated reports for critical open source software,
  opening automated intake in September 2026 on a VINCE-based platform;
- **Gold Eagle** (US government),
  the federal clearinghouse for AI-discovered vulnerabilities,
  runs on a VINCE-derived platform built with CERT/CC;
- **Athena** (Chainguard) and **Lightwell** (IBM/Red Hat),
  industry coalitions that pool frontier-model findings and coordinate upstream patches.

Chains compose:
the same project can receive reports directly (reporter → vendor),
through one coordinator,
or through several,
for example, reporter → VINCE → ASF Security → PMC.

Magpie already models the coordinator — but only from the **receiving side**:
the [`security-issue-import-via-forwarder`](../../skills/security-issue-import-via-forwarder/SKILL.md) sub-skill,
the [forwarder-relay adapter contract](../../tools/forwarder-relay/README.md),
and the [ASF-relay drafting rules](../../tools/gmail/asf-relay.md)
all describe what a vendor does when a coordinator's mail arrives.
The ASF Security team's own pipeline lives out of tree (the private `apache/security` repo),
so the sender-side templates and the receiver-side detection signatures are maintained in different places
and can drift apart silently.

This RFC names the **coordinator persona**
and defines its profile by function and termination authority, never by chain position:
the relay contract is strictly **pairwise**,
so chains of any depth need no new vocabulary.
It adds the **provenance fields** every hop must carry
(finder credits preserved verbatim, an ordered reporter chain each hop appends itself to, origin references, embargo terms),
makes forwarder adapters **bidirectional** —
one adapter carries both the emit templates and the detect signatures,
closing the drift gap above —
and sketches the coordinator-mode skills that generalize the ASF Security team's existing pipeline into the framework.

## Status of this document

**Draft.**
Nothing in this RFC is implemented.
A working coordinator pipeline already runs out of tree —
the ASF Security team's, in the private `apache/security` repo —
and would be the natural migration source for the coordinator-mode skills proposed here.

## Motivation

1. **The two ends of one contract are maintained in two repos.**
   The ASF Security team's `templates/forward.md` *generates* the
   "Dear PMC, The security vulnerability report has been received by the Apache Security Team…" preamble
   that [`tools/gmail/asf-relay.md`](../../tools/gmail/asf-relay.md) teaches vendor-side skills to *detect*.
   Either side can change without the other noticing,
   and vendor-side classification then breaks silently.
   Both ends of the contract belong in one adapter directory.

2. **Coordinators re-implement framework machinery out of tree.**
   The ASF Security team's pipeline duplicates what the security family already has:
   mail intake and thread-head selection
   ([`security-issue-import`](../../skills/security-issue-import/SKILL.md) Steps 1 and 3),
   a classification cascade (Step 3),
   prior-report and prior-rejection dedup search (Steps 2a/2b),
   threat-model triage ([`security-issue-triage`](../../skills/security-issue-triage/SKILL.md)),
   and draft-only reporter correspondence.
   The differences are parameters, not different work:
   the role settings,
   and where triage results are kept —
   a Pony Mail archive instead of a bug tracker.

3. **Chain depth is not stable, so nothing may hardcode it.**
   The same PMC receives reports at depth 0 (reporter → PMC),
   depth 1 (reporter → ASF → PMC),
   and depth 2 (reporter → clearinghouse → ASF → PMC).
   Any design that names levels ("first-level triage", "foundation triage")
   breaks each time a coordinator appears or disappears.
   Akrites is the live proof:
   a new coordinator with **no traffic yet** —
   which also means, for once, that the wire format can be agreed *before* the first message
   instead of being reverse-engineered from received mail afterward.

4. **Round-trip testability.**
   When a coordinator running Magpie sends what a vendor running Magpie receives,
   the whole relay round trip
   (forward → via-forwarder import → reporter question relayed back up)
   exercises one contract from both ends and becomes testable in one place.

## Proposal

### CVD vocabulary, not level names

Adopt the standard CVD role names (CERT/CC's CVD guide, ISO 29147 / 30111):

| Role            | Definition                                                                                                                                                                          | Examples                                                                            |
|-----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| **finder**      | Discovers the vulnerability. The identity advisory credit attaches to; invariant along the chain.                                                                                   | An individual researcher; the employee behind a company's report.                   |
| **reporter**    | Conveys the report to the receiving party *on a given hop*. Hop-relative: at the first hop usually the finder; on every relayed hop the forwarding party is the proximate reporter. | The finder themselves; a company's product-security team; the upstream coordinator. |
| **coordinator** | Receives, triages on behalf of others, forwards to the owner. Never owns the verdict.                                                                                               | CERT/CC (VINCE), the ASF Security team, Akrites.                                    |
| **vendor**      | Owns the code and the verdict (non-issue / hardening / CVE).                                                                                                                        | A PMC, any project security team — Magpie's existing persona.                       |

Finder and reporter usually coincide at the first hop and split as soon as anyone relays:
a company's product-security team reporting an employee's discovery is the reporter for that employee's finding,
and each forwarding coordinator becomes the proximate reporter on its hop.
The finder is invariant along the chain;
the reporter is not —
which is why the provenance block (below) carries the finder verbatim
and the reporters as an ordered, append-only chain.
The split also maps onto two fields every hop already keeps separate:
who to greet in correspondence (the proximate reporter)
versus who to credit in the advisory (the finder).

Levels get **no names**.
The relay contract is pairwise:
every node sees only its immediate upstream (as a forwarder adapter)
and its immediate downstream (as a routing target).
A vendor's `forwarders.enabled` lists `asf-security`;
the ASF coordinator's own config lists `vince`, `akrites`, `ghsa`.
Nobody declares chain depth —
the chain emerges hop by hop, the way SMTP `Received:` headers do.

The existing [forwarder-routing policy](../security/forwarder-routing-policy.md)
(milestones DO relay / negative space DO NOT relay)
generalizes unchanged:
each node applies it **toward its upstream**, whatever that upstream is.

### The coordinator profile

What distinguishes coordinators from each other is not position but **function** and **termination authority**,
declared in the adopter's `<project-config>/project.md` security-workflow section:

```yaml
coordinator:
  # Which triage functions this node performs.
  #   routing       — decide which downstream party owns the report
  #   assessment    — screen plausibility against the OWNER's threat model
  #   deduplication — consolidate reports of the same flaw into one
  #                   downstream case before forwarding
  #   bookkeeping   — track the status of every report through to
  #                   resolution, including reports that reached the
  #                   owner directly, and chase the ones that stall
  #   (verdict is never a coordinator function; it belongs to the vendor)
  functions: [routing, assessment, deduplication, bookkeeping]

  # Dispositions this node may terminate itself, instead of forwarding.
  # Every coordinator may drop spam. Anything beyond that is delegated
  # authority the downstream parties have granted (explicitly or by
  # long-standing practice) and must be exercised non-assertively.
  # Terminating as a hardening also makes this node responsible for
  # the public-issue conversion (see "Hardening conversion" below).
  may_terminate: [spam, false-positive-decline, hardening-decline]

  # Immediate upstreams — forwarder adapters, same contract as a
  # vendor's `forwarders.enabled`.
  upstreams: [vince, akrites, ghsa]

  # How downstream owners are resolved. A vendor resolves <tracker>,
  # <security-model>, <security-list> ONCE from config; a coordinator
  # resolves them PER REPORT from a directory of downstream parties.
  downstream_directory: <tool or config reference>

  # Where a bookkeeping node observes report status beyond its own
  # forwards. Only meaningful with `bookkeeping` declared.
  status_sources: [owner-security-lists, tracker-notifications]
```

Under this profile, VINCE is `functions: [routing]`, `may_terminate: [spam]`;
Akrites is `functions: [routing, deduplication]` —
consolidation is its stated purpose;
the ASF Security team declares all four,
with delegated decline authority for high-confidence false positives.
The word *triage* stays one word —
a node's profile says which functions of it the node performs.

The two non-obvious functions deserve a word each.
Declared **deduplication** is consolidation as a service —
merging several upstream reports of the same flaw into one downstream case,
which is what makes finder credits and origin references list-valued in the provenance block.
It is distinct from the local dedup pass every hop runs regardless of profile
(see [Deduplication composes per hop](#deduplication-composes-per-hop)).
**Bookkeeping** is the one function whose scope extends beyond the reports the node itself relays:
the ASF Security team is copied on every `security@<pmc>.apache.org` message
and receives the private-tracker notifications,
so it tracks the status of each report through to resolution —
including reports that reached a PMC directly and were never forwarded by anyone —
and can answer status queries and nudge handling that stalls.
Bookkeeping is also what makes the
[handling-identifier exchange](#the-handling-identifier-exchange)
worth its records:
the identifiers a bookkeeping node collects are how it follows a report it no longer holds.

The `downstream_directory` is the coordinator's defining feature:
where every existing security-family skill reads `<tracker>` / `<security-model>` / `<security-list>` once per adopter,
a coordinator-mode skill resolves the owning project, its security model, and its delivery address per report.

### Provenance fields — carried across hops

Pairwise recursion is only safe
if the fields that belong to the chain's *endpoints* survive every hop untouched.
The relay contract gains a **provenance block**:
every field in it is preserved verbatim,
except the reporter chain, which is append-only:

- **Finder credits** (*list*) —
  carried verbatim, never re-derived from `From:` headers:
  on a relayed hop `From:` is the proximate reporter, never the finder.
  A list because a consolidating coordinator carries every finder's credit,
  exactly as [`security-issue-deduplicate`](../../skills/security-issue-deduplicate/SKILL.md)
  already preserves multiple `credits[]` entries in CVE JSON.
- **Reporter chain** (*ordered list*) —
  the parties that conveyed the report, origin first;
  each party appends itself when it forwards
  and never rewrites or removes an earlier entry
  (the `Received:`-header analogy made literal).
  The last entry is the proximate reporter —
  the party this hop corresponds with and relays milestones back to;
  the chain as a whole is how a hop tells a relayed report from a direct one.
  It is the one provenance field that grows per hop instead of being preserved unchanged.
- **Origin references** (*list*) —
  VINCE case URL, GHSA URL, HackerOne URL, Akrites case URL.
  Clickable URLs, not bare IDs
  (per the existing [`asf-relay.md`](../../tools/gmail/asf-relay.md) rule),
  and drawn from an archive, not from a private workspace:
  an ASF forward carries the Pony Mail permalink of the original report
  on `security@apache.org`
  (resolvable by the Security team and ASF Members),
  and the forward itself acquires one in the `security@<pmc>` archive
  the receiving PMC can read.
  The Gmail label the ASF pipeline currently tracks reports under
  (e.g. `logging/2026-08-24 syslog crlf injection`)
  may accompany the permalink as a human-readable handle, but never replace it;
  the trade-offs between the ASF's candidate identifiers are discussed under the
  [handling-identifier exchange](#the-handling-identifier-exchange).
  A list, because a deduplicating coordinator may consolidate several origins into one forward.
- **Embargo / disclosure-timeline terms** —
  set by the finder or the first coordinator;
  relayed, never renegotiated mid-chain by a hop.
- **Upstream dedup claims** —
  "consolidated from N reports" is recorded as a *hint*,
  never as permission to skip the local dedup pass
  (see [Deduplication composes per hop](#deduplication-composes-per-hop)).
- **Back-channel convention** —
  content destined for the reporter travels as the ready-to-paste, reporter-voiced block
  ([`asf-relay.md`](../../tools/gmail/asf-relay.md)),
  wrapped hop by hop in both directions:
  a vendor's question to the reporter transits each coordinator,
  and each hop wraps — none rewrites.

### The handling-identifier exchange

Every hop that accepts a report returns to the party it received it from,
the identifier under which it handles it:
a tracker issue number, a case id, a thread link —
whatever the receiving hop's own pipeline keys on.
The exchange is pairwise, like everything else in the contract:

- the upstream records the returned identifier next to its own record of the report
  and cites it in every later message about it —
  status queries, milestone relays, relayed reporter questions —
  so cross-hop correspondence needs no fuzzy re-matching;
- the identifier is a reference, not access:
  returning a private tracker's issue number grants nothing;
  it names the report in future correspondence;
- a consolidating hop returns the same identifier for several upstream reports —
  which is itself a dedup signal one hop up;
- the two flows meet:
  the identifier a hop returns upstream is the same one it sends downstream as an origin reference when it forwards.
  A VINCE case URL is VINCE's handling identifier returned to the reporting company
  *and* the origin reference on VINCE's forward to the next hop.

Existing practice already has instances of the shape —
VINCE case numbers, GHSA identifiers, HackerOne report URLs —
this section makes the exchange a contract obligation on every hop
rather than a per-platform habit.

Which identifier the ASF Security team should share is a genuine design choice.
Pony Mail addresses an archived message in two ways —
a **permalink**, keyed on Pony Mail's internal id,
and a **lookup** (`thread/<Message-ID>?<listid>`), keyed on the message's `Message-ID`,
which exists only for messages that carry one —
and none of the three candidate identifiers wins on every axis:

- **The Pony Mail permalink of the original report** on `security@apache.org`.
  Known at send time,
  so it can ride on the forward itself as an origin reference;
  the receiver can even reconstruct the same message's lookup on its own,
  since a forward carries the original's `Message-ID` in its `References:` header.
  But it resolves only for the Security team and ASF Members:
  most PMC members can cite it, not open it.
- **The Pony Mail permalink of the forwarded message** in the `security@<pmc>` archive.
  The PMC can actually open this one,
  which matters most on duplicates:
  told "this duplicates the report behind \<permalink\>",
  the PMC can verify it is in fact the same report rather than take the claim on faith.
  However, this permalink cannot be included in the forward itself,
  because it is not known at send time;
  only the forward's own lookup can.
- **The internal Gmail label**
  (e.g. `logging/2026-08-24 syslog crlf injection`).
  Resolvable by nobody outside the pipeline,
  yet the friendliest handle in human correspondence:
  a PMC answering that `logging/2026-08-24 syslog crlf injection`
  duplicates `logging/2026-08-25 rfc5424 crlf injection`
  is stating something a reader follows at a glance —
  the same sentence in two Pony Mail references is opaque until dereferenced.

Two caveats keep the Pony Mail candidates honest.

**Unicity.**
The GMail label is the only canonical identifier:
one per report, assigned at intake.
Pony Mail references are plural by construction —
every message of the thread, in every archive that holds a copy,
addressable by permalink and (usually) by lookup —
so two correspondents can cite the same report by different references
and neither is wrong.
Every reference canonicalizes back to the label,
but only the Security team can perform that conversion:
the mapping lives in its pipeline.
The contract consequence:
the label is what gets *matched on*;
a permalink or lookup arriving in correspondence is an alias to canonicalize on receipt,
and a correspondent who knows the label echoes it.

**Privacy.**
Permalink and lookup are not interchangeable toward reporters.
A lookup embeds the message's `Message-ID` —
for an original report, minted by the reporter's own mail system
and often enough to identify them.
A permalink carries no such payload.
So lookups —
including the one the forward itself can carry —
stay between hops that already hold the message
(the Security team and the receiving PMC leak nothing to each other),
while anything reporter-facing,
above all a dedup answer sent to a *different* reporter,
uses permalinks only.

What remains between the candidates is a compromise between comforts:
the label is the form the Security team's own records key on,
the forward's permalink the one the PMC can open and check.
The pragmatic emit rule is therefore a **pair**:
the label as the canonical, human-readable handle,
plus a Pony Mail reference as the resolvable one —
the original report's permalink for parties who can read `security@apache.org`,
the forward's own (as a lookup at send time) for the receiving PMC.
Pinning that pair down is exactly what the `asf-security` adapter's
emit templates (below) are for.
Mail-based coordinators still get a head start —
when the handling record *is* an archived message,
its lookup needs no separate bookkeeping —
but the reporter-safe permalink must still be fetched from the archive and stated,
so the exchange never disappears entirely.

The hardening conversion (below) relies on the same exchange run in reverse:
the reporter, having opened the requested public issue,
returns its identifier to the declining hop.

### Forwarder adapters become bidirectional

Today a forwarder adapter
(per [`tools/forwarder-relay/README.md`](../../tools/forwarder-relay/README.md))
faces the upstream only:
it detects inbound relays, extracts credits,
and renders reporter-facing wrappers (`reporter_addressing_block`),
but carries no normative templates for the forward a coordinator emits downstream —
which is exactly where the drift lives.
This RFC extends the adapter contract with a **sender side**:
the normative outbound templates
(forwarding preamble, credit-line format, AI-disclaimer line, provenance block layout)
live in the *same adapter directory* as the detection signatures derived from them.

Concretely, the `asf-security` adapter absorbs the ASF Security team's `templates/forward.md` family
as its normative emit templates;
the detection rules in [`asf-relay.md`](../../tools/gmail/asf-relay.md)
become derived-from-the-template rather than reverse-engineered.
One directory, one source of truth, both roles consume it.

For Akrites the order inverts, deliberately:
the adapter's emit side is written **first** —
proposed to the Akrites project as the format to emit —
and the detect side follows mechanically.
Since Akrites is itself a coordinator,
the better outcome is that it adopts the coordinator-mode skills and emits the contract natively;
the adapter then exists mostly as the pinned description of that agreement.

### Coordinator-mode skills

Two new skills in the `security` family (mode: Triage),
generalized from the ASF pipeline:

| Skill                         | Capability          | Does                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
|-------------------------------|---------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `security-coordinator-import` | `capability:intake` | Sweep the coordinator's inbox through a mail-source backend; select thread heads on header facts; classify each candidate through the config-driven cascade (below); resolve the owning downstream party; record everything in the coordinator's local tracker. Raw message bytes are read by a lightweight-model subagent that returns a typed proposal — the orchestrating context never ingests untrusted mail directly.                                                                                                                            |
| `security-coordinator-assess` | `capability:triage` | For each classified report: dedup against the coordinator's own archive (text-confirmed, sibling-vs-duplicate discipline); screen against the *owner's* threat model using the ASF pipeline's assessment triple (adversary in the model × attacker-controllable input × violated security property); then draft — a forward to the downstream owner carrying the provenance block, or, within `may_terminate` authority only, a non-assertive decline to the reporter — a hardening decline also carrying the responsibility for the public-issue conversion (below). Drafts only; a human sends. |

Both fan out **per downstream party**
(one assessor per owning project,
reusing that project's threat model and source checkout across its reports),
which is the coordinator's structural difference from every vendor-mode skill.

The `bookkeeping` function gets no skill in this RFC:
a status sweep over the profile's `status_sources`
(matching handling identifiers against owner-list traffic and tracker notifications,
surfacing reports that have gone quiet)
is deliberately left for a follow-up once the profile stabilizes.

Existing vendor-mode skills are untouched;
a vendor receiving from a coordinator continues through
`security-issue-import` + `security-issue-import-via-forwarder` exactly as today.

### Classification cascade becomes config-driven

`security-issue-import` Step 3 and the ASF pipeline's category table are the same mechanism with different rows.
The cascade becomes a table the adopter profile extends:
the vendor baseline keeps today's classes
(Report, CVE-tool bookkeeping, scanner dump, consolidated multi-issue, media request, spam, cross-thread-followup, fix-already-public…),
and the coordinator profile adds its own
(digest, **mirror**, license-confusion, dependency-inquiry).
Step 3 already runs the via-forwarder sub-skill ahead of its own table
whenever `forwarders.enabled` is non-empty —
the dispatch seam the config-driven cascade generalizes.

The **mirror** class is worth naming in the contract itself:
it exists *because* chains deliver the same report along two paths
(once via a coordinator, once directly from the reporter),
which pure vendors at depth 0 never see.
Every coordinator profile needs it;
with Akrites in the chain it also appears one level up.

### Hardening conversion — exactly one hop

Non-issues, bugs and hardenings both terminate the private track,
but they differ in what should survive:
a non-issue ends and nothing is owed;
a bug or hardening is a fact-correct improvement that falls outside the owner's threat model —
worth implementing, just not as a security issue.
A multi-hop chain gives hardenings a failure mode of their own:
every hop can assume another hop (or the reporter) will file the improvement publicly,
and nobody does.
Today's practice is the right first step with no fallback:
decline replies invite the reporter to take the finding to the public tracker,
and the improvement is lost whenever the reporter does not follow through.

The rule:
**opening the public issue falls on the reporter first;
the hop that terminated the private handling is responsible for ensuring it happens.**

- The decline invites the reporter to open the public issue
  and to return its identifier —
  the [handling-identifier exchange](#the-handling-identifier-exchange) run in reverse.
  When the terminating hop is mid-chain,
  the invitation relays upstream hop by hop,
  like every other reporter-facing message.
- Reporter-opened is the preferred outcome:
  the improvement is filed under the finder's own name,
  so attribution needs no consent machinery.
- If no identifier comes back within the window the decline states,
  the terminating hop files the issue itself.
  A fallback filing is written fresh,
  as an improvement request in the filer's own words:
  a hardening is public-safe by definition (no exploitable vulnerability is disclosed),
  but the private thread is not —
  no verbatim paste of the report,
  and the finder is credited only with their consent.
- Either way the terminating hop records the issue identifier in its decline record,
  so later duplicates of the same finding can be answered with
  "here is where the improvement is tracked".
- Any hop that forwards instead passes the responsibility down with the report.
  It therefore always lands on exactly the terminating hop —
  never duplicated, never dropped.

At depth 0 the vendor's `DEFENSE-IN-DEPTH` disposition
([`security-issue-triage`](../../skills/security-issue-triage/SKILL.md):
"close as wontfix + file a public PR for the hardening")
already implements the fallback arm;
this rule adds the reporter-first invitation before it.

### Deduplication composes per hop

Each hop's dedup scope is its own inbox and archive:
Akrites dedups across what flowed through Akrites;
the ASF coordinator dedups across `security@apache.org`
(including direct reports Akrites never saw);
the vendor dedups across its tracker.
Therefore:

- an upstream "already deduplicated" provenance claim is a hint that seeds the local check,
  never a reason to skip it;
- a local dedup match is confirmed by **text**,
  never by tags, labels, or upstream claims alone
  (the ASF pipeline's sibling-vs-duplicate and open-vs-closed relabel rules
  move into the shared dedup guidance);
- consolidation at any hop makes finder credits and origin references *lists* everywhere downstream
  (see the provenance block).

The local pass described here is not declarable — every hop runs it, whatever its profile says.
The profile's `deduplication` function is the stronger, opt-in thing built on top of it:
consolidating the matches into one downstream case instead of merely cross-referencing them.

### Tools

- **`tools/mail-source/`** gains the ASF pipeline's read-only Gmail-API backend
  (`gmail.readonly` scope, OAuth via environment)
  as a concrete adapter beside `imap/` and `mbox/`.
  It complements, not replaces, the existing
  [`tools/gmail/`](../../tools/gmail/README.md) (gmail-mcp) backend —
  the reference adopter's primary full read + write backend —
  as the narrower-scoped choice for pipelines that only read and classify.
- **`tools/vince/`** —
  upstream forwarder adapter for CERT/CC's VINCE platform,
  per the (now bidirectional) contract.
  Akrites runs on VINCE and Gold Eagle on a VINCE derivative,
  so this adapter is the base the next two specialize.
- **`tools/akrites/`** —
  adapter for the Linux Foundation's Akrites clearinghouse
  (automated intake from September 2026).
  Its emit side is the format-agreement opportunity named in
  [Reference adopter and migration](#reference-adopter-and-migration):
  written and proposed before the first report flows.
- **`tools/gold-eagle/`** —
  adapter for the US-government Gold Eagle clearinghouse
  (CERT/CC-built VINCE derivative);
  expected to share most of its detect/emit rules with `tools/vince/`.
- **`tools/jpcert/`** —
  adapter for JPCERT/CC.
  The easiest coordinator to support:
  JPCERT/CC communicates over plain e-mail rather than a lock-in portal,
  so the adapter is nothing but mail conventions —
  a preamble to detect,
  a case reference (JVN / JPCERT# identifiers) to record,
  and a reply address to relay through.
- **`tools/cncert/`** —
  adapter for CNCERT/CC, the coordinator behind China's CNVD database.
  E-mail-based (`vsupport@cert.org.cn`) with the highest-effort detect side:
  notifications are Chinese-language and carry CNVD rather than CVE identifiers,
  so the adapter holds the subject/preamble patterns and the CNVD id format.
- **`tools/zdi/`** —
  adapter for Trend Micro's Zero Day Initiative,
  e-mail-based with stable per-case identifiers (`ZDI-CAN-NNNNN`)
  and fixed disclosure-deadline terms to record as embargo provenance.
- **`tools/aws-security/`** —
  adapter for AWS Security acting as a coordinator.
  E-mail-based like JPCERT/CC,
  and its newer messages carry an `Engagement ID: <m>.2.<n>:mailto:amazon.com` line —
  a ready-made instance of the
  [handling-identifier exchange](#the-handling-identifier-exchange)
  to record and quote back.
- **`tools/athena/`**, **`tools/lightwell/`** —
  adapters for the Chainguard Athena and IBM/Red Hat Lightwell coalitions,
  whose platforms are their own;
  added when each relationship goes live.
  Both pool frontier-model findings before forwarding,
  so their preambles are where consolidated multi-origin reports
  (list-valued finder credits and origin references, per the provenance block)
  are most expected.

ASF-specific machinery
(Whimsy PMC lookup, Pony Mail archive search, the tag vocabulary, the `email-classification` archive layout)
stays in the adopter's `<project-config>/` —
it is the ASF coordinator's `downstream_directory` and archive implementation,
not framework surface.

### Reference adopter and migration

The ASF Security team's `inbox-manager` repo is already a Magpie adopter
and becomes the reference coordinator.
Migration is phased so each step is independently useful:

1. **Single-source-of-truth first**:
   move the forwarding preamble / credit-line / disclaimer formats
   into the `asf-security` adapter as emit templates;
   upstream the dedup discipline and the assessment triple into the shared security docs,
   reconciling the triple with
   [`security-issue-triage`](../../skills/security-issue-triage/SKILL.md)'s existing vocabulary
   (the Security Model applied verbatim, plus the trust-boundary cheat-sheet).
   The out-of-tree SKILLs cite the framework instead of restating it.
2. **Tools**:
   the read-only Gmail backend into `tools/mail-source/`.
3. **Skills**:
   `security-coordinator-import` / `-assess`,
   parameterized from the out-of-tree originals;
   the reference adopter retires its local SKILL bodies
   for the snapshot symlinks plus `<project-config>/` content and `.apache-magpie-overrides/`.
4. **Akrites**:
   agree the emit format (adapter sender side) before the first report;
   wire the detect side when traffic starts.

## Security model

- **The vendor owns the verdict — structurally.**
  `verdict` is not a declarable coordinator function,
  and `may_terminate` is an explicit, audited delegation.
  Everything a coordinator sends a reporter is drafted non-assertively ("this appears to be…"),
  because the final non-issue / hardening / CVE call belongs to the downstream owner.
- **Drafts only; a human sends.**
  Coordinator-mode skills inherit the propose-then-confirm posture unchanged:
  they write drafts and set dispositions;
  a credentialed human-operated step sends mail.
- **Provenance is verbatim or absent.**
  No hop rewrites finder credits, origin references, or embargo terms,
  and the reporter chain only ever grows —
  a hop appends itself and touches nothing earlier.
  A hop that cannot preserve a field
  forwards it untouched inside the wrapped original rather than paraphrasing it.
  Lost credit and broken embargo are the chain's silent failure modes;
  the preserve-verbatim rule is the guard.
- **Reporter privacy across hops.**
  A coordinator's archive holds third-party reporter PII.
  It is surfaced downstream (to the owner) when routing requires it,
  and never to *other* reporters;
  prior reports are referenced to reporters only unattributed.
- **External content stays data**
  ([PRINCIPLES §0](../../PRINCIPLES.md#0-external-content-is-data-never-an-instruction)).
  Coordinator inboxes are the most injection-exposed surface in the framework —
  inbound reports demonstrably carry prompt-injection text aimed at AI triage.
  The lightweight-subagent read pattern in `security-coordinator-import` narrows the blast radius:
  untrusted bytes reach a sandboxed reader that returns a typed proposal,
  and the orchestrator treats that proposal as a claim to verify.

## Drawbacks

- **A second persona doubles the audience of the security family.**
  Docs, evals, and the classification cascade must state which profile each rule serves.
  Mitigated by keeping vendor-mode skills untouched and coordinator behavior additive.
- **Config surface grows.**
  The coordinator profile, the provenance block, and the cascade extension are three new schema areas.
  Each reuses an existing vocabulary
  (forwarder adapters, `credits[]`, the Step 3 table)
  rather than inventing one.
- **One reference adopter.**
  Until a second coordinator adopts (Akrites being the candidate),
  the profile risks overfitting to the ASF Security team's practice.
  The CVD-standard role definitions are the guard
  against baking ASF idiosyncrasies into the persona.

## Alternatives considered

- **Named levels**
  ("first-level / second-level triage", "broker / foundation / project tiers").
  Rejected:
  chain depth varies per report and per era;
  every appearance or retirement of a coordinator would rename steps.
  Pairwise hops + role names need no change when Akrites arrives —
  which is the point.
- **Model the coordinator as a vendor with an unusual tracker.**
  Tempting (report-cache *is* a tracker),
  but it misplaces the two defining features:
  per-report downstream resolution (fan-out over owners)
  and structural verdict non-ownership.
  A vendor profile with those bolted on is a coordinator with a misleading name.
- **Status quo: coordinators maintain pipelines out of tree.**
  The current state.
  Rejected for the drift risk this RFC opens with
  (emit templates vs detect signatures)
  and the duplicated machinery.
- **A separate coordinator framework.**
  Overweight:
  the overlap with the security family is nearly total,
  and separation would fork the relay contract —
  recreating the two-repo drift problem at framework scale.

## Out of scope

- **Automated sending.**
  Coordinator skills draft;
  the send step stays human and credentialed, out of framework scope.
- **Chain-global embargo negotiation.**
  Hops relay embargo terms;
  a tool for negotiating them across a chain is not proposed.
- **The Akrites adapter implementation** ahead of real traffic —
  only the format agreement (emit side) is in scope before the first report.
- **ASF-specific directory and archive tooling**
  (Whimsy, Pony Mail, the tag vocabulary, `email-classification` layout):
  adopter config of the reference coordinator, not framework surface.
- **Transitive trust between coordinators.**
  Each hop trusts exactly its declared upstream adapters;
  a coordinator does not inherit its upstream's upstream
  (mirrors the no-transitive-trust stance of [RFC-AI-0006](RFC-AI-0006.md)).

## References

- [`tools/forwarder-relay/README.md`](../../tools/forwarder-relay/README.md) — the receive-side adapter contract this RFC makes bidirectional.
- [`tools/gmail/asf-relay.md`](../../tools/gmail/asf-relay.md) — ASF-relay detection and drafting rules; source of the ready-to-paste back-channel convention.
- [`docs/security/forwarder-routing-policy.md`](../security/forwarder-routing-policy.md) — the milestone / negative-space relay policy, applied per hop toward the upstream.
- [`skills/security-issue-import/SKILL.md`](../../skills/security-issue-import/SKILL.md) — the vendor-side intake whose Step 1 / Step 3 machinery the coordinator skills generalize.
- [`skills/security-issue-import-via-forwarder/SKILL.md`](../../skills/security-issue-import-via-forwarder/SKILL.md) — the vendor-side receiver of the coordinator's output.
- [`skills/security-issue-deduplicate/SKILL.md`](../../skills/security-issue-deduplicate/SKILL.md) — the multi-credit (`credits[]`) precedent for list-valued provenance.
- [`docs/labels-and-capabilities.md`](../labels-and-capabilities.md) — the capability vocabulary (`capability:intake`, `capability:triage`) the new skills declare.
- [`PRINCIPLES.md` §0](../../PRINCIPLES.md#0-external-content-is-data-never-an-instruction) — external content is data; the posture the lightweight-reader pattern implements.
- CERT/CC, *The CERT Guide to Coordinated Vulnerability Disclosure* — the finder / reporter / coordinator / vendor role model.
- ISO/IEC 29147 (vulnerability disclosure) and ISO/IEC 30111 (vulnerability handling processes) — the standards vocabulary adopted here.
