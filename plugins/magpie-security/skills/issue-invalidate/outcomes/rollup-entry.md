<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-invalidate — Step 5e rollup entry

Read from [`SKILL.md` Step 5e](../SKILL.md#5e--status-rollup-entry); `<sm> render-rollup` renders it.

Append a new entry to the existing rollup comment
(per
[`tools/github/status-rollup.md`](../../../../../tools/github/status-rollup.md)
upsert recipe) with the action label `Closed as invalid`.
Draft only the entry body; Step 6a's tool writes the `<details>` envelope. Shape:

```markdown
**Closed as `invalid` on <YYYY-MM-DD>** (decided in [comment](#issuecomment-<id>)).

**Reasoning** (verbatim from the team's discussion, capped at ~5 quotes):

- @<author>: > <quote 1> ([source](#issuecomment-<id>))
- @<author>: > <quote 2> ([source](#issuecomment-<id>))
- ...

**Canned response selected:** *<canned section name>* in [`canned-responses.md`](https://github.com/<tracker>/blob/<tracker-default-branch>/<project-config>/canned-responses.md#<anchor>).

**Reporter notification:** <one of — required line, never omit:>
- **`security@`-imported, direct-reporter mode:** Gmail draft `<draftId>` created on thread `<threadId>` anchored at message `<messageId>` — awaiting user review.
- **`security@`-imported, via-forwarder mode:** Forwarder-relay draft `<draftId>` to `<forwarder-contact>` on thread `<threadId>` per the matching adapter's `reporter_addressing_block` convention (clickable URL + paste-ready reporter-voice block) — awaiting user review.
- **`security@`-imported, `duplicate` disposition:** *(same as direct or via-forwarder above; the draft body MUST name the canonical CVE-ID per Step 5d).*
- **No notification owed — internal audit finding:** Tracker imported from project-internal markdown audit (`<source-markdown>`), no inbound `security@` thread, no reporter to notify.
- **No Gmail draft owed — GHSA-relay-only, operator has GHSA-write access:** GHSA-relay-only reporter channel (`GHSA-XXXX-XXXX-XXXX`); closure communicated as GHSA comment `<URL>` / advisory state set to `<withdrawn|informational>`. No Gmail reply needed.
- **Forwarder-relay draft owed — GHSA-relay-only, operator lacks GHSA-write access:** GHSA-relay-only channel (`GHSA-XXXX-XXXX-XXXX`); operator's account does not have GHSA-write on `<upstream>`. Forwarder-relay draft `<draftId>` queued to `<forwarder-contact>` requesting they post the closure comment on the GHSA on our behalf — awaiting user review.
- **PR-imported:** none (no reporter; per [Reporter credit policy](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-import-from-pr/SKILL.md#reporter-credit-policy-for-public-pr-imports)).
- **Indeterminate import path:** none (flag from Step 2 surfaced; user explicitly chose silent close).

**The Reporter-notification line is required on every invalidate
rollup entry.** Exactly one of the cases above must apply. If
none does (the channel is genuinely ambiguous), surface as a
blocker to the user before closing — do NOT post the rollup
entry without the line.

**Project board:** archived (item `<item-id>`).

**Next:** none — terminal disposition.
```

Start every body line at column 0 — leading spaces inside the `<details>` envelope render as a code block.
Trim the reasoning quotes to ~5 even when the discussion has more: the rollup is a navigation aid, not an archive.
