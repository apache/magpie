<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — PonyMail pre-flight gate

3. **PonyMail MCP status.** Whether this is a hard gate depends on
   the manifest: if `<project-config>/project.md → Mail sources`
   declares `ponymail` with `mandatory: yes` (the **ASF default**),
   PonyMail is a pre-flight prerequisite and the outcomes below
   that "degrade quietly" become **hard stops** instead. Call
   `mcp__ponymail__auth_status()` once. Three outcomes:
   - **Authenticated session** — record
     `ponymail_enabled: true, ponymail_authenticated: true` in the
     skill's observed-state bag. **Downstream steps use PonyMail
     MCP as the primary read path** for the mailing-list queries
     documented in 1c / 1d / 1e / 2b / 2c; Gmail becomes the
     fallback. This is the normal configuration for <governance-body>-authenticated
     triagers.
   - **No session / expired session** —
     - *`mandatory: yes` (ASF default):* **stop**. Surface
       *"mandatory mail-source backend `ponymail` is registered but
       not authenticated — run `mcp__ponymail__login()` and
       re-invoke"*. Private-list reads need the LDAP session, and
       ASF triagers are <governance-body>-authenticated, so an unauthenticated
       session is a hard stop, not a Gmail-only fallback.
     - *`mandatory: no`:* record
       `ponymail_enabled: true, ponymail_authenticated: false`,
       warn (*"PonyMail MCP is configured but not authenticated —
       run `mcp__ponymail__login()` if you want this session to use
       it; otherwise Gmail will serve all reads"*), and proceed
       with Gmail as the primary read path.
   - **MCP tools not available** (the `mcp__ponymail__*` tools
     are absent from the current session's tool list) —
     - *`mandatory: yes` (ASF default):* **stop**. Surface
       *"mandatory mail-source backend `ponymail` unavailable: MCP
       not registered; run aborted — register it per
       `tools/ponymail/tool.md` (install from the latest `main` of
       `apache/comdev`) and re-invoke"*.
     - *`mandatory: no`:* record `ponymail_enabled: false` and
       silently proceed Gmail-only.
   When the manifest declares `ponymail` with `mandatory: no` and
   `.apache-magpie-overrides/user.md` sets `tools.ponymail.enabled:
   false` (or omits the block), skip this sub-step; Gmail is the
   only read backend. See
   [`tools/ponymail/tool.md`](../../../../tools/ponymail/tool.md)
   for the one-time setup instructions.
