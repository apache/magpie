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
   **Capability:** capability:NAME
   ```

   (multi-value: `capability:NAME + capability:NAME`), with NAME drawn
   from the taxonomy in `docs/labels-and-capabilities.md`. Substrate
   bridges default to `capability:setup`.

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

Both are **HARD** checks in
[`tools/skill-and-tool-validator`](skill-and-tool-validator/) — a tool
README missing either the `**Capability:**` line or the
`## Prerequisites` section fails `skill-and-tool-validate` (and the
`prek` / pre-commit hook that runs it).

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
