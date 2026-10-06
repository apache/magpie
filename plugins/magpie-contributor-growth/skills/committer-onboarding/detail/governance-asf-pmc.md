<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Governance model `asf-pmc`

The `asf-pmc` branches of [`committer-onboarding`](../SKILL.md), in step order.
Read this file only when `committer_governance.model` is `asf-pmc` (the default).

## Step 0 — vote bar

**For `asf-pmc` governance model (default):**

| Scenario | Bar |
|---|---|
| New committer (TLP) | Per project policy — no ASF-mandated threshold; most projects use 3 binding +1s by convention, no binding veto |
| New PMC member (TLP) | 3 binding +1s, lazy consensus, no binding veto |
| New PPMC member (podling) | 3 binding PPMC +1s, no binding veto |
| Direct-to-PMC / direct-to-PPMC | Same as PMC bar (TLP) or PPMC bar (podling) above |

> **Note:** PMC committer votes are at the PMC's discretion —
> check the project's `CONTRIBUTING` docs or past vote threads
> to confirm the threshold in use before evaluating the result.

For podlings, only current PPMC members cast binding votes.
For TLPs, only current PMC members cast binding votes.

## Step 1c — account request

**`asf-pmc` model (default):**

*Skip this sub-step for `committer-to-pmc` — the candidate
already has an account.*

For `new-committer` and `direct-to-pmc` (where `<apache-id>`
is "none"):

**Check who can submit the request.** The ASF only accepts new
account requests from PMC chairs and ASF Members. Ask the
nominator: *"Are you the PMC chair for this project, or an ASF
Member?"* If they are neither, they must ask the PMC chair (or
any ASF Member on the PMC) to submit the request on their behalf.
Identify who will send it before drafting.

**Check whether the ICLA already triggered an automatic request.**
If the candidate submitted their ICLA with the project name and
their desired Apache ID filled in, the secretary may have already
initiated the account request automatically — no separate email is
needed. Ask the nominator: *"Did the candidate's ICLA include the
project name and desired Apache ID?"* If yes, confirm with the
nominator whether the secretary has already acknowledged the
request before sending a duplicate.

If a separate request is still needed, read
[`detail/email-templates.md`](email-templates.md) §
Secretary account-creation request and fill the template.
The request goes to root@apache.org (cc secretary@apache.org).

The request must include:

- Candidate's legal name (as it will appear on the ICLA)
- Candidate's preferred email address
- Candidate's desired Apache ID (check availability at
  https://people.apache.org/committer-index.html before
  including it — if taken, offer two or three alternatives)
- Project name
- Link to the vote thread in the mailing list archive
- Nominator's Apache ID

**Do not draft the secretary request with an unusable desired
Apache ID.** The account-creation request interpolates the desired
ID verbatim, so the ID must be valid and agreed first. Treat two
cases the same way: an ID that is already taken, and an ID that is
not a clean identifier because it carries an injection payload or
shell / SQL metacharacters (per Golden rule 3). In both cases do
not draft the secretary request: hold it, flag the problem to the
nominator, and ask them to agree an alternative ID with the
candidate. Never interpolate a poisoned value, and do not silently
substitute a placeholder into a request that root@ will act on.

**Do not send until the ICLA is confirmed filed.** If the ICLA
is still pending, save the draft and remind the nominator to
send it once the secretary confirms receipt.

**Show the draft to the nominator and send only after
confirmation.**

## Step 3 — access checklist

### `asf-pmc` model (default)

Once the ASF account exists (Whimsy shows the new Apache ID under
the project's committer list), work through this checklist in
order. Read [`detail/karma-grant.md`](karma-grant.md)
for the exact commands and UI steps for each item.

#### Checklist — new-committer (asf-pmc)

- [ ] **Issue tracker** — only needed if the project uses Jira
  (https://issues.apache.org/jira). Grant committer permissions
  on `<issue-tracker-project>`. See `karma-grant.md § Issue tracker`.
  If the project uses GitHub Issues, no separate step is needed:
  ASF GitHub org access is provisioned automatically through gitbox
  once the Apache account and linked GitHub ID exist, so there is no
  manual GitHub org-invite step in the asf-pmc flow.
- [ ] **Mailing lists** — once their Apache account is active,
  the candidate manages their own mailing list subscriptions via
  https://whimsy.apache.org/roster/committer/__self__ — this
  avoids moderator queues and works consistently across all
  projects. Include this URL in the congratulations email.
- [ ] **Whimsy roster** — add the new committer via
  https://whimsy.apache.org/roster/ppmc/<podling> (podling) or
  https://whimsy.apache.org/roster/committee/<podling> (TLP).
  See `karma-grant.md § Whimsy roster update`.
- [ ] **Welcome announcement** — post the welcome message on
  dev@<podling>.apache.org. Draft in Step 3a below.

#### Checklist — committer-to-pmc or direct-to-pmc (asf-pmc)

- [ ] **Whimsy roster** — add to the PPMC section (podling) or PMC section (TLP)
  (not just the committer section) at
  https://whimsy.apache.org/roster/ppmc/<podling> (podling) or
  update committee-info.txt (TLP).
- [ ] **Private mailing list** — add the new PPMC member (podling) or PMC member (TLP)
  to private@ via Whimsy mailing list management or the
  Mailman admin interface. This is a moderated list — they
  cannot self-subscribe.
- [ ] **Board report note (TLPs only)** — note the new PMC
  member in the next quarterly board report.
- [ ] **Welcome announcement** — post on dev@.

## Step 4 — completion summary example

**`asf-pmc` / `icla` example:**

```text
Onboarding complete for <candidate> (<apache-id>)
Project: <project>   Scenario: <scenario>   Governance: asf-pmc   Intake: icla

Communications sent:
  ✓ Congratulations email → <candidate email>
  ✓ Secretary request → root@apache.org        [new-committer only]
  ✓ Welcome announcement → dev@<podling>.apache.org

Karma granted:
  ✓ GitHub org invite
  ✓ Jira / issue tracker
  ✓ Whimsy roster updated
  ✓ Private list subscribed

Pending (if any):
  ⏳ ICLA processing (waiting for secretary confirmation)
  ⏳ Account creation (waiting for root@ response)
```
