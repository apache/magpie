<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/gmail/`](#toolsgmail)
  - [Prerequisites](#prerequisites)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/gmail/`

**Capability:** contract:mail-source + contract:mail-draft

Gmail API substrate. Read + draft-only — never sends. Provides two
contracts: `mail-source` for inbound report intake (search / read a
uniform thread/message view) and `mail-draft` for outbound courtesy-reply
drafting. Used by the security-issue-import / sync / invalidate flows. See [`tool.md`](tool.md) for the operation catalogue and the per-area files for ASF relay routing, draft backends, threading, search queries.

## Prerequisites

- **Runtime:** claude.ai Gmail MCP (`mcp__claude_ai_Gmail__*`) for search / read / draft; the preferred `oauth_curl` draft backend is Python 3.11+ run via `uv` (`tools/gmail/oauth-draft`) plus `curl`.
- **CLIs:** None beyond the runtime on the MCP path; `uv` + `curl` for the `oauth_curl` backend.
- **Credentials / auth:** claude.ai Gmail MCP authenticated. For `oauth_curl`, a Google OAuth refresh-token file (default `~/.config/apache-magpie/gmail-oauth.json`, overridable via `$GMAIL_OAUTH_CREDENTIALS` or `tools.gmail.oauth_credentials_path`) created once by `oauth-draft-setup`. Read + draft only — never sends.
- **Network:** Gmail API (`gmail.googleapis.com`); `lists.apache.org` for the adjacent PonyMail archive lookups.
- **Optional:** `google-auth-oauthlib` (pulled by `uv` for the one-time `oauth-draft-setup` consent flow only).
