<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [tools/chat-slack/ — operations](#toolschat-slack--operations)
  - [`list_channels()`](#list_channels)
  - [`resolve_user(github_handle)`](#resolve_usergithub_handle)
  - [`search_messages(chat_user_id, since, until, channels)`](#search_messageschat_user_id-since-until-channels)
  - [Tools this adapter never calls](#tools-this-adapter-never-calls)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# tools/chat-slack/ — operations

How each [`tools/chat/`](../chat/README.md) verb maps onto the Slack MCP.

## `list_channels()`

`mcp__claude_ai_Slack__slack_search_channels` with `channel_types: "public_channel"`, one call per configured channel name as `keywords`, or with a broad keyword and pagination when no channels are configured.
Return `{id, name, is_private: false}` per channel; never request `private_channel`.

## `resolve_user(github_handle)`

1. `mcp__claude_ai_Slack__slack_search_users` with the handle, then with the contributor's verified real name when one is known.
2. For each candidate, `mcp__claude_ai_Slack__slack_read_user_profile`.
   Return `confirmed_by: "profile"` only when a profile field — title, a custom field, or a linked account — names the GitHub handle or its `github.com/<handle>` URL.
   That is the Slack account's own claim; the consuming skill still requires the GitHub side, the directory, or the maintainer to confirm it (see [`community-signals.md` § Identity](../../plugins/magpie-contributor-growth/skills/nomination/community-signals.md#identity)).
3. Otherwise return the best candidate with `confirmed_by: null`, or `null` when there is none.

## `search_messages(chat_user_id, since, until, channels)`

`mcp__claude_ai_Slack__slack_search_public` with the query `from:<@chat_user_id> after:<the day before since> before:<the day after until>` (Slack's `after:` and `before:` exclude the day they name), adding `in:<#channel>` per configured channel.
Page through the results; map each hit to `{url, channel, ts, text, is_reply, answers_question}`, where `answers_question` is true when the message is a thread reply to a message that asks a question and was written by someone else.

## Tools this adapter never calls

`slack_send_message`, `slack_send_message_draft`, `slack_schedule_message`, `slack_create_canvas`, `slack_update_canvas`, and any search that includes private channels (`slack_search_public_and_private`).
