<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import — mail-source backends and the Step 0 probe

Read from the [Prerequisites](../SKILL.md#prerequisites) and from [Step 0](../SKILL.md#step-0--pre-flight-check) items 1 and 3.

## Which backends the skill needs

- **At least one mail-source backend** from [`<project-config>/project.md → Mail sources`](../../../../../<project-config>/project.md#mail-sources),
  used through the operations in [`tools/mail-source/contract.md`](../../../../../tools/mail-source/contract.md)
  (adapters: [`gmail`](../../../../../tools/gmail/tool.md), [`ponymail`](../../../../../tools/ponymail/tool.md), [`imap`](../../../../../tools/mail-source/imap/README.md), [`mbox`](../../../../../tools/mail-source/mbox/README.md)).
  Together they must cover `list_recent_threads` + `read_thread` to find reports, and `create_draft` to draft the Step 7 receipt;
  without `create_draft`, Step 7 says *"no draft backend available"* and the user writes the reply by hand.
  A `maildir` drafting backend ([`draft-backends.md`](../../../../../tools/gmail/draft-backends.md#how-the-skills-pick-a-backend)) covers `create_draft` with no Gmail account.

See
[Prerequisites for running the agent skills](../../../../../docs/quick-start/prerequisites.md#prerequisites-for-running-the-agent-skills)
in `docs/prerequisites.md` for the overall setup.

## Step 0 item 1 — probe every declared backend

1. **Mail-source backends from `<project-config>/project.md →
   Mail sources` are available.** For each declared backend, run
   the backend's trivial health probe (per its adapter doc —
   Gmail: `mcp__claude_ai_Gmail__search_threads` with `pageSize:
   1`; Ponymail: `mcp__ponymail__auth_status()`; IMAP: a
   `CAPABILITY` against the configured host; mbox: a `stat` on
   the archive path) and record the result in the skill's
   observed-state bag. Apply the
   [contract's resolution rule](../../../../../tools/mail-source/contract.md#resolution-rule--which-backend-runs-an-operation)
   to figure out which backend serves which op for this run.

   * **`mandatory: yes` backend unavailable** → **stop
     immediately**. Surface *"mandatory mail-source backend
     `<name>` unavailable: `<reason>`; run aborted"*. The user
     fixes the auth / connection and re-invokes.
   * **`mandatory: no` backend unavailable** → continue with the
     remaining backends. If the resolution then leaves an
     operation with no provider (e.g. no available backend
     supports `create_draft`), the skill records *"no `<op>`
     backend available"* in the observed-state bag and the
     relevant downstream step omits that proposal with a clear
     hand-back to the user.
   * **Every declared backend healthy** → proceed; the
     observed-state bag records one provider per op so every
     dispatch later is unambiguous.

## Step 0 item 3 — the reference adopter

3. **(Reference adopter.)** It sets both `gmail` and `ponymail` to `mandatory: yes` (the ASF default),
   so a Gmail failure, or PonyMail missing or not authenticated for the private `<security-list>` archive, stops the run per item 1.
   Gmail serves just-arrived mail and every draft; PonyMail serves archive lookups, and is the primary read path when authenticated.
   Read "Gmail" in later steps as "the backend the resolution rule picked for that operation".
