<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-via-forwarder — the routing components

From Step 3, as the skill carried it; `security-management issue-import-via-forwarder route` and `first-name` decide the parts that are rules.

When `mode = import` (the parent is [`security-issue-import`](../../issue-import/SKILL.md) at its Step 7 — *Apply confirmed imports*), `mode = invalidate` (the parent is [`security-issue-invalidate`](../../issue-invalidate/SKILL.md) at its Step 5d — *ASF-relay branch*), or `mode = sync` (the parent is [`security-issue-sync`](../../issue-sync/SKILL.md) at its Step 2b — *Draft routing for reporter-facing milestones*), the skill produces:

1. **`to_recipients`** — the matched adapter's `contact_handle`, read from the adopter's [`<project-config>/project.md → forwarders.<adapter>.contact_handle`](../../../../../<project-config>/project.md#forwarders).
   For the ASF-default `asf-security` adapter this is the configured security-team liaison handle (with a rota fallback when configured); for a third-party platform adapter it is that platform's program contact or assigned triager.
   The adapter MAY return a list of fallbacks — pick the first available one and surface the chosen handle in the recap.

2. **`addressing_block`** — the paste-ready block rendered by the adapter's `reporter_addressing_block()` per [`tools/forwarder-relay/README.md` § `reporter_addressing_block()`](../../../../../tools/forwarder-relay/README.md#reporter_addressing_block---string).
   Parameters passed in:

   - `forwarder_first_name` — the first-name part of the adapter's `contact_handle` (e.g. for a handle like `@some-liaison`, *"Some"*, from the GitHub profile).
     When the handle is a list, use the first available contact's first name.
   - `reporter_first_name` — the first-name part of the credit extracted at Step 2.
     Empty when Step 2 returned `null`; the adapter's wrapper then falls back to a generic salutation.
   - `links` — the `(label, url)` pairs the parent passed in (GHSA URL, CVE record URL, advisory URL, fix-PR URL, …).
     The adapter's wrapper decides where they render — typically a *"Context links"* block near the top.
   - `inner_body` — the project-voice text the parent drafted.
     The adapter wraps it in the paste-ready fence; it does not modify the content.

3. **`question_mode`** — read from the adapter's `via_forwarder_question_mode` attribute.
   When `true`, the credit-preference question (if any) folds into the same draft as the milestone notice (one paste action for the forwarder); when `false`, the parent emits a separate back-channel draft for the question.
   The skill returns the boolean; the parent assembles the draft.

The skill **does not create the draft itself** — the parent owns the `create_draft` call against the mail-source backend per [`tools/gmail/draft-backends.md`](../../../../../tools/gmail/draft-backends.md).
It returns only the components (`to_recipients`, `addressing_block`, `question_mode`).

**Negative-space rule** — drafts produced via this routing must never include the items the forwarder-routing policy classifies as *do-not-relay*: regular workflow status, standalone credit-acceptance confirmation messages on subsequent sync passes, reviewer-comment relays.
The list lives in [`docs/security/forwarder-routing-policy.md` § Negative space — DO NOT relay](../../../../../docs/security/forwarder-routing-policy.md#negative-space--do-not-relay).
When `mode = sync` and the parent's milestone falls into the negative-space list, return empty `addressing_block` / `to_recipients`; the parent then skips the draft for that milestone.
