<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-invalidate — reporter email draft

## Step 5 — Build the proposal

### 5d — Email draft (security@-imported only)

Skip this entire substep when the import path detected in Step 2
is *PR-imported*. Two additional skip cases — both **must be
named explicitly** in the Step 5e rollup terminal entry:

- **Internal-audit-finding imports.** The tracker was
  imported from a project-internal markdown audit
  (`<source-markdown>` or equivalent) with no inbound
  `security@` thread. No reporter to notify. The rollup
  terminal entry MUST state: *"No reporter notification owed
  — internal audit finding, no inbound `security@` thread."*
- **GHSA-relay-only reports — operator with GHSA write
  access.** The only inbound channel is a GHSA advisory, the tracker carries no Gmail thread,
  and the operator has write access to the `<upstream>` repo's GHSA
  (`gh api repos/<upstream>/security-advisories/<GHSA-ID>` returns non-403).
  The GHSA advisory itself IS then the closure communication: post a closing comment on the GHSA, mark the advisory withdrawn or closed informational,
  and record in the rollup terminal entry: *"GHSA-relay-only reporter channel (GHSA-XXXX-XXXX-XXXX) — closure communicated as GHSA comment `<URL>` / advisory state set to `<withdrawn|informational>`; no Gmail reply needed."*
- **GHSA-relay-only reports — operator without GHSA write
  access.** Same intake, but the operator cannot comment on or modify the GHSA
  (the call above returns 403, or the triager account lacks GHSA-write membership).
  The GHSA channel is then **not** self-sufficient: relay the closure through a forwarder with GHSA-write permission, who posts the closure comment / state change on our behalf.
  If the parent tracker was imported via a forwarder adapter (the optional
  [`security-issue-import-via-forwarder`](../issue-import-via-forwarder/SKILL.md)
  sub-skill, with `forwarders.enabled` non-empty in `<project-config>/project.md` and a registered adapter that applies),
  route the draft through that adapter's `contact_handle` and its `reporter_addressing_block` convention, per
  [`tools/forwarder-relay/README.md`](../../../../tools/forwarder-relay/README.md).
  The body carries the clickable GHSA URL on its own line and a paste-ready block in the reporter's voice with the invalid-disposition rationale
  (plus the canonical CVE-ID when `duplicate`) for the forwarder to post on the GHSA.
  Record in the rollup terminal entry: *"GHSA-relay-only reporter channel (GHSA-XXXX-XXXX-XXXX); operator lacks GHSA-write access on `<upstream>`. Forwarder-relay draft `<draftId>` queued to `<forwarder-contact>` requesting they post the closure comment on the GHSA on our behalf — awaiting user review."*

For every other `security@`-imported tracker, the invalidation
reply is one of the four
[forwarder-routing-policy milestones](../../../../docs/security/forwarder-routing-policy.md#milestones--do-relay)
(*Report assessed as invalid*) — so the draft fires in both
direct-reporter and via-forwarder modes; the policy only changes
the **recipient** and the **body shape**.

1. **Recipients:**
   - **Direct-reporter mode**: `toRecipients` is
     `tracker.reporterEmail` (the `From:` of the inbound root
     message). The reply lands on the inbound thread via thread
     attachment.
   - **Via-forwarder mode** (the parent tracker was imported via
     a forwarder adapter — see the optional
     [`security-issue-import-via-forwarder`](../issue-import-via-forwarder/SKILL.md)
     sub-skill and the
     [policy's detection list](../../../../docs/security/forwarder-routing-policy.md#when-does-via-forwarder-mode-apply)):
     `toRecipients` is the **forwarder contact** resolved via the
     matching adapter's `contact_handle` per
     [`tools/forwarder-relay/README.md`](../../../../tools/forwarder-relay/README.md)
     (or the named contact from an explicit no-direct-contact
     marker comment on the tracker). The body follows the
     adapter's `reporter_addressing_block` convention and the
     *Report assessed as invalid* milestone-body shape in the
     policy doc — short, references the external identifier
     (GHSA ID, HackerOne URL) rather than restating the
     technical detail.
     Invoke the sub-skill only when it can match (its Step 1 stays the authoritative detection):
     when `forwarders.enabled` is empty, never load it;
     otherwise invoke it only when the tracker's import rollup records a forwarder-relay provenance, or the inbound root message passes the parent-side `detect()` check in
     [`security-issue-import` Step 3](../issue-import/SKILL.md#step-3--classify-each-candidate)
     (sender pattern OR first-400-character preamble of an enabled adapter).
     A tracker that passes neither is not an adapter relay; the policy's other via-forwarder cases (GHSA-only, markdown import, the no-direct-contact marker) route without the sub-skill.
   - `ccRecipients`: includes `security_cc` from the shared
     [security draft CC resolution](../../../../tools/mail-source/contract.md#security-draft-cc-resolution).
     If no address resolves, block draft creation.
2. **Subject:** `Re: <root subject>`.
   Never invent a fresh subject: the reply lands on the inbound thread
   (`replyToMessageId` for `claude_ai_mcp`, `--thread-id` for `oauth_curl`).
3. **Body:**
   - Spine: the canned section picked in Step 4, verbatim.
   - Augmentation: a clearly-marked block filling the
     `HERE DETAILED EXPLANATION FOLLOWS` placeholder (or
     equivalent) with the case-specific reasoning gathered in
     Step 3. Use the same `> **[Inline addition for this
     report]**` block convention as
     [`security-issue-import` Step 5](../issue-import/SKILL.md)
     — the user must be able to delete the augmentation
     cleanly without leaving a grammatical orphan.
   - **No mention of `<tracker>`.** The tracker repo is private and the reporter has no access;
     cite the public Security Model and any public CVEs instead.
   - **Canonical CVE-ID for `duplicate` dispositions.** When
     the close is a `duplicate` of an existing CVE record, the
     body MUST name the canonical `CVE-YYYY-NNNNN` ID
     verbatim — e.g. *"This is the same root cause as
     `CVE-2026-XXXXX` which we already track and ship the fix
     for in `<product>` X.Y.Z."* This lets a forwarder's
     dedup workflow group the two threads. For via-forwarder mode this
     additionally goes inside the adapter's paste-ready
     reporter-voice block per the matching adapter's
     `reporter_addressing_block` convention — see
     [`tools/forwarder-relay/README.md`](../../../../tools/forwarder-relay/README.md).
   - **Polite-but-firm**, per
     [`AGENTS.md`](../../../../AGENTS.md#tone-polite-but-firm--no-room-to-wiggle):
     state the team's position once, with reasoning, and do not re-open the discussion (*"happy to discuss further"*).
4. **Backend selection:** the project's configured drafting backend, per
   [`tools/gmail/draft-backends.md`](../../../../tools/gmail/draft-backends.md#how-the-skills-pick-a-backend).
   Prefer `oauth_curl` (credentials at default path `~/.config/apache-magpie/gmail-oauth.json`), which preserves URLs verbatim.
   Use the discouraged `claude_ai_mcp` backend, which
   [rewrites embedded URLs into Google tracking redirects](../../../../tools/gmail/draft-backends.md#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects),
   only when `oauth_curl` credentials are missing AND the body has no links.
5. **Existing-draft check.** Before drafting, scan the inbound thread for a pending draft per the
   [*Detecting drafts that already exist on a thread*](../../../../tools/gmail/draft-backends.md#detecting-drafts-that-already-exist-on-a-thread)
   recipe — both `mcp__claude_ai_Gmail__list_drafts` and `mcp__claude_ai_Gmail__get_thread`.
   If one exists, surface it instead of silently shadowing it.
