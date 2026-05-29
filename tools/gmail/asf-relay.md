<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gmail — ASF-security-relay drafting](#gmail--asf-security-relay-drafting)
  - [Rules](#rules)
  - [How the skills detect relay cases](#how-the-skills-detect-relay-cases)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Gmail — ASF-security-relay drafting

Some reports reach the project's security list via the ASF security
team — `security@apache.org` itself, or a personal `@apache.org`
address of an ASF security-team member — forwarding a report that
came in through GHSA, HackerOne, or another channel the project's
security team does not have direct access to. In those cases the
"reporter" on the Gmail thread is the ASF forwarder, and the
**actual external reporter is unreachable to us directly**: we can
only reach them by asking the ASF forwarder to relay questions
through the same external channel.

When drafting any reply on an ASF-security-relay tracker — receipt
of confirmation, credit-preference request, status update — the
threading rules from [`threading.md`](threading.md) all still apply;
the differences are in the headers and body shape.

**Scope of this file: relay thread is the *only* thread.** The
relay-specific shape below (different `To:`, brevity, link to the
external reference) applies when the inbound relay thread is the
**only** thread recorded on the tracker — i.e. the external
reporter never sent a direct message to the project's security
list, so the relay is the only path back to them. When the tracker
records **two threads** — a direct primary reporter thread *and* a
separate forwarder/relay thread (typical when an external reporter
filed directly *and* the same bug was later relayed by huntr.com /
GHSA / ASF-security) — default drafts go to the **primary** thread
per [`threading.md` — Selecting the inbound thread when multiple
are recorded](threading.md#selecting-the-inbound-thread-when-multiple-are-recorded),
and the relay-specific shape below applies only to the rarer
back-channel message the project sends *through* the relay
channel (e.g. *"please ask the external reporter to confirm a
credit form for the advisory"*).

Placeholder convention:

- `<security-list>` — the project's security list. The concrete
  address is declared in
  [`<project-config>/project.md → Mailing lists`](../../<project-config>/project.md#mailing-lists).

## Rules

- **Thread attachment** — attach the draft to the inbound relay
  thread, per the [threading rule](threading.md). On the default
  `claude_ai_mcp` backend that means resolving the thread's latest
  message ID and passing it as `replyToMessageId`; on the opt-in
  `oauth_curl` backend it means passing the `threadId` to
  `oauth-draft-create --thread-id`. Never fabricate a new thread for
  a credit-preference relay; it goes on the same thread as the
  original inbound report.
- **Subject** — `Re: <root subject>`, i.e. the subject of the
  inbound relay message. No fabricated new subject, no
  relay-specific title like *"\<Project\>: credit-preference relay
  for <GHSA-ID>"*.
- **`To:`** — the ASF forwarder (the `From:` address of the
  inbound relay message). Typically this is a personal
  `@apache.org` address; use that, not the `security@apache.org`
  list alias, so the conversation stays with the individual who
  already knows the report.
- **`Cc:`** — `<security-list>` as always.
- **Body** — short, per the *"Brevity: emails state facts, not
  context"* rule in [`../../AGENTS.md`](../../AGENTS.md). The ASF
  security team knows the handling process; do **not** restate the
  vulnerability, the severity analysis, or the project's CVE
  process. When the purpose of the draft is a credit-preference
  relay, the ask is one sentence: *"Please forward the
  credit-preference question below to the external reporter through
  the original channel."*

- **Include the clickable external-reference URL in the body, not
  just the ID.** The forwarder receives many relays; making them
  re-look-up the ID to forward our reply is friction. Put the full
  URL on its own line near the top of the body so it is one click
  reachable:

  - GHSA: `https://github.com/<org>/<repo>/security/advisories/GHSA-NNNN-NNNN-NNNN`
  - HackerOne: the report URL the forwarder originally shared
  - Any other channel: the canonical URL for the report

  The CVE-record URL (`https://www.cve.org/CVERecord?id=<CVE-ID>`
  or the adopting project's CVE-tool URL) goes on its own line too
  when the message includes a CVE allocation.

- **Reporter-facing content goes as a ready-to-paste block, not as
  a third-person ask.** Any text destined for the external reporter
  via the forwarder MUST be drafted as the actual reporter-facing
  message, addressed to the reporter and signed by the project,
  inside a fenced block the forwarder can copy verbatim into their
  reply to the reporter.

  ❌ Third-person framing forces the forwarder to compose the
  reporter-facing text themselves:

  ```text
  Could you please pass to Matteo that CVE was allocated for
  GHSA-2vgv-x9xr-7gfj: CVE-2026-49296. Thanks.
  ```

  ✓ Paste-ready block in the reporter's voice:

  ```text
  Hi <forwarder>,

  GHSA: https://github.com/<org>/<repo>/security/advisories/<GHSA-ID>
  CVE: https://www.cve.org/CVERecord?id=<CVE-ID>

  Please forward the following to the external reporter:

  ---
  Hello <reporter first-name>,

  Thanks again for your report. We have allocated <CVE-ID> for
  the issue and the fix is being prepared. Please keep this issue
  private until it has been publicly disclosed.

  Best,
  <project> security team
  ---

  Thanks,
  <sender>
  ```

  **Why both rules together.** The clickable URL gives the
  forwarder one-click context on their side; the paste-ready block
  gives them zero-edit-required content for their reply. Together
  they reduce the relay round-trip to a single forward-and-paste
  action on the forwarder's side and let the project control the
  reporter-facing wording (credit framing, embargo wording,
  disclosure-timeline language).

  Apply this shape to every relay message that carries content
  intended to reach the external reporter — receipt of
  confirmation, credit-preference question, CVE-allocation
  notification, status update, release-shipped notification,
  advisory-published notification.

  **Source:** Arnout Engelen (`@raboof`, `engelen@apache.org`,
  ASF Security) feedback on a CVE-allocation relay sent for
  `GHSA-2vgv-x9xr-7gfj` / `CVE-2026-49296`, 2026-05-30.

## How the skills detect relay cases

The `security-issue-import` skill classifies candidates into
`Report`, `ASF-security relay`, and several non-import classes; the
classification feeds this drafting path.

Relay-specific signals in the inbound message:

- `From:` is `security@apache.org` or a personal `@apache.org`
  address of an ASF-security-team member;
- Body opens with the ASF forwarding preamble — *"Dear PMC, The
  security vulnerability report has been received by the Apache
  Security Team and is being passed to you for action …"* — with
  the original report underneath (often after a `====GHSA-…`
  separator when the report came in via GitHub Security Advisory);
- The body usually ends with a `Credit` line naming the discoverer
  (e.g. *"This vulnerability was discovered and reported by
  bugbunny.ai"*) — use that verbatim for the Reporter-credited-as
  placeholder, not the `From:` header (which is always the
  forwarder's address).

The import skill's Step 3 classification table documents the exact
subject / sender signals; this file describes what to do once the
classification says *"ASF-security relay"*.
