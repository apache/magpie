<!-- SPDX-License-Identifier: Apache-2.0 -->
# Email templates

Fill every `<placeholder>` before showing the draft to the nominator.
Do not send any of these without explicit nominator confirmation.

---

## Congratulations email

The ICLA block follows the ASF's own
[committer invitation template](https://community.apache.org/templates/committer-invite.txt);
when the two differ, the ASF template wins, and this file should be brought back in line with it.

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
If you accept, you will need an Apache account, and before it
can be created the Apache Software Foundation needs an
Individual Contributor License Agreement (ICLA) from you:

1. The ICLA form and its details are at:
   https://www.apache.org/licenses/#clas

2. Fill it in with a PDF form filler, and return it to the
   ASF Secretary as described at:
   https://www.apache.org/licenses/contributor-agreements.html#submitting

3. In the form, name the Apache <project> project and choose a
   unique Apache ID. Check that your preferred ID is not
   already taken:
   https://people.apache.org/committer-index.html
   Naming the project lets the Secretary notify the PMC when
   your ICLA has been recorded.

Do not copy the project or anyone else on your message to the
Secretary: the form contains personal information that should
be kept private.

If you have already filed an ICLA, let us know the email
address and public name you used on it and your preferred
Apache ID instead, and we will request your account.

When your ICLA has been recorded, you will receive a follow-up
message with the next steps.
───────────────────────────────────────────────────────────────
[END ICLA BLOCK]

[INCLUDE THE FOLLOWING BLOCK ONLY IF ICLA SUBMITTED BUT NOT YET PROCESSED:]
───────────────────────────────────────────────────────────────
Thank you for submitting your ICLA — the secretary will process
it shortly. Once it has been processed and your Apache account
is created, we will grant you access to the project's
repositories and mailing lists.

If your ICLA named the Apache <project> project, the Secretary
will notify the PMC when it has been recorded, and you will
receive a follow-up message with the next steps.
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

Please let us know in reply to this message whether you accept
or decline, and do not share that you were invited before the
PMC announces it.  Feel free to ask any questions too.
We're excited to have you on board!

On behalf of the <project> PPMC,  [use PMC for TLPs]
<nominator name> (<nominator apache-id>@apache.org)
```

---

## Secretary account-creation request

**To:** `root@apache.org`
**Cc:** `secretary@apache.org`
**Subject:** [ACCOUNT REQUEST] <project> — <candidate name>

> **Send only after ICLA is confirmed filed and processed.**
> If unsure, ask the nominator to confirm with secretary@apache.org first.

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

> Post this publicly only *after* the account exists and karma has been granted.

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
