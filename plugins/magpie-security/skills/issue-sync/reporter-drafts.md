<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — draft emails to the reporter

Part of the Step 2b lookup in [`signals-to-actions.md`](signals-to-actions.md), which says when to read this file.

- **Status update to the reporter** — **whenever the issue's status has changed since our last message to the reporter, propose a Gmail draft that brings the reporter up to date.**
  The transitions that warrant one are listed in
  [`docs/security/roles.md` — Keeping the reporter informed](../../../../docs/security/roles.md#keeping-the-reporter-informed),
  including the post-close *"CVE is live on cve.org"* transition surfaced by
  [Step 1g](gather.md#1g-recently-closed-trackers--check-cveorg-publication-state).

  **Pick the matching canned-response template** rather than free-drafting.
  [`<project-config>/canned-responses.md`](../../../../<project-config>/canned-responses.md)
  carries one template per lifecycle transition — *"CVE allocated"*,
  *"Fix PR opened"*, *"Fix PR merged"*, *"Release shipped"*,
  *"Advisory sent"*, *"CVE published on cve.org"*, *"Credit
  correction"*.
  Substitute the SCREAMING_SNAKE_CASE placeholders (`CVE_ID`, `PR_URL`, `VERSION`, `ADVISORY_URL`, `RELEASE_URL`)
  with values from the tracker body and the Step 1b / Step 1g signals.
  Draft from scratch only if the transition is not in the canned set,
  and then offer to add the new wording to the canned-responses file as a follow-up.

  Each status update follows the three-paragraph shape in
  [*Brevity: emails state facts, not context*](../../../../docs/editorial-guidelines.md#brevity-emails-state-facts-not-context):
  (a) one sentence on what changed, (b) one sentence on what comes next and roughly when, (c) the artifact URLs on their own line(s).
  Nothing else: no re-introduction, no recap, no process explanation, no speculation about severity or schedule.

  Always reply on the **original** Gmail thread (identified in Step 1c), not the GitHub-notifications mirror thread.

  **Use full, clickable URLs for every reference in the email body.**
  Shorthand like ``<upstream>#65346`` or ``<tracker>#261`` does **not** render as a link in mail. Concretely:

  - Tracking issue (allowed on the private mail thread): the **full** URL ``https://github.com/<tracker>/issues/<N>``, never ``#<N>`` or ``<tracker>#<N>``.
  - Fix PRs on ``<upstream>``: the **full** URL ``https://github.com/<upstream>/pull/<N>``, never ``<upstream>#<N>``.
  - Any other GitHub reference (public issues, commits, security advisories): the full URL.
    Markdown-link syntax (``[text](url)``) does **not** render in plain-text email — use the bare URL.
  - CVE IDs appear as **plain ``CVE-YYYY-NNNN`` inline text only**.
    **Never** include the CVE-tool URL (``<cve-tool-url>/cve5/CVE-YYYY-NNNN``) in a reporter email.
    Once the CVE is **published** on ``cve.org`` (advisory sent, ``announced`` label set),
    the ``cve.org`` URL (``https://www.cve.org/CVERecord?id=CVE-YYYY-NNNN``) is an acceptable alternative,
    but plain text stays the default. Full rule and pre-draft self-check:
    [*Reporter emails: CVE ID only, never the ASF CVE-tool URL*](../../../../docs/editorial-guidelines.md#reporter-emails-cve-id-only-never-the-asf-cve-tool-url).
  - Advisory archive URLs (``<mail-archive-url>/thread/...``) are already full URLs; paste them as-is.

  This applies to the **email** path only; comments on the ``<tracker>`` issue use the
  markdown-linked ``[#<N>](url)`` / ``[<upstream>#<N>](url)`` form per Golden rule 2.

  **Confidentiality:** the tracking-issue URL is a public-safe identifier and *may* go in the reporter email;
  the tracker's content and, before the advisory ships, the security framing may not, per
  [Confidentiality of `<tracker>`](../../../../AGENTS.md#confidentiality-of-the-tracker-repository).
  For a reporter who cannot access the tracker, pair the URL with a one-line identifier-only note
  (see [`docs/confidentiality.md`](../../../../docs/confidentiality.md#sharing-a-tracker-url-with-someone-who-cannot-access-it)).

  **Do not re-ask questions that have already been asked.** Before drafting, scan the thread end-to-end for open questions we already put to the reporter —
  most importantly the credit-preference question, but also technical follow-ups.
  If one is still pending an answer, **omit it from the new draft**.
  Restate the credit question only if (a) it has never been asked on the thread,
  or (b) more than ~7 days have passed since it was last asked **and** publication is imminent.
  When in doubt, ask the user before re-pinging the reporter.

  Concrete check: in our previous messages on the thread, look for *"credited"*, *"credit"*, *"how would
  you like to be"*, *"name (and, if applicable, affiliation"*, or *"prefer to
  remain anonymous"*.
  If any is present and the reporter has not replied, the credit question is **already pending** — do not re-ask.

- **Draft email to reporter (other reasons)** — whenever the ball is in our court on the thread for another reason
  (a reporter question, a triage follow-up, a negative assessment), propose a **Gmail draft** reply (not a sent message).
  State the draft's intent in one line, and reuse a canned response from
  [`canned-responses.md`](../../../../<project-config>/canned-responses.md) verbatim where one applies.
  Show the exact subject, recipients, In-Reply-To, and body in the proposal.

  **Brevity** applies: fresh wording carries only the facts the reporter needs (the question answered, the decision communicated) plus one artifact link,
  per [*Brevity: emails state facts, not context*](../../../../docs/editorial-guidelines.md#brevity-emails-state-facts-not-context).

  **Route through the forwarder-relay adapter when one is registered.**
  If the parent tracker carries a forwarder-adapter marker (set by the optional
  [`security-issue-import-via-forwarder`](../issue-import-via-forwarder/SKILL.md)
  sub-skill when `forwarders.enabled` is non-empty in
  [`<project-config>/project.md`](../../../../<project-config>/project.md)
  and the inbound message matched a registered adapter),
  route any drafted reply through that adapter's `contact_handle` and use its `reporter_addressing_block` convention.
  Contract, including the per-event do-relay / suppress matrix that decides whether a draft is proposed at all
  (e.g. CVE-allocated and advisory-sent events relay; routine credit-form questions and reviewer-comment relays are suppressed):
  [`tools/forwarder-relay/README.md`](../../../../tools/forwarder-relay/README.md).
  When no adapter is registered (`forwarders.enabled` is empty, or the tracker has no forwarder-adapter marker),
  proceed in direct-reporter mode — the draft targets the reporter on the inbound thread.
  In either of those cases do not load or invoke the sub-skill at all:
  with `forwarders.enabled` empty its Step 0 returns no match, and the marker is the recorded result of the import-time `detect()`, so a tracker without it has no adapter to route through.
  The sub-skill's Step 1 stays the authoritative detection for the trackers that do carry the marker.

  **Never send.** Always create a draft, preferably attached to the inbound mail thread
  (the preferred `oauth_curl` backend uses `--thread-id` directly and preserves URLs verbatim;
  the `maildir` backend replies by `In-Reply-To` / `References` on the inbound `Message-ID`, per
  [*The Maildir backend*](../../../../tools/gmail/draft-backends.md#the-maildir-backend);
  the discouraged `claude_ai_mcp` backend resolves the latest message ID from the inbound `threadId` and passes it as `replyToMessageId` but rewrites embedded URLs —
  see [`draft-backends.md`](../../../../tools/gmail/draft-backends.md#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects)).
  If Step 1c could not resolve a `threadId` but the inbound `Message-ID` is known (PonyMail, or the tracker's recorded root `Message-ID`),
  `oauth_curl` passes it as `in_reply_to` (and its `References` chain as `references` when known) so the draft still threads by header.
  Otherwise fall back to a subject-matched draft (thread-attachment parameter omitted, `subject: Re: <root subject>`)
  per [`tools/gmail/threading.md`](../../../../tools/gmail/threading.md).
  Surface which path was taken in the proposal.
  The Gmail MCP's no-update-no-delete limitation — corrections surface the prior `draftId` for manual discard rather than silently shadowing it —
  is in [`tools/gmail/operations.md`](../../../../tools/gmail/operations.md#hard-limitation--no-update-no-delete).
