<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [AGENTS — conventions for `tools/`](#agents--conventions-for-tools)
  - [Every tool is a directory with a README](#every-tool-is-a-directory-with-a-readme)
  - [Refresh the cross-references when tools change](#refresh-the-cross-references-when-tools-change)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# AGENTS — conventions for `tools/`

Operational context for everything under `tools/`. It is loaded in
addition to the repository-wide [`/AGENTS.md`](../AGENTS.md), which still
governs everything (commit trailers, placeholder convention,
privacy/security posture). Where the two overlap, the repo-wide
`AGENTS.md` wins.

A **tool** is the only layer that is allowed to know a specific vendor
exists — the generic skills target capabilities, and each tool fulfils a
capability for one concrete backend. See
[`docs/vendor-neutrality.md`](../docs/vendor-neutrality.md) for how the
skills / tools / capabilities split delivers vendor neutrality, and
[`docs/labels-and-capabilities.md`](../docs/labels-and-capabilities.md)
for the capability taxonomy.

## Every tool is a directory with a README

Each tool lives at `tools/<name>/` and **must** have a `README.md` that
declares, up front:

1. **Its capability** — a line of the exact form

   ```markdown
   **Capability:** contract:NAME
   ```

   …or `substrate:NAME` (multi-value: `contract:a + substrate:b`). A
   **tool capability** is the interface the tool provides (RFC-AI-0005):
   `contract:<name>` when it implements a capability contract under
   `tools/<contract>/` (e.g. `contract:tracker`), or `substrate:<name>`
   for framework substrate (e.g. `substrate:sandbox`). Draw the value
   from the taxonomy in `docs/labels-and-capabilities.md`.

2. **Its prerequisites** — a `## Prerequisites` section stating what the
   tool needs *before it can run*, so an adopter never discovers a
   missing dependency at first invocation. Cover the bullets that apply:

   - **Runtime** — e.g. `Python 3.11+ run via uv`, `Bash + coreutils`,
     `Python stdlib only`, `Node.js 20+`. State it even when trivial.
   - **CLIs** — external commands the tool shells out to (`gh`, `git`,
     `svn`, `jq`, `groovy`, `docker`/`podman`, `bubblewrap`, `socat`, …),
     or `None beyond the runtime`.
   - **Credentials / auth** — `gh auth status`, an OAuth token at a
     home-dir path, an API-token env var, …, or `None`.
   - **Network** — the hosts it reaches (`api.github.com`,
     `*.apache.org`, a JIRA host, …), or state that it runs fully
     offline / on local files.
   - **Optional** — real optional dependencies or features only.

   Keep it factual and tight (≈3–6 bullets); never invent a dependency.
   A pure interface-spec tool (an adapter *contract* with no executable
   code) says so and defers concrete prerequisites to its adapters.

3. **(Optional) its organization** — when a tool *belongs to* a specific
   organization (it is the backend/adapter for that org's stack, e.g.
   the ASF Vulnogram / PonyMail / apache-projects tools), add a line of
   the exact form

   ```markdown
   **Organization:** ASF
   ```

   The value must name an organization under
   [`organizations/`](../organizations/) (e.g. `ASF`). Omit the line for
   organization-agnostic tools — absence means "belongs to no specific
   organization". Skills declare the same membership with an
   `organization:` frontmatter key; skill families with an
   `organization:` scope banner in `docs/<family>/README.md`.

4. **(Optional) its MCP backing** — when a tool wraps a
   [Model Context Protocol](https://modelcontextprotocol.io) server as a
   concrete backend, declare it with a line of the exact form

   ```markdown
   **MCP:** <server> (mcp__<prefix>__*)
   ```

   e.g. `**MCP:** PonyMail — apache/comdev (mcp__ponymail__*)`. The value
   names the human-readable server (optionally with `— <org>`) and, in
   parentheses, the `mcp__<prefix>__*` tool namespace it exposes. Omit the
   line for tools with no MCP backend — absence means "wraps no MCP". This
   marker is the per-tool source of truth for the "wraps an MCP"
   classification: it is mirrored in the
   [`docs/labels-and-capabilities.md`](../docs/labels-and-capabilities.md#mcp-servers-classified-by-capability)
   MCP table and read by the project website's tool index to drive its
   "Wraps an MCP" filter. An MCP is transport, not a capability axis — the
   `**Capability:**` line still states the contract the tool provides.

The capability and prerequisites are **HARD** checks in
[`tools/skill-and-tool-validator`](skill-and-tool-validator/) — a tool
README missing either the `**Capability:**` line or the
`## Prerequisites` section fails `skill-and-tool-validate` (and the
`prek` / pre-commit hook that runs it). The optional `**Organization:**`
line, when present, must name a known organization or the validator
fails the run.

## Refresh the cross-references when tools change

The tool inventory is referenced from a few hand-maintained places.
When you **add, rename, remove, or re-scope** a tool — or change which
backends it supports or the tracking issues behind its extension
points — review and refresh:

- [`docs/labels-and-capabilities.md`](../docs/labels-and-capabilities.md)
  — the *Capability to tool map* row. The validator's `capability-sync`
  check enforces that every tool with a `**Capability:**` declaration has
  a matching row, so this one fails the build if you forget it.
- [`docs/vendor-neutrality.md`](../docs/vendor-neutrality.md) — the
  per-axis extension-point citations (the axis prose, the
  *contract tool* table, and the *Status at a glance* table). This list
  is **not** machine-checked; it is the public explanation of which
  backends work today and which are open extension points, so it has to
  be refreshed by hand whenever a tool or its tracking issue changes.

When in doubt about whether a doc references the tool you touched, grep
`docs/` for the tool name before opening the PR.
