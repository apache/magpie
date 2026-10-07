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
2. Filter for standard text and announcement channels (`type: "GuildText"`, `type: "GuildAnnouncement"`).
3. Verify channel visibility for the `@everyone` role:
   - Check the guild-level `@everyone` base role permission for `VIEW_CHANNEL`.
   - When `@everyone` has `VIEW_CHANNEL` enabled in the guild base role, a channel is public unless either the channel or its parent category carries an explicit deny overwrite for `@everyone`.
   - When `@everyone` lacks `VIEW_CHANNEL` in the guild base role, a channel is only public if the channel (or its parent category) carries an explicit allow overwrite granting `VIEW_CHANNEL` to `@everyone`.
   - Drop every channel where effective permissions do not grant `VIEW_CHANNEL` to `@everyone`.
4. Filter by the channel names or IDs declared in `chat.channels` when configured, or include all public channels when `chat.channels` is empty.
5. Return `[{id, name, is_private: false}]` per channel; never return private channels or direct messages.

## `resolve_user(github_handle)`

1. Call `mcp__discord__discord_search_members` with `github_handle`, then with the contributor's verified real name when one is known.
2. Return the best candidate member with `confirmed_by: null`, or `null` when there is none.
   (Note: Discord bot tokens cannot read other users' OAuth connected accounts or user profile bios without user authorization, so bot-based resolution returns matching candidates with `confirmed_by: null`. The consuming skill still requires the GitHub side, the organization's directory, or the maintainer to confirm the account per [`community-signals.md` § Identity](../../plugins/magpie-contributor-growth/skills/nomination/community-signals.md#identity)).

## `search_messages(chat_user_id, since, until, channels)`

1. Determine target channels: if `channels` is provided and non-empty, restrict search to those channel IDs; otherwise use every public channel returned by `list_channels()`.
2. Call `mcp__discord__discord_search_messages` with `author_id: chat_user_id` restricted to those target channels and within the window `[since, until]`.
3. Page through the search results.
4. Map each hit to:
   ```json
   {
     "url": "https://discord.com/channels/<guild_id>/<channel_id>/<message_id>",
     "channel": "<channel_id_or_name>",
     "ts": "<iso_timestamp>",
     "text": "<message_content>",
     "is_reply": true,
     "answers_question": true
   }
   ```
   where:
   - `<guild_id>` resolves to `chat.guild_id` from `<project-config>/project.md` when declared, or to `channel.guild_id` from the channel metadata returned by `list_channels()` (or the sole guild from `mcp__discord__discord_list_guilds`).
   - `is_reply` is true when the message references another message (`message_reference` / in-reply-to).
   - `answers_question` is true when the message is a reply to a question asked by someone else.
5. Drop any hit outside the resolved public channels.

## Tools this adapter never calls

`discord_send_message`, `discord_create_message`, `discord_edit_message`, `discord_delete_message`, `discord_add_reaction`, and any tool that reads direct messages (`discord_get_dm_channel`, `discord_get_private_channel`).
