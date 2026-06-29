<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/ponymail/`](#toolsponymail)
  - [Prerequisites](#prerequisites)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/ponymail/`

**Capability:** capability:setup + capability:intake

PonyMail archive substrate. Read-only ASF mailing-list archive client; complements `gmail` for threads not present in the inbox. Used by security-issue-import + sync to cross-reference public mailing-list discussions. See [`tool.md`](tool.md) for the operation catalogue and [`operations.md`](operations.md) for usage.

## Prerequisites

- **Runtime:** Node.js 20+ — the backing MCP server is the `apache/comdev` `mcp/ponymail-mcp/` package, reached from Claude Code via the `mcp__ponymail__*` tools. This directory is documentation for that substrate.
- **CLIs:** `git` + `npm` / `node` to clone and run the comdev MCP server; `claude mcp add` to register it with Claude Code.
- **Credentials / auth:** ASF LDAP OAuth via `mcp__ponymail__login` (session cached at `~/.ponymail-mcp/session.json`) for private lists; anonymous read for public lists.
- **Network:** `lists.apache.org` (PonyMail HTTP API), `oauth.apache.org` (LDAP login redirect), and `github.com` (cloning `apache/comdev`).
