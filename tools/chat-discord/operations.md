<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [tools/chat-discord/ — operations](#toolschat-discord--operations)
  - [Guild resolution](#guild-resolution)
  - [`list_channels()`](#list_channels)
  - [`resolve_user(github_handle)`](#resolve_usergithub_handle)
  - [`search_messages(chat_user_id, since, until, channels)`](#search_messageschat_user_id-since-until-channels)
  - [Permitted tools and read-only enforcement](#permitted-tools-and-read-only-enforcement)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# tools/chat-discord/ — operations

How each [`tools/chat/`](../chat/README.md) verb maps onto the Discord MCP.

## Guild resolution

Before invoking any Discord tool, resolve `<guild_id>`:
1. `chat.guild_id` from `<project-config>/project.md` when declared.
2. Else, call `mcp__discord__discord_list_guilds`: if exactly one guild is returned, use that sole guild ID.
3. Else (multiple guilds returned or none), stop and ask the user or maintainer to declare `chat.guild_id`.

Use this resolved `<guild_id>` for all MCP calls that take `guild_id` (`discord_list_channels`, `discord_search_members`, `discord_search_guild_messages`, `discord_audit_permissions`) and for constructing message URLs (`https://discord.com/channels/<guild_id>/<channel_id>/<message_id>`).

## `list_channels()`

1. Call `mcp__discord__discord_list_channels(guild_id: <guild_id>)` for the resolved server (guild).
2. Filter for standard text and announcement channels (`type: "GuildText"`, `type: "GuildAnnouncement"`).
3. Verify channel visibility for the `@everyone` role:
   - Check the guild-level `@everyone` base role permission for `VIEW_CHANNEL`.
   - When `@everyone` has `VIEW_CHANNEL` enabled in the guild base role, a channel is public unless either the channel or its parent category carries an explicit deny overwrite for `@everyone`.
   - When `@everyone` lacks `VIEW_CHANNEL` in the guild base role, a channel is only public if the channel (or its parent category) carries an explicit allow overwrite granting `VIEW_CHANNEL` to `@everyone`.
   - Drop every channel where effective permissions do not grant `VIEW_CHANNEL` to `@everyone`.
4. Filter by the channel names or IDs declared in `chat.channels` when configured, or include all public channels when `chat.channels` is empty.
5. Return `[{id, name, is_private: false}]` per channel; never return private channels or direct messages.

## `resolve_user(github_handle)`

1. Call `mcp__discord__discord_search_members(guild_id: <guild_id>, query: ...)` with `github_handle`, then with the contributor's verified real name when one is known.
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
   - `<guild_id>` is the guild ID resolved at the top of operations.
   - `is_reply` is true when the message references another message (`message_reference` / in-reply-to).
   - `answers_question` is true when the message is a reply to a question asked by someone else.
5. Drop any hit outside the resolved public channels.

## Permitted tools and read-only enforcement

The adapter calls **only** the read tools explicitly named in this document:
`discord_list_guilds`, `discord_list_channels`, `discord_search_members`, `discord_search_guild_messages`, `discord_read_messages`, `discord_audit_permissions`, `discord_get_channel_permissions`.

Direct message tools are dropped at registration via `-e DISCORD_MCP_TOOLSETS=discovery,messages,members,permissions`. Write tools in the messages toolset (`discord_reply_message`, `discord_send_embed`, `discord_forward_message`, `discord_crosspost_message`, etc.) are never invoked by this adapter, and enforcement is guaranteed by the bot application's Discord permissions (authorized with `View Channels` and `Read Message History` only).
