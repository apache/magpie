<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Editorial guidelines](#editorial-guidelines)
  - [Tone: polite but firm — no room to wiggle](#tone-polite-but-firm--no-room-to-wiggle)
  - [Brevity: emails state facts, not context](#brevity-emails-state-facts-not-context)
  - [Threading: drafts stay on the inbound Gmail thread](#threading-drafts-stay-on-the-inbound-gmail-thread)
  - [ASF-security-relay reports: a special case for drafting](#asf-security-relay-reports-a-special-case-for-drafting)
  - [Point reporters to the project's Security Model, don't re-explain it](#point-reporters-to-the-projects-security-model-dont-re-explain-it)
  - [Reporter claims about dependencies: conditional language only](#reporter-claims-about-dependencies-conditional-language-only)
  - [Linking CVEs](#linking-cves)
    - [Reporter emails: CVE ID only, never the ASF CVE-tool URL](#reporter-emails-cve-id-only-never-the-asf-cve-tool-url)
  - [Linking tracker issues and PRs](#linking-tracker-issues-and-prs)
    - [On markdown surfaces](#on-markdown-surfaces)
    - [On terminal surfaces](#on-terminal-surfaces)
    - [Confidentiality applies to *contents*, not to identifiers](#confidentiality-applies-to-contents-not-to-identifiers)
    - [Editing rules](#editing-rules)
  - [Mentioning project maintainers and security-team members](#mentioning-project-maintainers-and-security-team-members)
  - [Other editorial guidelines](#other-editorial-guidelines)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Editorial guidelines

The detailed editorial playbook for text this framework produces — canned
responses, reporter-facing emails, status comments, CVE and tracker links,
and maintainer mentions. [`AGENTS.md`](../AGENTS.md#writing-and-editing-documentation)
carries the load-bearing summary of each rule; this file is the full
reference an agent loads before drafting or editing reporter-facing or
tracker-facing text.

The documents in this repository are short and opinionated. When editing them,
prefer small, targeted improvements over rewrites, and preserve the existing
structure (including the `doctoc`-generated tables of contents) unless the
change is explicitly about structure.

## Tone: polite but firm — no room to wiggle

The canned responses in
[`<project-config>/canned-responses.md`](<project-config>/canned-responses.md)
are the public face of the security team. They are often sent to reporters
whose submissions have been assessed as invalid or out of scope. The tone
must be:

1. **Polite and professional.** Thank the reporter, acknowledge the intent, stay neutral.
2. **Firm and unambiguous.** State the outcome as a decision, not as a negotiation. The response
   is an expectation, not a suggestion.
3. **Free of accusation, sarcasm, and condescension.** Never imply the reporter "didn't bother
   to read", never say things like "Two reasons indicate that you did not", never tell them to
   "digest" the security model. These phrasings leave bad taste and, worse, invite argument.
4. **Free of hedging.** Avoid phrases like "feel absolutely free", "we would appreciate if you
   stopped", or "we would kindly ask you to consider" — they weaken the message and imply the
   expectation is optional. Prefer "please do not use this address for such requests" or "we are
   unable to treat this as a security issue unless…".

Concrete phrasing patterns that work well:

- Lead with: *"Thank you for the report."* Then state the outcome.
- State the decision in plain terms: *"We do not consider this a vulnerability."* / *"We cannot
  accept this report."* / *"This is explicitly out of scope for our security process."*
- Anchor the decision in an authoritative document, not in the responder's opinion:
  *"… is documented in our Security Model under '…': <link>."*
- When describing consequences of repeated policy violations, use passive, factual language:
  *"Accounts that repeatedly send reports which do not meet the policy are added to a deny list."*
  Do not threaten.
- End with a constructive alternative where one exists: *"We would welcome a PR through the
  regular contribution process."*

## Brevity: emails state facts, not context

Every outbound email drafted by a skill — status updates to reporters,
escalation messages to `<private-list>`, relay requests to
PMC members, communications to the ASF security team (`cve-managers@`,
`security@apache.org`) — must be **short and factual**. The recipient
already has the context; the point of the message is to deliver new
information.

**Baseline shape.** A status-update email to a reporter should fit in
three short paragraphs or less:

1. One sentence stating **what changed** (CVE allocated, fix PR
   opened, advisory sent, etc.).
2. One sentence stating **what comes next** and roughly when (e.g.
   *"The advisory will be sent once the fix ships, currently expected
   with the next patch release."*).
3. The relevant **artifact URLs** on their own line(s) — CVE tool
   link, PR URL, advisory archive URL — per the linking rules in
   [Linking CVEs](#linking-cves) and
   [Linking tracker issues and PRs](#linking-tracker-issues-and-prs).
   Gmail autolinks bare URLs; do not use markdown or shorthand.

That is the entire body. No re-introduction of the vulnerability, no
recap of earlier messages on the same thread, no explanation of the
handling process, no speculation about severity or timelines beyond
the single forward-looking sentence in paragraph 2.

**Emails to the ASF security team are even shorter.** The ASF CVE
managers and the ASF security team already know the project's
process, the Vulnogram tool, and the CVE-5 schema. A message to
them is a **request or a fact**, not a briefing:

- Lead with the ask or the fact in one sentence (*"Please push the
  attached credit correction to cve.org for CVE-YYYY-NNNNN."*).
- Include only the minimum artifact the recipient needs to act (the
  CVE ID, the corrected JSON, the archive URL) — one link, maybe two.
- Do **not** restate the vulnerability, the project's release train,
  or the history of the ticket.
- Do **not** explain why the ASF team's action is needed when their
  role in the process is already established (e.g. pushing to cve.org,
  allocating a CVE from a PMC-gated form).

**What to omit in every drafted email, reporter or otherwise:**

- The vulnerability description or attack narrative — the recipient
  read it in the previous message on the thread or knows it from the
  tracker.
- A recap of earlier status updates ("As you know, we confirmed
  validity on X and allocated the CVE on Y…").
- Security-model paraphrasing — link to the chapter, do not
  re-explain (per
  [Point reporters to the project's Security Model, don't re-explain it](#point-reporters-to-the-projects-security-model-dont-re-explain-it)).
- Inflated closings ("We greatly appreciate your continued
  patience…"). A plain *"Thanks,"* / *"Regards,"* is enough.
- Any open question that was already asked on the thread and is
  still awaiting a reply (see the "Do not re-ask" rule in the
  `security-issue-sync` skill — pinging twice gets us blocklisted).

**Exception: the initial receipt-of-confirmation reply.** The first
message the security team sends to a new reporter, drafted by the
`security-issue-import` skill, uses the *"Confirmation of receiving
the report"* canned response from
[`<project-config>/canned-responses.md`](<project-config>/canned-responses.md)
**verbatim**. That template is longer because it introduces the process
to a reporter who has not yet seen it and carries the credit-preference
question; leave it alone and do not trim it per this brevity rule.

Everything else — every follow-up, every status update, every relay
to a PMC member, every message to the ASF security team — falls
under this rule.

## Threading: drafts stay on the inbound Gmail thread

Every drafted email that relates to a tracking issue **should**
attach to the original inbound Gmail thread. On the default
`claude_ai_mcp` backend, that means resolving the thread's latest
message ID (via `get_thread`) and passing it to `create_draft` as
`replyToMessageId`; on the opt-in `oauth_curl` backend it means
passing the `threadId` to `oauth-draft-create --thread-id`. The
pragmatic fallback — when the inbound thread cannot be resolved —
is to omit the thread-attachment parameter and create the draft
with the matching `Re: <root subject>` line, which most clients
still thread by subject. The full rule (when each path applies,
when to stop instead, how to surface the degraded threading in the
skill's proposal) lives in
[`tools/gmail/threading.md`](../tools/gmail/threading.md).

## ASF-security-relay reports: a special case for drafting

Some reports reach the project's security list via the ASF security
team (from `security@apache.org`, or a personal `@apache.org` address
of an ASF-security-team member) rather than from the external reporter
directly. The drafting rules for that case — different `To:`, same
threading behaviour (attach to the inbound thread, fall back to the
inbound subject when the thread cannot be resolved), terse body — live in
[`tools/gmail/asf-relay.md`](../tools/gmail/asf-relay.md). The detection
signals the `security-issue-import` skill uses to classify a candidate
as a relay live in that skill's Step 3.

## Point reporters to the project's Security Model, don't re-explain it

The project's Security Model is the authoritative source for what is and
is not considered a security vulnerability. Canned responses must link
directly to the relevant chapter instead of paraphrasing it. Paraphrases
drift over time and create a second source of truth that has to be
maintained.

The authoritative URL and known-useful anchors for the currently active
project live in
[`<project-config>/security-model.md`](<project-config>/security-model.md).
When adding a new canned response, identify the matching chapter in the
Security Model first. If no chapter covers the case, that is a signal
the Security Model should be updated upstream (in the project's source
repository) rather than duplicated in the canned responses.

## Reporter claims about dependencies: conditional language only

When a reporter says the vulnerability they found lives in **one of
the project's dependencies** (a third-party library, a transitive
package, an upstream tool the project bundles), drafted replies
must **not adopt the claim as fact**. The project's security team
has no authority to confirm a vulnerability in code it does not
maintain — that judgement belongs to the dependency's own
maintainers and CNAs.

Use **conditional phrasing** in every reply that touches the
claim:

- ✗ *"Thanks for finding this vulnerability in `<library>`."* —
  endorses the claim.
- ✗ *"We've confirmed the issue in `<library>` is exploitable
  through our usage."* — endorses the claim plus a downstream
  consequence.
- ✓ *"Thanks for the report. We're forwarding your finding to
  `<library>`'s maintainers; if confirmed there, we will reassess
  whether our usage exposes it."*
- ✓ *"We will track the upstream report. Once `<library>` issues
  an advisory, we will evaluate the impact on our deployment."*

Why this matters:

- The reporter can screenshot or forward a confirmation in our
  voice as evidence of an unconfirmed vulnerability in a
  third-party project — pressuring its maintainers and damaging
  relationships the project depends on.
- A wrong endorsement (the dependency maintainers disagree, or
  the behaviour turns out to be intentional / not exploitable as
  described) becomes a public correction the team has to retract.
- We may not have the deployment context to know whether the
  claimed primitive is reachable in our usage at all. A
  conditional reply is honest about that.

This rule pairs with
[Reporter-supplied CVSS scores are informational only](../AGENTS.md#reporter-supplied-cvss-scores-are-informational-only--never-propagate-them):
the team independently assesses anything that ends up attributed
to the project's voice. Dependency claims are the same shape — a
position from the reporter the team has not yet evaluated.

When the report turns out to describe a real vulnerability in the
project's **own** code that *happens to involve* a dependency
(e.g. the project calls the dependency's API in a way that
exposes a primitive), this rule no longer applies — that finding
is the project's and the reply can state it plainly per the
brevity rule above.

## Linking CVEs

Whenever a CVE ID appears in text this repository produces — status
comments on `<tracker>` issues, proposals from the
`security-issue-sync` skill, recap messages, canned-response drafts
to reporters, internal notes — render it as a **clickable link**,
not as bare text. The canonical link is the adopting project's CVE-tool
record URL, which any security team member can click through to the
live CVE record we control:

```text
https://cveprocess.apache.org/cve5/<CVE-ID>
```

Example:

> [`CVE-2026-40690`](https://cveprocess.apache.org/cve5/CVE-2026-40690)

For CVEs that have already been **published** (the advisory has been sent
to `<users-list>`, the issue carries `vendor-advisory`, and the
CVE record is visible on public databases), additionally link to the public
`cve.org` / MITRE record so non-security-team readers can see the public
description without needing access to the ASF tool:

```text
https://www.cve.org/CVERecord?id=<CVE-ID>
```

A published CVE should appear with both links, for example:

> `CVE-2025-50213` ([ASF](https://cveprocess.apache.org/cve5/CVE-2025-50213),
> [cve.org](https://www.cve.org/CVERecord?id=CVE-2025-50213))

`https://nvd.nist.gov/vuln/detail/<CVE-ID>` is an acceptable alternative to
`cve.org` once NVD has scored the record. Before publication, `cve.org`
shows the CVE as RESERVED with no details — skip the public link in that
case and link only to the ASF tool.

**Confidentiality**, as a cross-reference to the
[Confidentiality of the tracker repository](../AGENTS.md#confidentiality-of-the-tracker-repository)
section:

- CVE-tool links are fine inside `<tracker>` private comments, in
  rollup entries, in skill proposals, and in notes the security team
  reads — every one of those surfaces is viewed by collaborators
  who can authenticate against the ASF CVE tool.
- **Reporter emails never carry the CVE-tool URL** — see the
  subsection immediately below.
- Public `<upstream>` PR descriptions, public mailing-list posts,
  and any other public surface **must not** link to the CVE tool
  before the advisory is sent — doing so implies the existence of
  the private tracking issue. Once the advisory is public, link
  only to `cve.org` (or NVD), never to the CVE tool.

When editing an existing document that contains a bare `CVE-YYYY-NNNNN`
string, convert it to the linked form in the same edit — **except**
in reporter-facing email drafts, which follow the rule below.

### Reporter emails: CVE ID only, never the ASF CVE-tool URL

Emails drafted to a reporter on `<security-list>` — receipt-of-
confirmation replies, status updates, advisory notifications, credit
corrections, CVE-publication notifications — **must not** contain the
ASF CVE-tool URL (`https://cveprocess.apache.org/cve5/<CVE-ID>`).

**Why:**

- The ASF CVE tool is gated behind ASF OAuth. An external reporter
  clicking that URL gets a login page they cannot resolve; the link is
  dead weight at best and confusing at worst.
- The tool is internal security-team infrastructure. Putting its URL in
  front of an external party exposes internal tooling that the reporter
  has no reason to see, and invites questions about the record that the
  team would prefer to answer on its own cadence.
- The CVE ID alone is the public identifier. Once the record publishes
  on `cve.org`, the reporter can look it up there. Before publication,
  no external database has details, and the CVE ID as text is exactly
  the right amount of information for the reporter to file or cross-
  reference.

**How to reference a CVE in a reporter email:**

- **Before publication** (CVE is `RESERVED` on `cve.org`): write the
  CVE ID as plain inline text, e.g. *"… allocated CVE-2026-40690 for
  this issue …"*. Do not add a URL of any kind. Most email clients
  do not autolink `CVE-YYYY-NNNNN`, which is the intended behaviour —
  the reporter reads the ID, not a clickable link.
- **After publication** (advisory has been sent, CVE is visible on
  `cve.org`): the `cve.org` URL is acceptable if a clickable
  reference is worth including, e.g.
  `https://www.cve.org/CVERecord?id=CVE-2026-40690`. This is still
  optional — the CVE ID as plain text remains sufficient and is
  often cleaner.
- **Never** include `cveprocess.apache.org/cve5/<CVE-ID>` (or any
  other ASF CVE-tool URL) in the email body, quoted excerpt,
  footer, signature, or forwarded context. If a prior draft in the
  thread contained the URL, do not repeat it in the follow-up.

**Self-check before creating the Gmail draft:** grep the draft body
for the literal strings `cveprocess.apache.org` and
`cveprocess.apache.org/cve5/`; if either appears, remove the URL and
leave the bare CVE ID. The tracker-internal surfaces that the sync
and other skills write to (rollup entries, status comments, proposal
summaries) continue to link the ASF CVE-tool record as before —
this rule is specific to the outbound-reporter-email surface.

## Linking tracker issues and PRs

Whenever a reference to a `<tracker>` issue, pull request, comment,
or discussion appears in text this repository produces — sync / fix
skill proposals, status comments on the private issue itself, recap
messages, internal notes, `SKILL.md` files — the reference must be
**one click away** in whatever surface it lands on. Bare `#NNN` or
`<tracker>#NNN` with no link wrapper of any kind is never
acceptable.

The URL formats are:

```text
https://github.com/<tracker>/issues/<N>
https://github.com/<tracker>/pull/<N>
https://github.com/<tracker>/issues/<N>#issuecomment-<C>
https://github.com/<tracker>/milestone/<N>
```

### On markdown surfaces

Tracker comments, PR / issue bodies, README files, draft email text
destined for the `<security-list>` Gmail thread, `SKILL.md` files,
and any other markdown-rendered destination get the **markdown link
form**:

> [`<tracker>#221`](https://github.com/<tracker>/issues/221)

or, when the repository is already obvious from context (for example
inside a comment on `<tracker>#221` itself):

> [`#221`](https://github.com/<tracker>/issues/221)

Link both the number *and* any referenced comment / review by using
the per-comment anchor:

> [`<tracker>#216 — issuecomment-4252393493`](https://github.com/<tracker>/issues/216#issuecomment-4252393493)

### On terminal surfaces

CLI proposal previews, drill-in screens, hand-back artefacts, recap
output, session summaries, and any other terminal-bound output get
**OSC 8 hyperlink escape sequences** — the visible text stays the
short form (`<tracker>#NNN` or `#NNN`), the URL is wrapped invisibly
so modern terminals make the short text clickable:

```text
\e]8;;https://github.com/<tracker>/issues/221\e\\<tracker>#221\e]8;;\e\\
```

Terminals that honour OSC 8 today: **iTerm2, Kitty, GNOME Terminal,
WezTerm, Windows Terminal, Alacritty**, and most other modern
terminal emulators. When OSC 8 is unsupported (CI logs, `less`
without `-R`, dumb terminals, plain captures), fall back to printing
the bare URL on the same line after the number:

```text
<tracker>#221  https://github.com/<tracker>/issues/221
```

In Python, the OSC 8 wrapper is one helper away:

```python
def osc8(text: str, url: str) -> str:
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"

print(osc8("<tracker>#221", "https://github.com/<tracker>/issues/221"))
```

Equivalent helpers exist in Bash (`printf '\e]8;;%s\e\\%s\e]8;;\e\\' "$url" "$text"`)
and other languages — embed one wherever the skill prints user-visible
text.

### Confidentiality applies to *contents*, not to identifiers

See the
[Confidentiality of the tracker repository](../AGENTS.md#confidentiality-of-the-tracker-repository)
section. The rendered tracker links — markdown or OSC 8 form
— are stable identifiers that may appear on public surfaces (public
`<upstream>` PRs, reporter emails, advisory references). What still
must not appear publicly is the *contents* the link points at —
comment quotes, labels, body excerpts, severity assessments — and,
before the advisory ships, the security framing of the change. The
scrubbing grep the `security-issue-fix` skill runs before pushing
anything public flags content leaks (CVE IDs, *"vulnerability"*,
*"security fix"* phrasing, verbatim tracker quotes); a bare tracker
URL or `#NNN` reference on its own does not trigger the scrub.

### Editing rules

When editing an existing document in this repo that contains a bare
`#NNN` or `<tracker>#NNN`, convert it to the appropriate clickable
form for that document's surface in the same edit. Skill-generated
output (sync proposals, issue comments, email drafts to reporters
on the `<security-list>` thread, terminal previews shown before a
post, recap output) must emit the linked form from the start —
bare references are a miss.

**Self-check before emitting**: grep the text for bare `#\d+`
tokens that aren't already inside a markdown link, a raw
`https://...` URL, or an OSC 8 wrapper (`\033]8;;`), and convert
any match to the appropriate clickable form for the target
surface.

## Mentioning project maintainers and security-team members

When writing text that lands on a GitHub issue or PR and refers to a
specific project maintainer, committer, release manager, or security-
team member, **use the person's GitHub handle with the leading `@` so
GitHub notifies them**. Plain-text names do not fire notifications,
and the whole point of mentioning the person is usually that they own
the next step or are the right reviewer. Agent-generated status
comments, PR bodies, sync recaps, fix-PR follow-up comments, and
draft-advisory text should all follow the rule.

The project-specific roster rules (who the rule applies to, which
surfaces it applies to, public-surface caveats tied to this project's
confidentiality constraints, how external reporters are handled) live
in
[`<project-config>/naming-conventions.md`](<project-config>/naming-conventions.md#mentioning-airflow-maintainers-and-security-team-members).
The authoritative roster and the release-manager rotation list live in
[`<project-config>/release-trains.md`](<project-config>/release-trains.md).

The security-issue-sync and security-issue-fix skills should render
every maintainer / security-team / release-manager reference in the
status comments they post as an `@` handle. Before publishing a status
comment, the skills must grep for names of known people and flag any
bare-name occurrence to the user.

## Other editorial guidelines

- Project-specific naming rules (e.g. acronym casing,
  contributor-base size phrasing, project-name capitalisation
  conventions) live in
  [`<project-config>/naming-conventions.md`](<project-config>/naming-conventions.md).
- Use em dashes (`—`) sparingly; prefer shorter sentences to dash-heavy ones.
- Preserve the `doctoc` TOC markers at the top of each document. If you rename a heading, update
  the corresponding TOC entry in the same change.
- Do not add emojis.
