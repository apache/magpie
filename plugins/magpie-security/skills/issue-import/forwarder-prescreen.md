<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 3 — the forwarder pre-screen

Read from [Step 3](SKILL.md#step-3--classify-each-candidate) when `forwarders.enabled` is non-empty; then classify with Step 3's table.

When `forwarders.enabled` is non-empty in [`<project-config>/project.md`](../../../../<project-config>/project.md),
the optional [`security-issue-import-via-forwarder`](../issue-import-via-forwarder/SKILL.md) sub-skill runs FIRST
and may pre-classify the message through a registered forwarder adapter ([contract](../../../../tools/forwarder-relay/README.md)):
use its classification when it returns one, else the table below.
Invoke it only when `<sm> relay-prescreen --message <scratch>/root-<threadId>.json --forwarders <scratch>/forwarders.json` prints `invoke_subskill: true`.
The message file holds the root's raw `from` header and `body`, and its `cc` and RFC-5322 `message_id` when an enabled adapter sets a list-rewrite path (the Gmail MCP does not expose `Message-ID:`; [get it](../../../../tools/gmail/operations.md#get-the-root-message-id-of-a-thread) through the OAuth Gmail helper or the archive, and leave it out when neither is reachable, so a list-rewritten relay shows as one signal only); the forwarders file holds `project.md → forwarders`, each enabled adapter with every pattern key it sets (`sender_pattern`, `preamble_match`, and the three `list_*_pattern` keys of its list-rewrite path; leaving those out drops list-rewritten relays to one signal only)
(else its [defaults](../../../../tools/forwarder-relay/README.md#asf-default--asf-security-forwarder)), never copied into this skill.
The pre-screen needs both `detect()` signals of one adapter (sender against `From:` AND preamble against the first 400 characters), since either alone is forgeable by any sender;
the sub-skill's Step 1 stays authoritative. An adapter listed under `partial` matched only one signal: classify the candidate as a direct report and show *"relay-shaped, one signal only"* in its Step 5 entry.
