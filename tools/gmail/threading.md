<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gmail — drafts stay on the inbound thread](#gmail--drafts-stay-on-the-inbound-thread)
  - [The rule](#the-rule)
  - [Selecting the inbound thread when multiple are recorded](#selecting-the-inbound-thread-when-multiple-are-recorded)
  - [Fallback — subject-matched draft when `replyToMessageId` is unavailable](#fallback--subject-matched-draft-when-replytomessageid-is-unavailable)
  - [Special case — ASF-security relay](#special-case--asf-security-relay)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Gmail — drafts stay on the inbound thread

Every drafted email that relates to a tracking issue **should**
attach to the original inbound Gmail thread — the thread whose
`threadId` was recorded when the tracker was imported. Gmail's
server-side threader attaches by message-ID-of-parent (passed as
`replyToMessageId` on the MCP, or by `threadId` on the OAuth path);
**other mail clients** (Thunderbird, Outlook, Apple Mail, the
recipient's own client) thread by the MIME `In-Reply-To` /
`References` headers and the subject line, which Gmail synthesises
from the parent message in either case.

Both supported drafting backends now provide thread-attachment — see
[`draft-backends.md`](draft-backends.md):

| Backend | Thread attach | Mechanism |
|---|---|---|
| `oauth_curl` (**preferred**) | **yes** | `threadId` plus explicit `In-Reply-To` / `References` headers |
| `claude_ai_mcp` (discouraged — see [`draft-backends.md`](draft-backends.md#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects)) | **yes** | `replyToMessageId` — the message ID of the chronologically-last message on the inbound thread |

The two threading paths available to the skills, in preferred order:

1. **Thread-attached draft** — the first-choice path. Both backends
   support this. Resolve the inbound thread's latest message ID (via
   `get_thread`) and pass it to `replyToMessageId`, or pass the
   `threadId` to `oauth-draft-create --thread-id`.
2. **Subject-matched draft** — the pragmatic fallback. Use when the
   thread cannot be resolved (archived, deleted, stale `threadId`)
   or the inbound subject is unsafe to match on. Both backends fall
   back to this by simply omitting the thread-attachment parameter.

The call shape (signature, kwargs, no-send rule) per backend lives in
[`operations.md` — Drafting backends](operations.md#drafting-backends);
the rules on **which** thread to use and what the other fields look
like live here.

## The rule

- **Same thread every time, by `threadId` when known.** Whatever
  the recipient change — a reporter reply, an ASF-security relay
  request, a PMC credit question, a follow-up asking for a PoC —
  the draft should attach to the inbound tracker's `threadId`. A
  triager reading the Gmail conversation view should see every
  exchange on a single tracker in one place; if threading breaks,
  that history scatters across two conversations.
- **Subject is always `Re: <root subject>`**, never a fabricated
  new one. Gmail's own threading survives without matching
  subjects when `threadId` is set, but other clients commonly fall
  back to subject-based threading. A drifted subject looks like a
  broken conversation on half the world's mail readers. The root
  subject is the subject of the **first message** on the inbound
  thread — not the last reply's subject line, which Gmail may
  have displayed with a prefix trim.
- **`To:` may differ from the original correspondents.** It is
  fine to address a draft to a specific person (an ASF
  security-team member who relayed the report, a named PMC member,
  an individual reporter) even if the original inbound root was
  addressed to a list. Threading does not require recipient
  overlap; it requires `threadId` or (as the fallback) a matching
  subject plus the right `In-Reply-To` / `References` headers.

## Selecting the inbound thread when multiple are recorded

A tracker's *Security mailing list thread* body field can hold
more than one thread when:

- a second reporter independently filed the same root-cause bug
  through a different channel and
  [`security-issue-deduplicate`](../../skills/security-issue-deduplicate/SKILL.md)
  merged the two trackers (one line per reporter, per the dedupe
  skill's body-field shape); or
- an external reporter's report reached the project's security
  list via a separate forwarder thread — e.g. a huntr.com bounty
  relayed by `@apache/security`, a GHSA forward, a HackerOne
  forward — *after* the original direct report had already been
  imported, so the secondary thread was appended to record the
  duplicate-of provenance.

**The rule: default drafts go to the primary reporter's thread,
never to a forwarder/relay thread.** The forwarder/relay thread
is kept on the tracker for record-keeping and for back-channel
relay questions only (e.g. *"please ask the external reporter to
confirm a credit form"*) — see [`asf-relay.md`](asf-relay.md) for
the relay-shape body language.

The primary reporter is the one whose name appears in
*Reporter credited as* without a relay annotation, whose direct
email started the security-list thread chronologically first, and
whose line in *Security mailing list thread* does **not** carry
any of the forwarder signals below.

**Forwarder/relay signals — match case-insensitively in the line's
annotation text** (everything around the `threadId` reference):

- `via huntr.com`, `via GHSA`, `via HackerOne`, `via bugcrowd`,
  `via <any bounty platform>`
- `ASF-relayed`, `ASF-security relay`, `ASF-security-relay`,
  `relayed by @apache/security`, `relayed by`
- `forwarder`, `forwarded by`, `relay`, `relayed`
- `huntr.com bounty <id>-class duplicate`,
  `<provider>-class duplicate`

If a line has any of these signals it is **secondary**; the line
without any of these signals (or — for legacy trackers that
predate the convention — the chronologically-first thread
mentioned) is **primary**.

Worked example. The body field on a real tracker reads:

```text
No public archive URL — tracked privately on Gmail thread `19dc8d4675dfc1f1`.
Aymane Maguiti (huntr.com bounty `abdbcf11-…`-class duplicate, ASF-relayed by @apache/security on 2026-05-04T09:22:25Z): Gmail thread `19def0954b27ac31`.
```

- Line 1 → primary (no relay signal). Use `19dc8d4675dfc1f1` for
  every default reply: receipt-of-confirmation, credit-question,
  CVE-allocated status update, advisory-shipped follow-up.
- Line 2 → secondary (matches `via huntr.com`-class, `ASF-relayed`).
  Use `19def0954b27ac31` only when the project needs to relay a
  question back through huntr.com to the external reporter and the
  primary thread cannot deliver it.

**Edge cases:**

- **Only one thread recorded, with relay signals.** Classic
  ASF-security-relay case. Follow [`asf-relay.md`](asf-relay.md);
  there is no primary thread to fall back to.
- **Only one thread recorded, no relay signals.** Standard
  single-reporter case; the thread is the primary by default.
- **Both lines carry relay signals.** Rare — typically a
  third-party reporter relayed by two different channels.
  Surface to the user before drafting; do not pick a "least
  forwarded" line silently.
- **Neither line carries a `threadId`** (PonyMail URL only, no
  Gmail identifier). The tracker pre-dates the Gmail-threadId
  convention; fall back to the rollup-comment `threadId` lookup
  per the per-skill recipes.

Surface the primary/secondary selection in the skill's proposal
so the user sees which thread the draft attaches to (*"Drafting
on primary reporter thread `19dc8d4675dfc1f1` (Vincent55); the
secondary huntr.com-relay thread `19def0954b27ac31` was excluded
from default reply targets."*). The user can override per draft
if a specific message genuinely needs to go through the relay
channel instead.

## Fallback — subject-matched draft when `replyToMessageId` is unavailable

Thread attachment is the first-choice path, but the skills must also
work in cases where the inbound thread cannot be resolved:

- The tracker's *security-thread* body field was never filled in
  (see
  [`../github/issue-template.md`](../github/issue-template.md#field-roles-the-skills-use)
  for the field role).
- The `threadId` in that field is stale (the thread was deleted
  or archived out of the user's Gmail search index).
- `get_thread` returns no messages (the thread exists but has been
  emptied), so there is no `replyToMessageId` to point at.
- The draft is a brand-new outbound ask on a topic the inbound
  thread did not cover (e.g. a relay request to a PMC member who
  was not on the original thread), where re-threading on the
  original inbound is actually confusing.
- The Gmail backend returns an error when attaching the supplied
  message / thread (rare, but possible if the user has moved the
  thread between accounts).
- A draft already exists on the same thread and the pile-up
  workaround in [`draft-backends.md`](draft-backends.md#known-issue--thread-attached-drafts-may-not-surface-in-the-global-drafts-folder-when-stacked)
  applies — drop thread attachment for the new draft so it surfaces
  in the global Drafts folder.

In these cases, **create the draft with `replyToMessageId` omitted
(or `--thread-id` omitted on the OAuth path) but with the matching
subject line from the inbound message**. Gmail will start a new
conversation on the sender's side, but most other clients (and
Gmail's own subject-fallback behaviour on the recipient's side) will
still thread the reply by subject. This is not as good as a
thread-attached draft, but it is substantially better than either
fabricating a new subject or not drafting at all.

**Surface the degraded threading in the skill's proposal** so the
user knows which path the draft took:

- *"Draft attached by `replyToMessageId` to message `<msg-id-prefix>...`
  on thread `<thread-id-prefix>...`."* — the good case (default
  `claude_ai_mcp` backend).
- *"Draft attached by `threadId` (via `oauth_curl` backend)."* —
  the good case for the OAuth-opt-in user.
- *"Draft created by subject fallback (`<reason>`). Gmail shows it
  as a new conversation server-side; the recipient's client will
  thread it via the `Re: <subject>` match."*

When the fallback kicks in, record the reason on the tracker's
status comment so the next sync run can see why a new Gmail thread
appeared. Do not silently drop to fallback — it changes the shape
of the conversation the reporter sees.

**When fallback is not appropriate.** Some cases genuinely warrant
stopping rather than drafting on a mismatched subject. Examples:

- You have neither a thread to attach to **nor** a matching subject
  to use (typically when the tracker has never been linked to any
  inbound thread at all — a bug, usually a missed import step).
  Stop and surface it; drafting with no thread context at all is
  worse than no draft.
- The inbound subject itself is the reason you cannot thread (the
  reporter sent the report with an empty subject, a generic
  *"Security"*, or a subject that collides with dozens of unrelated
  threads in the user's inbox). A same-subject draft would attach
  to the wrong conversation on the recipient's side. Stop and ask
  the user to confirm a good subject manually.

## Special case — ASF-security relay

When the inbound report arrives via an ASF forwarder rather than
directly from the external reporter, the drafting shape changes
slightly (different `To:` / `Cc:`, relay-specific body language) but
the threading rules above are **unchanged**: resolve and attach to
the inbound thread (`replyToMessageId` on the default backend,
`threadId` on `oauth_curl`); fall back to the inbound subject when
the thread cannot be resolved. See [`asf-relay.md`](asf-relay.md).
