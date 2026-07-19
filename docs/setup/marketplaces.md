<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Installing Apache Magpie from agent marketplaces](#installing-apache-magpie-from-agent-marketplaces)
  - [Supported agents](#supported-agents)
    - [Not supported](#not-supported)
  - [Versioning](#versioning)
  - [Verification status](#verification-status)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Installing Apache Magpie from agent marketplaces

From 0.2.0, Apache Magpie ships manifests so its skills can be installed
through the plugin/extension mechanisms of the major AI coding agents,
**in addition to** the canonical `/magpie-setup` snapshot adoption (see
[`install-recipes.md`](install-recipes.md)).

> [!IMPORTANT]
> The marketplace path is a **discovery and trial** channel: it drops the
> 70 skills into your agent so you can use them immediately. It does **not**
> set up the full adoption machinery (the committed pin, the gitignored
> snapshot, drift detection, agentic overrides, or the secure-agent setup).
> For a project that adopts Magpie for real, use `/magpie-setup` — the
> marketplace install and full adoption are complementary, not exclusive.

> [!NOTE]
> The **canonical release** of Apache Magpie remains the signed source
> artefact on `dist.apache.org` per the
> [ASF release policy](https://www.apache.org/legal/release-policy.html).
> Marketplace entries are a convenience layer that reference the released
> `X.Y.Z` git tag; they are derived from — not a substitute for — the ASF
> source release.

All entries package the whole framework as a single **`magpie`** plugin
that exposes every skill under the `skills/` tree. Skills are then invoked
with the installing agent's namespacing (e.g. `/magpie:release-vote-tally`).

## Supported agents

| Agent | Install | Manifest in this repo |
|---|---|---|
| **Claude Code** | `/plugin marketplace add apache/magpie` then `/plugin install magpie@apache-magpie` | `.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json` |
| **OpenAI Codex CLI** | `codex plugin marketplace add apache/magpie` then install `magpie` | `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` |
| **GitHub Copilot** | add the repo as a plugin marketplace, then install `magpie` | `marketplace.json` (repo root) |
| **Google Gemini CLI** | `gemini extensions install https://github.com/apache/magpie` | `gemini-extension.json` |
| **Cursor** | add via the plugin/skill install flow pointing at the repo | consumes the plugin manifests above |
| **microsoft/apm** | `apm install apache/magpie` (compiles to Claude/Cursor/Codex/Copilot/Gemini) | `apm.yml` |
| **Kiro** | install from the GitHub subdirectory of a skill (Kiro installs per-skill from a subdir, not the repo root) | native `skills/<name>/SKILL.md` |
| **OpenCode** | drop the skills into `.opencode/skills/`, or use a community installer against this repo | native `skills/<name>/SKILL.md` |

### Not supported

- **Windsurf** — has no skills/rules marketplace; project rules are plain
  `.windsurfrules` files with no install mechanism. Skills would have to be
  converted by hand; there is no distribution channel.
- **Goose (Block)** — its extension registry is Model Context Protocol
  (MCP) servers, not `SKILL.md` skills. Distributing Magpie there would
  require wrapping skills behind an MCP server (a rebuild, not packaging).

## Versioning

The plugin version tracks the framework release (`0.2.0`). The manifest
version strings are kept in sync with `pyproject.toml` by the
`release-prepare` version bump — see
[`release-management-config.md`](../../projects/magpie/release-management-config.md)
(`version_manifest_files`).

## Verification status

The Claude Code and Gemini CLI manifests follow the current published
schemas. The Codex CLI, GitHub Copilot, and `apm` (schema v0.1) formats
move quickly; re-check each against the vendor's current documentation
before a marketplace publish. Manifests that fail live validation should be
fixed here and re-released — they never change how the ASF source release
is built or signed.
