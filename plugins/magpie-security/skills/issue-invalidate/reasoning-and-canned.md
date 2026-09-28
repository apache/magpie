<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-invalidate — invalidity reasoning and canned response

## Step 3 — Mine invalidity reasoning from the discussion

The team's reasoning is the load-bearing input for the email
draft. Extract verbatim quotes the user can confirm before any
draft is written.

Scan `tracker.comments[]` for posts that argue **why** the report
is not a security issue. Strong signals:

- Citations of the project's security model (`<security-model-url>`)
  (full URL, anchor links, paraphrases).
- Phrases like *"this is by design"*, *"out of scope"*,
  *"documented behavior"*, *"requires X privileges already"*,
  *"not a CVE"*, *"won't fix"*, *"working as
  intended"*.
- Pointers to existing CVEs that already addressed the broader
  class (e.g. *"already covered by CVE-YYYY-NNNNN"*).
- Pointers to a documented mitigation the reporter missed
  (config flag, RBAC role, security-policy section).
- Counter-examples or PoC failures from team members trying to
  reproduce.

Surface the **3–5 most-load-bearing quotes** verbatim, each with
the comment author's handle and a clickable comment URL. Do not
paraphrase — the user should be able to copy a quote into the
email draft if it fits.

If no clear reasoning is present in the comments (e.g. the team
discussed in chat and only landed a one-line *"closing as invalid"*
on the tracker), surface this gap to the user with:

> The tracker has no detailed reasoning in its public comments.
> The email draft will need a reason to communicate to the
> reporter. Options: (a) supply a one-paragraph reason inline
> (`--reason "<text>"`), (b) point me to a chat transcript /
> private GHSA comment to extract from, or (c) close silently
> with no reply (only appropriate when the tracker is
> `security@`-imported but the reporter is unreachable — flag
> this in the rollup so the gap is visible).

---

## Step 4 — Match a canned-response template

The email draft is a canned-response spine plus augmentation, as in
[`security-issue-import` Step 5](../issue-import/SKILL.md).
Read [`<project-config>/canned-responses.md`](../../../../<project-config>/canned-responses.md)
and pick the section that best matches the invalidity reasoning mined in Step 3.
Section names always come from the adopting project's own `canned-responses.md` headings.
The table below is an **illustrative example** of one adopting project's headings, showing the kind of reasoning-shape to section mapping to perform; substitute the matching headings from `<project-config>/canned-responses.md`:

| Reasoning shape | Canned section (example headings) |
|---|---|
| Generic *"after review, not CVE-worthy"* with case-specific reasoning | *Negative Assessment response* (the `HERE DETAILED EXPLANATION FOLLOWS` placeholder is filled with the augmentation). |
| Dag-author-provided input is the attack vector | *When someone claims Dag author-provided "user input" is dangerous*. |
| DoS / RCE / arbitrary read via Connection configuration | *DoS/RCE/Arbitrary read via Provider's Connection configuration*. |
| Self-XSS by an authenticated user | *Immediate response for self-XSS issues triggered by Authenticated users*. |
| DoS triggered by an authenticated user (no privilege escalation) | *DoS issues triggered by Authenticated users*. |
| Parameter injection to operator/hook called by the dag author | *Parameter injection to operator or hook*. |
| Automated-scanner output without human-verified PoC | *Automated scanning results*. |
| Image / video reproducer instead of a written report | *When someone submits a media report* (or *Or an alternative response*). |

If multiple canned sections apply, pick the most specific one and note the others to the user;
if none fits, default to the project's generic negative-assessment section (*Negative Assessment response* in the example),
with the team's reasoning filling the placeholder.

Never invent a canned response or paraphrase one into the file.
If the project lacks a fitting template, surface the gap to the user: adding one is a separate `canned-responses.md` PR, not part of this run.

---
