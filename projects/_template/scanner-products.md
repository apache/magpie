<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — private scanner products + finder anonymisation](#todo-project-name--private-scanner-products--finder-anonymisation)
  - [Private scanner products to anonymise](#private-scanner-products-to-anonymise)
  - [Finder anonymisation policy](#finder-anonymisation-policy)
    - [Exempt cases (keep the named credit)](#exempt-cases-keep-the-named-credit)
    - [Per-finder override](#per-finder-override)
  - [Detection signal — how the skill recognises a private-scanner thread](#detection-signal--how-the-skill-recognises-a-private-scanner-thread)
  - [Related rules](#related-rules)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — private scanner products + finder anonymisation

This file lists the **private scanner products** whose name must
not appear in any public CVE surface for this project, and
declares the **finder-anonymisation policy** the
[`security-issue-sync`](../../skills/security-issue-sync/SKILL.md)
skill applies during sync.

The CVE-JSON generator reads three body fields verbatim into
public surfaces:

- *Short public summary for publish* → `containers.cna.descriptions[].value`
- *Reporter credited as* → `containers.cna.credits[].value` (type `finder`)
- *Security mailing list thread* → **private audit trail**,
  not pushed to the CVE record

The sync skill's anonymise gate (Step 1d signal row +
Step 5b 1b sixth pre-push gate) scrubs the first two of those
when the report came in through a private scanner channel. The
*Security mailing list thread* field stays untouched (it is the
team's audit trail).

## Private scanner products to anonymise

Each row lists one scanner product whose name must be stripped
from public CVE surfaces when its findings flow into trackers
on this project. Add a row per scanner the project's security
team works with privately.

| Product name (token) | Discovery channel | Notes |
|---|---|---|
| TODO: `<scanner-product>` | TODO: `<channel — internal SAST, partner-shared, unpublished bug-bounty pipeline, vendor private disclosure>` | TODO: `<one-line context — why the name is sensitive, contract clause if any>` |

**Token format.** The scanner-product token is the literal
string the scrubber matches against the *Short public summary*
text and the *Security mailing list thread* field. Match is
case-insensitive substring. Add aliases on separate rows when
a product has multiple names.

**When this list is empty.** If the project's security team
never receives findings from private scanners (every report
arrives via `security@<project>.apache.org` from a named
individual), leave this table empty with a note to that
effect. The sync skill's anonymise gate becomes a no-op.

## Finder anonymisation policy

The anonymise gate applies the following rule when the *Security
mailing list thread* field references one of the products
above:

1. **Default**: rewrite the *Reporter credited as* field to
   `anonymous` and strip the scanner-product name from the
   *Short public summary for publish* body field text.
2. **Audit trail stays**: the *Security mailing list thread*
   field, the status-rollup comment, and the Gmail / PonyMail
   thread keep the original scanner-product + person-name
   references for security-team auditing.

### Exempt cases (keep the named credit)

The scrubber must **not** anonymise a credit that was already
public elsewhere:

- The finder has a public **HackerOne** or **huntr.dev** report
  URL on the thread.
- The finder self-credited under their real name in their own
  inbound `security@` message (i.e. they sent the report
  themselves, named themselves, and asked to be credited).
- The finder's organisation publicly disclosed the discovery
  channel (a vendor blog post, an ASF community announcement,
  a public CVE record that already names them).

In any of these cases the credit was public-by-the-finder's-
choice before this CVE shipped; the scrubber is for the
opposite scenario (no explicit public consent).

### Per-finder override

A finder can opt back **in** to public credit by sending an
explicit *"please credit me as `<name>`"* line on the thread.
Record the consent in the tracker's status-rollup comment, set
the *Reporter credited as* field to the consented form, and
the gate stops firing for that tracker.

## Detection signal — how the skill recognises a private-scanner thread

The Step 1d signal row fires when **all** of the following
are true:

1. The *Security mailing list thread* body field's text
   contains one of the scanner-product tokens declared above
   (case-insensitive substring).
2. The *Reporter credited as* body field names a person
   (`<First> <Last>` pattern) rather than `anonymous` /
   a known public handle.
3. None of the exempt-case signals above is present on the
   tracker (no public HackerOne/huntr.dev URL; no inbound
   self-naming `security@` message; no public org-disclosed
   channel).

When the signal fires, sync proposes the rewrite as a
numbered Step 2 item; the user confirms or skips per the
normal proposal flow.

## Related rules

- The anonymise rule is one of **six pre-push hygiene gates**
  in [Step 5b 1b](../../skills/security-issue-sync/apply-and-push.md#decision-flow)
  of the `security-issue-sync` skill. The other five are
  title cleanup, upgrade-target version, trigger conditions,
  incomplete-fix cross-CVE clause, and CWE long-form
  description.
- The CVE-record-bound surfaces also follow the broader
  "Confidentiality of `<tracker>`" rules in
  [`AGENTS.md`](../../AGENTS.md#confidentiality-of-the-tracker-repository).
- The same anonymisation rule indirectly applies to advisory
  mail drafted on the `users@<project>.apache.org` thread —
  the draft is composed from the same *Short public summary*
  the sync skill polished, so the anonymise scrub is a
  one-time fix that propagates downstream.
