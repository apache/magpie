<!-- SPDX-License-Identifier: Apache-2.0 -->
# Email templates

Fill every `<placeholder>` before showing the draft to the
nominator. Do not send any of these without explicit nominator
confirmation.

---

## Congratulations email

**To:** `<candidate email>`
**Bcc:** `private@<podling>.apache.org`
**Subject:** Welcome to Apache <project> — invitation to become a committer

```text
Dear <candidate>,

On behalf of the <project> Project Management Committee (PMC)
[or PPMC, for incubating projects], I am delighted to let you
know that the project has voted to invite you to become a
committer.

Your contributions — <one or two sentences summarising what
the candidate did, taken from the nomination brief> — have made
a real difference to the project, and we look forward to your
continued involvement.

[INCLUDE THE FOLLOWING BLOCK ONLY IF ICLA IS NOT YET ON FILE:]
───────────────────────────────────────────────────────────────
Before we can create your Apache account, the Apache Software
Foundation requires you to file an Individual Contributor
License Agreement (ICLA).  Please:

1. Download the ICLA form:
   https://www.apache.org/licenses/icla.pdf

2. Fill in your legal name, postal address, preferred email
   address, and — in the "username" field — your preferred
   Apache ID (a short, lowercase identifier, e.g. "jsmith").
   Check that the ID is not already taken:
   https://people.apache.org/committer-index.html

3. Sign the form (electronic signatures are accepted) and
   email it to secretary@apache.org.  Include "<project>"
   and your preferred Apache ID in the subject line.

4. Reply to this email once you have filed it so that I can
   follow up with the secretary.

Account creation typically takes a few business days after the
ICLA is processed.
───────────────────────────────────────────────────────────────
[END ICLA BLOCK]

[INCLUDE THE FOLLOWING BLOCK ONLY IF ICLA SUBMITTED BUT NOT YET PROCESSED:]
───────────────────────────────────────────────────────────────
Thank you for submitting your ICLA — the secretary will process
it shortly. Once it has been processed and your Apache account
is created, we will grant you access to the project's
repositories and mailing lists.

If you have not already done so, please confirm with the
secretary (secretary@apache.org) that your filing was received.
We will follow up with them on the account-creation request
once it appears in the system.
───────────────────────────────────────────────────────────────
[END ICLA SUBMITTED BLOCK]

[INCLUDE THE FOLLOWING BLOCK ONLY IF APACHE ID ALREADY EXISTS:]
───────────────────────────────────────────────────────────────
Since you already have an Apache account (<apache-id>), we will
add you to the project's committer roster on Whimsy shortly.
You will receive a separate notification from Whimsy once that
is done.
───────────────────────────────────────────────────────────────
[END EXISTING ACCOUNT BLOCK]

Once your account is set up you will have access to the
project's repositories and issue tracker. Once your Apache account is active you can manage your
mailing list subscriptions at:
https://whimsy.apache.org/roster/committer/__self__

[INCLUDE THE FOLLOWING LINE ONLY FOR PMC TARGETS (TLP) OR PPMC TARGETS (PODLING):]
You will also be subscribed to the project's private mailing
list — you should receive a confirmation shortly.
[END PMC/PPMC LINE]

Please feel free to reply to this email if you have any
questions.  We're excited to have you on board!

On behalf of the <project> PPMC,  [use PMC for TLPs]
<nominator name> (<nominator apache-id>@apache.org)
```

---

## Secretary account-creation request

**To:** `root@apache.org`
**Cc:** `secretary@apache.org`
**Subject:** [ACCOUNT REQUEST] <project> — <candidate name>

> **Send only after ICLA is confirmed filed and processed.**
> If unsure, ask the nominator to confirm with
> secretary@apache.org before sending this email.

```text
Hi,

Please create an Apache account for a new committer on the
Apache <project> project [or: Apache <project> podling,
currently in the Apache Incubator].

  Legal name:        <candidate legal name as on ICLA>
  Preferred email:   <candidate email>
  Desired Apache ID: <desired-id>
                     (verified available at
                      https://people.apache.org/committer-index.html
                      as of <check-date>)
  Project:           <project>
  Role:              Committer [and PPMC member (podling) / PMC member (TLP), if applicable]

Vote thread:
  <vote-thread-url>

The ICLA was filed on <icla-file-date> (or: "The candidate
already has an Apache account — this request is for PMC/PPMC
roster addition only", if applicable).

Please let me know if you need anything else.

Thanks,
<nominator name> (<nominator-apache-id>@apache.org)
<project> PMC chair  [use PPMC for podlings]
```

---

## Welcome announcement

**To:** `dev@<podling>.apache.org`
**Subject:** [ANNOUNCE] New committer — <candidate name>

> Post this publicly only *after* the account exists and
> karma has been granted.

```text
Hi all,

I am pleased to announce that <candidate name> has accepted
our invitation to become a committer on Apache <project>.

<One or two sentences about what the candidate has contributed,
taken from the nomination brief.  Keep it factual and warm.>

Please join me in welcoming <candidate first name> to the team!

<nominator name>
On behalf of the <project> PMC  [use PPMC for podlings]
```
