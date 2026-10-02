<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [tools/chat-discord/ — operations](#toolschat-discord--operations)
  - [`list_channels()`](#list_channels)
  - [`resolve_user(github_handle)`](#resolve_usergithub_handle)
  - [`search_messages(chat_user_id, since, until, channels)`](#search_messageschat_user_id-since-until-channels)
  - [Tools this adapter never calls](#tools-this-adapter-never-calls)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# tools/chat-discord/ — operations

How each [`tools/chat/`](../chat/README.md) verb maps onto the Discord MCP.

## `list_channels()`

1. Call `mcp__discord__discord_list_channels` for the configured server (guild).
2. Filter for standard text and announcement channels (guild text, announcements, or public forum threads).
3. Drop every channel with `is_private: true`, channels residing under private categories, or channels where `@everyone` permissions deny view access.
4. Filter by the channel names declared in `chat.channels` when configured, or include all public channels when `chat.channels` is empty.
5. Return `[{id, name, is_private: false}]` per channel; never request or return private channels.

## `resolve_user(github_handle)`

1. Call `mcp__discord__discord_search_members` with `github_handle`, then with the contributor's verified real name when one is known.
2. For each candidate member, call `mcp__discord__discord_get_user_profile`:
   Return `confirmed_by: "profile"` only when:
   - A connected account names the GitHub handle (e.g. `connected_accounts: { github: "<github_handle>" }`), or
   - The user's profile bio ("About Me") explicitly names the GitHub handle or its `github.com/<handle>` URL.
   That is the Discord account's own claim; the consuming skill still requires the GitHub side, the directory, or the maintainer to confirm it (see [`community-signals.md` § Identity](../../plugins/magpie-contributor-growth/skills/nomination/community-signals.md#identity)).
3. Otherwise return the best candidate with `confirmed_by: null`, or `null` when there is none.

## `search_messages(chat_user_id, since, until, channels)`

1. Call `mcp__discord__discord_search_messages` with `author_id: chat_user_id` across the public channels returned by `list_channels()`.
2. Restrict to messages sent within the window `[since, until]`.
3. Page through the search results.
4. Map each hit to:
   ```json
   {
     "url": "https://discord.com/channels/<guild_id>/<channel_id>/<message_id>",
     "channel": "<channel_name_or_id>",
     "ts": "<iso_timestamp>",
     "text": "<message_content>",
     "is_reply": true,
     "answers_question": true
   }
   ```
   where:
   - `is_reply` is true when the message references another message (`message_reference` / in-reply-to).
   - `answers_question` is true when the message is a reply to a message asking a question written by someone else.
5. Drop any hit outside the public channels.

## Tools this adapter never calls

`discord_send_message`, `discord_create_message`, `discord_edit_message`, `discord_delete_message`, `discord_add_reaction`, and any tool that reads direct messages (`discord_get_dm_channel`, `discord_get_private_channel`).
