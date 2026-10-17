<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import — the privacy-LLM gate and redact-before-extract

Read from [Step 0](../SKILL.md#step-0--pre-flight-check) item 4 and [Step 4](../SKILL.md#step-4--extract-template-fields).
Identifying third-party PII is the model's judgement; redacting it is the `pii-redact` tool's job.
The [`security-management`](../../../../../tools/security-management/README.md) tool only ever sees the redacted text and passes `N-…` / `E-…` tokens through unchanged.

## Step 0 item 4 — the gate and what it loads

4. **Privacy-LLM contract.** This skill reads `<security-list>`
   bodies that may contain third-party PII the reporter
   discloses about other people. Run the gate-check first —
   non-zero exit is a hard stop:

   ```bash
   uv run --project <framework>/tools/privacy-llm/checker \
     privacy-llm-check
   ```

   The checker auto-locates `<project-config>/privacy-llm.md`
   (template at
   [`projects/_template/privacy-llm.md`](../../../../magpie-setup/templates/privacy-llm.md))
   and verifies every entry in *Currently configured LLM stack*
   is approved per
   [`tools/privacy-llm/models.md`](../../../../../tools/privacy-llm/models.md#the-pre-flight-check).
   In addition, verify:
   - `~/.config/apache-magpie/` is writable (the redactor's
     mapping file lives there);
   - the configured collaborator source is reachable via
     `gh api` (default: `<tracker>` from `project.md`) — fetch the
     collaborator list here, once per run, with
     `gh api repos/<tracker>/collaborators --jq '.[].login'` and keep
     it in the observed-state bag; Step 2-bis (team-member senders)
     and Step 4 (collaborator exemption) reuse it;
   - the redaction-tuning knobs (collaborator exemption,
     enabled field types) are loaded into the skill's
     observed-state bag — they apply at filter-time below.

   Each subsequent body fetch in Steps 4 / 7 / 8 (template-
   field extraction, draft assembly, recap) follows the
   redact-after-fetch protocol in
   [`tools/privacy-llm/wiring.md`](../../../../../tools/privacy-llm/wiring.md#redact-after-fetch-protocol);
   the receipt-of-confirmation draft assembly follows the
   [reveal-before-send protocol](../../../../../tools/privacy-llm/wiring.md#reveal-before-send-protocol)
   when (and only when) the draft references a third-party
   identifier.

## Step 4 — redact, then extract

**Apply the redact-after-fetch protocol BEFORE extracting fields.**
Every body fetched in Steps 2 / 2a / 2b / 3 (via `mcp__claude_ai_Gmail__get_thread`
with `messageFormat: FULL_CONTENT`) goes through the redactor per
[`tools/privacy-llm/wiring.md`](../../../../../tools/privacy-llm/wiring.md#redact-after-fetch-protocol)
before its content is used for field extraction. Concretely:

1. Reuse the collaborator set fetched once in Step 0 via
   `gh api repos/<tracker>/collaborators --jq '.[].login'`
   (the configured collaborator source from
   `<project-config>/privacy-llm.md` — default `<tracker>`).
2. For each candidate body, identify third-party PII candidates
   (names / emails / handles / etc. that appear in the body or
   signature, OTHER than the reporter from the `From:` header).
3. Filter out the reporter and any collaborator (apply the
   *Collaborator exemption* knob from `<project-config>/privacy-llm.md`
   — default `enabled`, so collaborators flow through; set
   `disabled` redacts them too).
4. Pass the remaining set as `--field <type>:<value>` arguments
   to `pii-redact`, capture the redacted body for use in this
   step's field extraction below. The reporter's own values
   (name, email, etc.) are NEVER redacted — they flow through
   in the clear.

The "issue description" template field below is sourced from the
**redacted body**, not the raw body. Skill docs and proposals
reviewed by the user in Step 5 / 6 will show third-party
identifiers (`N-…`, `E-…`) where the reporter named someone
else; the user can run `pii-list` to see the mapping if needed.
