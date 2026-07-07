<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Forwarder-routing policy](#forwarder-routing-policy)
  - [When does via-forwarder mode apply?](#when-does-via-forwarder-mode-apply)
  - [Milestones — DO relay](#milestones--do-relay)
  - [Events handled outside this policy](#events-handled-outside-this-policy)
  - [Negative space — DO NOT relay](#negative-space--do-not-relay)
  - [Implementation in the skills](#implementation-in-the-skills)
  - [Worked examples](#worked-examples)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Forwarder-routing policy

When a security tracker has **no direct way to reach the original
reporter** — there is no individual reporter email, GitHub Private
Reporting access is read-only, or the report arrived through a
forwarding service — the skills route reporter-facing communication
through whoever delivered the report to us instead (the *forwarder*
— typically a relay broker addressable at
`forwarders.<adapter>.contact_handle` per
[`<project-config>/project.md`](../../projects/_template/project.md),
or an internal security-team member who opened the tracker on
someone else's behalf). The ASF-Airflow default has the ASF Security
team relaying via `<security-list>` (the
`foundation_security_address` shared inbox).

In that **"via-forwarder" mode**, only **important milestones** are
relayed. Regular workflow chatter and credit-confirmation
questions are **not** sent to the forwarder — they would burn the
forwarder's goodwill with low-signal updates the forwarder has no
useful reply to.

This file is the single source of truth for *when* the
via-forwarder mode applies and *what* gets relayed.

## When does via-forwarder mode apply?

The mode applies to a tracker when **any** of the following is true:

1. **Forwarder-adapter relay.** The inbound report came from one
   of the adapters enabled in `forwarders.enabled` with that
   adapter's preamble; the original reporter is not addressable
   directly on the relayed thread. The relay broker's personal
   address (or, where the adapter declares it, the adapter's
   `contact_handle`) is the **forwarder contact**. The ASF-Airflow
   default is the `asf-security` adapter at
   [`tools/forwarder-relay/README.md`](../../tools/forwarder-relay/README.md),
   with the per-message detection mechanics described in
   [`tools/gmail/asf-relay.md`](../../tools/gmail/asf-relay.md).
2. **GitHub Private Reporting we cannot reply on.** A GHSA-style
   private report we have read access to but can't post comments
   on as a security team. Whoever made us aware of the GHSA
   (typically the same relay broker, or an internal escalation
   thread) is the forwarder.
3. **`security-issue-import-from-md`-imported tracker.** The
   tracker came from a markdown file (AI scan / third-party scan
   output) with no inbound reporter at all. There is no reporter to
   relay to; treat the security-team member who ran the import as
   the forwarder for any *"additional information"* questions.
4. **Explicit no-direct-contact marker.** A security-team member
   sets the marker comment

   ```html
   <!-- apache-magpie: routing-mode via-forwarder -->
   ```

   on the tracker (one line in the body, or as the first line of a
   pinned comment) and names the forwarder contact in the comment
   body. This is the fall-through escape hatch for cases the
   automatic detection above misses — an internal escalation, a
   chat-only report, a printed letter, anything else where the
   normal reporter address simply does not exist.

The trackers opened by
[`security-issue-import-from-pr`](../../skills/security-issue-import-from-pr/SKILL.md)
are a **separate case** with its own *no outreach to the PR
author* rule (see that skill's `Reporter credit policy for
public-PR imports` section). The forwarder-routing policy does
**not** apply there — the PR author is not someone we are
deliberately relaying through, just someone whose public PR we
imported. No reporter-facing drafts of any kind are proposed.

## Milestones — DO relay

Only these events warrant a draft to the forwarder. They map 1:1
to the lifecycle decisions a reporter (or the team that relayed
on their behalf) would actually want to hear about:

| Milestone | Where it fires | Draft body summary |
|---|---|---|
| **Report accepted as valid** | After Step 5 lands a `valid` consensus + scope label applied | *"We received the report you forwarded; the team has confirmed it as valid. A CVE will be allocated next; we will write again when the advisory is sent. If you can pass this update back to the original reporter, please do; if you can also ask them to reply with their preferred credit form, that would help — otherwise we'll proceed with the credit line in the original report."* |
| **Report assessed as invalid** | [`security-issue-invalidate`](../../skills/security-issue-invalidate/SKILL.md) — closing reply | *"The team has assessed the report you forwarded and concluded it is not a security vulnerability. Reasoning: \<one-paragraph summary\>. If you (or the original reporter) want to challenge the assessment, please reply with the additional context; otherwise this is our final disposition."* |
| **Advisory sent** | [`security-issue-sync`](../../skills/security-issue-sync/SKILL.md) Step 14 close-out — after the advisory archive URL is captured | *"The advisory for `CVE-YYYY-NNNNN` has been sent and is archived publicly at `<URL>`. This completes the lifecycle for the report you forwarded; thank you for the relay."* |
| **Additional information requested** | Any skill that needs a specific clarification from the reporter (re-reproduction steps, attack-vector clarification, affected-version range) | *"We need additional information to assess the report you forwarded: `<specific question(s)>`. If you can relay this to the original reporter and pass back a reply, that would help us land a decision."* |

The drafts go to the **forwarder contact**, not to the relay list
address — same rule as the forwarder-relay adapter contract in
[`tools/forwarder-relay/README.md`](../../tools/forwarder-relay/README.md)
(ASF-Airflow default: the `asf-security` adapter detailed in
[`tools/gmail/asf-relay.md`](../../tools/gmail/asf-relay.md)). The
body is short, references the external identifier (GHSA ID,
HackerOne URL, internal ticket number) when one exists, and never
re-states the technical detail of the report.

## Events handled outside this policy

Some lifecycle events generate reporter-facing notifications
*outside* this policy's milestone / negative-space rules. They
fire **the same way in both direct-reporter and via-forwarder
modes** — no recipient swap, no body-shape swap, no
suppression.

* **CVE allocated**
  ([`security-cve-allocate`](../../skills/security-cve-allocate/SKILL.md)
  Step 4 #5). The `<cve-tool>` adapter typically emits its own
  allocation notification when the CVE record is created
  (`cve_authority.emits_allocation_email: true` for the
  ASF-Airflow Vulnogram default), and even when it doesn't, the
  team owes the reporter (or their forwarder) a single short
  notification at this point regardless of routing mode. The
  notification lands on whatever thread the tracker's *Security
  mailing list thread* field resolves to; in via-forwarder mode
  that is the relay thread, so the same draft reaches the
  forwarder without any policy-specific re-routing. The
  credit-preference question is still suppressed in via-forwarder
  mode (per the
  [Negative space](#negative-space--do-not-relay) section
  below) but the rest of the CVE-allocated notification still
  fires.

Future events that follow the same shape (independent of
routing mode, not subject to milestone-only suppression) belong
here. Add a bullet and a one-paragraph explanation; do **not**
hide the event by silently omitting it from the milestone list.

## Negative space — DO NOT relay

These events would generate a draft in *direct-reporter* mode but
are **suppressed** in via-forwarder mode:

* **Regular workflow status** — `pr created` / `pr merged` /
  `fix released` label transitions. The forwarder has no actionable
  reason to learn about these intermediate states; the next
  forwarder-bound message is at advisory-sent (the *Advisory sent*
  milestone above).
* **Credit-acceptance confirmations** — i.e. messages asking the
  reporter to *confirm receipt and acceptance of the credit line
  the team plans to use*. The standalone
  [bot/AI credit-clarification draft](../../tools/cve-tool-vulnogram/bot-credits-policy.md)
  belongs to this class (it asks *"is this AI/bot handle the
  intended credit, or should we credit someone else?"* — a
  confirmation prompt on a proposed credit). So do the
  follow-up chase-ups *"please confirm we will credit you as
  X"* that direct-reporter sync passes would otherwise generate
  when the reporter has gone silent. The forwarder cannot
  meaningfully accept a credit on behalf of the original
  reporter, so the prompt bounces back and burns goodwill.

  **The credit *question* itself is not suppressed.** Folding
  a single short *"if the reporter has a preferred credit form,
  please pass it back"* line into a milestone draft (the Step 7
  receipt-of-confirmation, the *Report accepted as valid*
  milestone, or the *CVE allocated* notification per the
  [Events handled outside this policy](#events-handled-outside-this-policy)
  section) is fine — the forwarder might know, or might be
  able to relay the question through the original channel. The
  distinction is:

  * *Question* (allowed): a one-line ask included in a
    milestone message the team is already sending. Cheap; the
    forwarder either knows or can relay or drops it.
  * *Confirmation* (suppressed): a message whose entire purpose
    is to get the reporter to *accept* a credit line the team
    has chosen. Demands a reply the forwarder can't supply, so
    it becomes a chase-up loop.

  The bot-credit detection still runs in via-forwarder mode and
  still filters the auto-extracted credit before it lands in
  the body field; it just does not generate its own
  confirmation message.
* **Reviewer-comment relays.** CVE reviewer feedback that lands on
  `<security-list>` is handled by the security team internally; the
  forwarder is not on that loop and does not need to be.
* **Sync-rollup notifications.** The internal rollup comments
  `security-issue-sync` posts on the tracker stay on the tracker —
  they are for the security team, not for the forwarder.

## Implementation in the skills

Each skill that composes a reporter-facing draft checks the
tracker's routing mode (using the detection rules in this doc) and
applies one of three behaviours:

1. **Direct-reporter mode** (the common case) — proceed exactly as
   the skill's existing draft logic prescribes.
2. **Via-forwarder mode + the event is on the milestone list** —
   compose the draft to the forwarder contact instead of the
   reporter, using the short milestone-body shape above. Reference
   the external identifier rather than the technical detail.
3. **Via-forwarder mode + the event is NOT on the milestone list**
   — suppress the draft entirely. Record in the proposal recap
   *"skipped draft: `<event>` not on the via-forwarder milestone
   list"* so the user can see why no message was proposed.

The detection runs once per skill invocation; subsequent dispatch
through the skill is consistent for that run.

The detection itself is the responsibility of the optional sub-skill
[`security-issue-import-via-forwarder`](../../skills/security-issue-import-via-forwarder/SKILL.md),
which dispatches through whichever adapter from `forwarders.enabled`
matches the inbound message (per
[`tools/forwarder-relay/README.md`](../../tools/forwarder-relay/README.md)).
Skills load the sub-skill only when `forwarders.enabled` is
non-empty in `<project-config>/project.md`; when the list is empty,
via-forwarder mode falls back to the marker-comment escape hatch and
the `security-issue-import-from-md` import case.

## Worked examples

**Forwarder-relayed GHSA report, advisory sent.** A report arrives
via the configured forwarder adapter (ASF-Airflow default:
`asf-security` carrying the relay preamble) with a GHSA reference;
the import skill classifies it as a forwarder-relay match, drafts
the Step 7 receipt to the forwarder contact (the relay broker's
personal address — for ASF-Airflow, the forwarding ASF Security
team member, e.g. `@raboof` per
`forwarders.asf-security.contact_handle`). Weeks later the fix
ships and the advisory is archived on the project's public users
list (per `archive_system.advisory_publication_signal_url`);
`security-issue-sync` Step 14 captures the URL and proposes an
*Advisory sent* milestone draft to the same forwarder contact:
*"The advisory for `<CVE-ID>` has been sent and is archived
publicly at `<URL>`. This completes the lifecycle for the report
you forwarded; thank you for the relay."* No technical detail is
restated. (The intermediate *CVE allocated* notification landed
on the same thread per the
[Events handled outside this policy](#events-handled-outside-this-policy)
rule, so the forwarder already saw it.)

**Bot-credit candidate in via-forwarder mode.** The relayed report
names the discoverer as `Automated Scanner v3`. The bot-credit
policy detects the match and would normally propose a
clarification draft to the reporter. In via-forwarder mode the
clarification draft is **suppressed**; the credit field stays at
`_No response_` until the next milestone draft, where a single
line *"if the original reporter has a preferred credit form,
please pass it back"* is folded in.

**Internal-escalation tracker.** A `governance.cve_allocation_gate`-
authorised member (ASF-Airflow default: a PMC member) forwards a
private internal report to the security team verbally; the
security team opens the tracker by hand and writes the
`<!-- apache-magpie: routing-mode via-forwarder -->` marker
comment naming the governance-authorised member as the forwarder
contact. From that point on, every sync skill that would draft to
a reporter routes to the named contact instead, and milestone-only
suppression applies as if the tracker had come in via a
forwarder-adapter relay.
