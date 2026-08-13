<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Installing Apache Magpie from agent marketplaces](#installing-apache-magpie-from-agent-marketplaces)
  - [Two manifest families: Agent Plugins 1.0 and client-specific](#two-manifest-families-agent-plugins-10-and-client-specific)
  - [Choosing a plugin: all-in-one vs per-family](#choosing-a-plugin-all-in-one-vs-per-family)
  - [Skill names differ by install method](#skill-names-differ-by-install-method)
  - [Supported agents](#supported-agents)
    - [Claude Code](#claude-code)
    - [OpenAI Codex CLI](#openai-codex-cli)
    - [VS Code and GitHub Copilot](#vs-code-and-github-copilot)
    - [Google Gemini CLI](#google-gemini-cli)
    - [Cursor](#cursor)
    - [microsoft/apm (multiplexer)](#microsoftapm-multiplexer)
    - [Kiro (AWS)](#kiro-aws)
    - [OpenCode](#opencode)
    - [Not supported](#not-supported)
  - [Automatic upgrade detection](#automatic-upgrade-detection)
  - [Versioning](#versioning)
  - [Verification status](#verification-status)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

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

> [!WARNING]
> **Marketplace/plugin support is still young in most agentic CLIs.**
> [Agent Plugins 1.0](#two-manifest-families-agent-plugins-10-and-client-specific)
> standardised the *package format* in August 2026, but it deliberately
> specifies no install mechanism or marketplace format — so install commands,
> catalog schemas, and the client-specific manifests still change between
> releases (see [Verification status](#verification-status)).
> If a marketplace install breaks, or your agent has no marketplace at all, the
> **non-marketplace install is always available, universal, and portable**:
> adopt Magpie with `/magpie-setup` from either the **signed SVN release**
> (`dist.apache.org`) or the **GitHub repo** (git tag or branch) — see
> [`install-recipes.md`](install-recipes.md). That path is **harness-neutral**:
> it wires the skills into *any* agent's directory via the universal
> `.agents/skills/` layout, so it works on **every** agentic CLI — not only the
> ones with a marketplace. Rule of thumb: use a marketplace for a quick trial
> on a supported agent; use `/magpie-setup` for a stable, portable install.

## Two manifest families: Agent Plugins 1.0 and client-specific

Magpie ships **both** of the manifest shapes an agent may look for, because as
of 2026-08 no single one is read by every client.

**[Agent Plugins 1.0](https://agent-plugins.org/specification)** (published
2026-08-06 by a TSC drawn from Amazon, Cursor, Microsoft, OpenAI, and Vercel;
Google has since joined) is the vendor-neutral standard. A conformant plugin is
a directory with a root [`plugin.json`](../../plugin.json) declaring the
canonical `$schema`, plus skills in `skills/<name>/SKILL.md` and — optionally —
MCP servers in a root `mcp.json`. Magpie's skill tree already had exactly that
layout, so conformance needed **no file moves**: the root `plugin.json` is the
only addition.

**Client-specific manifests** stay alongside it, because the clients that
predate the standard still read their own:

| Manifest | Read by | Why it is still needed |
|---|---|---|
| [`plugin.json`](../../plugin.json) (root) | VS Code, GitHub Copilot (CLI + app + SDK) | The AP1 manifest. VS Code auto-detects the format from the root manifest and treats the `$schema` value as the AP1 marker |
| [`.claude-plugin/plugin.json`](../../.claude-plugin/plugin.json) | Claude Code (also read by VS Code) | Claude Code documents only this path, and AP1's schema is closed — it has no place for the `hooks` block or the `skills` path |
| [`.codex-plugin/plugin.json`](../../.codex-plugin/plugin.json) | OpenAI Codex CLI | Codex documents this as its plugin entry point, with its own `interface` / `apps` / `hooks` fields |
| [`gemini-extension.json`](../../gemini-extension.json) | Google Gemini CLI | Gemini's extension format is unrelated to AP1; Google has announced support for the standard but not a migration for this file |
| [`apm.yml`](../../apm.yml) | `microsoft/apm` | A cross-client compiler, not a client — its own package schema |

The manifests do not conflict: they sit at different paths, each client reads
the one it documents, and every one of them points at the same single `skills/`
tree. `tools/dev/check-family-plugins.py` enforces that they all carry the same
version and shared metadata, and that the AP1 manifest stays inside its closed
ten-field schema — a Claude-only key such as `skills` or `hooks` copied into it
is a **fatal** manifest error for an AP1 client, not an ignorable one.

> [!NOTE]
> **AP1 covers skills and MCP servers only.** It deliberately specifies no
> hooks, agents, commands, or marketplace/registry format. So Magpie's
> `SessionStart` upgrade prompt and its marketplace catalogs remain
> client-specific by necessity, not by choice — see
> [Automatic upgrade detection](#automatic-upgrade-detection).

## Choosing a plugin: all-in-one vs per-family

The framework ships as **eleven** plugins. You can install **either** the
all-in-one plugin **or** any number of per-family plugins — and you can mix
several families. Pick based on the trade-off between install simplicity and
always-on token cost (each installed skill advertises a short description to
the model on **every** turn — see ["always-on" cost](#versioning) below).

**All-in-one — `magpie`**

- ✅ One install; all 70 skills; nothing to decide. Uses the real `skills/`
  directory, so **no symlinks** — works on Windows out of the box.
- ⚠️ Adds **~21.7k always-on tokens to every session**, including families you
  may never use — that context (and cost) is spent whether or not you invoke a
  Magpie skill that turn.
- Best when you genuinely want everything, or you're on Windows without symlink
  support.

**Per-family — `magpie-<family>`** *(recommended)*

- ✅ Install only the families you use, so the always-on cost is proportional
  (`magpie-security` ≈ 3.9k, `magpie-pairing` ≈ 0.6k). Install several to mix
  and match.
- ⚠️ You manage a few installs instead of one; adding a family later is a
  separate install; relies on git symlinks (see the Windows note below).
- Best for day-to-day use where you want a lean context window.

Mixing is fine — e.g. install `magpie-release-management` + `magpie-security`
and nothing else. The two are **not** exclusive with the all-in-one either, but
installing both `magpie` *and* a family plugin just double-loads those skills,
so pick one approach.

| Family plugin | Skills | ~Always-on tokens |
|---|---|---|
| `magpie-security` | 12 | ~3.9k |
| `magpie-release-management` | 10 | ~2.9k |
| `magpie-setup` | 9 | ~2.6k |
| `magpie-pr-management` | 8 | ~2.4k |
| `magpie-issue` | 8 | ~2.4k |
| `magpie-repo-health` | 7 | ~2.1k |
| `magpie-contributor-growth` | 6 | ~1.8k |
| `magpie-utilities` | 4 | ~1.4k |
| `magpie-mentoring` | 4 | ~1.2k |
| `magpie-pairing` | 2 | ~0.6k |
| **`magpie`** (all) | **70** | **~21.7k** |

Skills are invoked under the installing plugin's namespace — e.g.
`/magpie:release-vote-tally` (all-in-one) or
`/magpie-release-management:release-vote-tally` (family plugin).

Per-family plugins reference the shared `skills/` tree via symlinks (no copies),
so there is a single source of truth for every skill.

> [!IMPORTANT]
> **Windows + per-family plugins.** The per-family plugins rely on git symlinks
> (each `plugins/magpie-<family>/skills/<skill>` links to the shared
> `skills/<skill>`). Git for Windows does **not** materialise real symlinks
> unless `core.symlinks` is enabled *and* the account may create them (Windows
> Developer Mode, or an elevated shell) — otherwise the clone writes each
> symlink as a plain text file and that family's skills won't load. On Windows,
> either enable symlink support
> (`git config --global core.symlinks true` + Developer Mode) **or** install the
> **all-in-one `magpie` plugin**, which uses the real `skills/` directory and
> needs no symlinks. macOS and Linux are unaffected. (Verified on macOS: a
> `/plugin marketplace add` GitHub clone preserves and resolves the symlinks.)

> [!IMPORTANT]
> **The per-family plugins are not Agent Plugins 1.0 packages.** AP1 requires a
> symlink's final target to resolve *inside* the plugin root, and each family
> plugin's `skills/<skill>` deliberately points out of its own root at the
> shared `../../../skills/<skill>` tree. Materialising them as real directories
> would mean vendored copies of every skill — which
> [PRINCIPLES §13](../../PRINCIPLES.md) rules out, and which would leave eleven
> divergent copies to keep in sync. So the families stay a **Claude Code**
> feature (Claude Code resolves the symlinks, as verified above), and AP1
> clients install the **all-in-one `magpie` plugin**, whose `skills/` *is* the
> real tree and needs no symlink at all. If per-family granularity on AP1
> clients turns out to be worth its cost, the way to get it is to generate
> materialised family directories as a **release artefact** rather than commit
> them — deliberately deferred, not overlooked.

## Skill names differ by install method

The **same skill** is invoked by a **different name** depending on how you
installed it. The portable `/magpie-setup` install bakes a `magpie-` prefix into
each skill's name (so framework skills never collide with your own); the
marketplace plugins namespace with `plugin:skill` and keep the bare skill name.

| Skill (directory) | Portable — `/magpie-setup` snapshot | Marketplace — all-in-one `magpie` | Marketplace — family plugin |
|---|---|---|---|
| `release-vote-tally` | `/magpie-release-vote-tally` | `/magpie:release-vote-tally` | `/magpie-release-management:release-vote-tally` |
| `security-issue-triage` | `/magpie-security-issue-triage` | `/magpie:security-issue-triage` | `/magpie-security:security-issue-triage` |
| `setup` | `/magpie-setup` | `/magpie:setup` | `/magpie-setup:setup` |

Why the difference:

- **Portable install** (`/magpie-setup` snapshot) — the `setup` skill symlinks
  each framework skill under a `magpie-<name>` entry (e.g.
  `skills/release-vote-tally/` → `magpie-release-vote-tally`), and the skill's
  own frontmatter `name:` carries the same `magpie-` prefix. It is therefore
  invoked as a **single hyphenated token**, `/magpie-<name>`. The prefix *is* the
  namespace — it keeps framework skills from clashing with the adopter's own
  skills.
- **Marketplace install** — the **plugin name** is the namespace, applied with a
  **colon**: `/<plugin>:<skill>`. The `magpie-` frontmatter prefix is ignored
  (the plugin already namespaces), so the skill keeps its bare directory name.
  With the all-in-one plugin that's `/magpie:<skill>`; with a family plugin it's
  `/magpie-<family>:<skill>`.

Throughout this repo's own docs and skills, cross-references use the
**portable** form (`/magpie-<name>`), because that is the canonical install.
When you install via a marketplace, translate `/magpie-<name>` to
`/<plugin>:<name>` (drop the `magpie-` prefix, add the plugin namespace).

## Supported agents

Every method below uses the **GitHub repository
[`apache/magpie`](https://github.com/apache/magpie)** as the marketplace —
no third-party or vendor "official" directory is required. Pin to a released
tag (e.g. `0.2.0`) for reproducibility, or track `main` for the latest.

Quick reference:

| Agent | One-liner | Manifest in this repo |
|---|---|---|
| **Claude Code** | `/plugin marketplace add apache/magpie` → `/plugin install magpie@apache-magpie` | `.claude-plugin/marketplace.json` + `.claude-plugin/plugin.json` |
| **OpenAI Codex CLI** | `codex plugin marketplace add apache/magpie` → install `magpie` | `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` |
| **VS Code / GitHub Copilot** | install straight from the repo URL `https://github.com/apache/magpie`, or add it as a plugin marketplace | root `plugin.json` (AP1), `marketplace.json` (repo root) |
| **Google Gemini CLI** | `gemini extensions install https://github.com/apache/magpie` | `gemini-extension.json` |
| **Cursor** | add via the plugin/skill install flow pointing at the repo | root `plugin.json` (AP1) |
| **microsoft/apm** | `apm install apache/magpie` (compiles to Claude/Cursor/Codex/Copilot/Gemini) | `apm.yml` |
| **Kiro** | install per-skill from a GitHub subdirectory, or the AP1 package | root `plugin.json` (AP1), native `skills/<name>/SKILL.md` |
| **OpenCode** | clone skills into `.opencode/skills/`, or use a community installer | native `skills/<name>/SKILL.md` |

Detailed steps per agent follow.

### Claude Code

1. In a Claude Code session, add the marketplace from GitHub — this clones
   the repo and reads `.claude-plugin/marketplace.json`:

   ```text
   /plugin marketplace add apache/magpie
   ```

2. Install the all-in-one plugin, **or** just the families you use:

   ```text
   /plugin install magpie@apache-magpie                    # everything (~21.7k always-on)
   /plugin install magpie-security@apache-magpie           # one family (~3.9k always-on)
   /plugin install magpie-release-management@apache-magpie
   ```

3. Confirm it is enabled (the `magpie` plugin should appear as installed):

   ```text
   /plugin
   ```

4. Invoke any skill under the plugin namespace, e.g.:

   ```text
   /magpie:release-vote-tally
   /magpie:security-issue-triage
   ```

5. **Update** later with `/plugin marketplace update apache-magpie` then
   `/plugin update magpie@apache-magpie`. On a version change the bundled
   `SessionStart` hook also prompts you to run `/magpie-setup upgrade`.

To pin a specific version instead of tracking `main`, add the marketplace
from the tag: `/plugin marketplace add apache/magpie@0.2.0`.

### OpenAI Codex CLI

1. Add the marketplace (reads `.agents/plugins/marketplace.json`):

   ```bash
   codex plugin marketplace add apache/magpie
   ```

2. Install the plugin:

   ```bash
   codex plugin install magpie
   ```

3. List / verify — inside Codex run `/plugins`, or from the shell
   `codex plugin list`.

> Codex's plugin/marketplace verbs are still evolving. If a command name
> differs, check `codex plugin --help`.

### VS Code and GitHub Copilot

Agent Plugins 1.0 support is generally available in VS Code, Copilot CLI, the
Copilot app, and the Copilot SDK on all Copilot plans. VS Code auto-detects the
plugin format from the root manifest, and Magpie's root
[`plugin.json`](../../plugin.json) declares the AP1 `$schema`, so it is loaded
as an AP1 package. Two ways in:

1. **Straight from the repo URL** — no marketplace needed. Point VS Code's
   plugin install at:

   ```text
   https://github.com/apache/magpie
   ```

   VS Code clones the repo and installs the plugin.

2. **As a marketplace** — add `apache/magpie` as a plugin marketplace (CLI or
   the coding-agent settings) and install `magpie` from it. That path reads the
   root [`marketplace.json`](../../marketplace.json).

Either way the 70 skills become available to the agent under the plugin.

> [!NOTE]
> VS Code **ignores client extension data and directories** in an AP1 package.
> Magpie's `.claude-plugin/` hook block is therefore inert here — the upgrade
> prompt is Claude Code-only (see
> [Automatic upgrade detection](#automatic-upgrade-detection)). Existing
> Copilot plugins that do not target AP1 remain supported, so the root
> `marketplace.json` keeps working regardless.

### Google Gemini CLI

1. Install the extension straight from GitHub (reads `gemini-extension.json`
   and auto-discovers the skills under `skills/`):

   ```bash
   gemini extensions install https://github.com/apache/magpie
   ```

2. Verify:

   ```bash
   gemini extensions list
   ```

3. Use the skills by asking the agent in natural language or by skill name.

4. **Update** with `gemini extensions update magpie`. Gemini has no lifecycle
   hook, so the shipped [`GEMINI.md`](../../GEMINI.md) reminds you to run
   `/magpie-setup upgrade` when the version changes.

### Cursor

Cursor is one of the Agent Plugins 1.0 launch clients (and sits on the spec's
TSC), so it reads the root [`plugin.json`](../../plugin.json). Add Magpie
through Cursor's plugin/skill install flow (Customize → Plugins/Skills)
pointing at `github.com/apache/magpie`.

> Confirm the exact add flow in Cursor's current docs — its self-serve
> marketplace surface is evolving.

### microsoft/apm (multiplexer)

`apm` compiles one package to several agents at once (Claude, Cursor, Codex,
Copilot, Gemini).

1. From your project root:

   ```bash
   apm install apache/magpie
   ```

   (reads `apm.yml`, `type: skill`).

2. `apm` deploys the skills into each supported agent's directory and writes
   an `apm.lock.yaml` — commit it to pin the exact resolved commit.

> `apm` schema is **v0.1** and may change; verify verbs with `apm --help`.

### Kiro (AWS)

Kiro installs skills **per-skill from a GitHub subdirectory** (it does not
consume the repo root). For each skill you want, point Kiro's "install from
GitHub" at that skill's subdir on a pinned tag, e.g.:

```text
https://github.com/apache/magpie/tree/0.2.0/skills/release-vote-tally
```

Kiro reads the `skills/<name>/SKILL.md` there.

### OpenCode

OpenCode reads native Agent Skills from `.opencode/skills/`. Either:

- clone the skill directories you want into `.opencode/skills/` (project) or
  `~/.opencode/skills/` (personal) from `github.com/apache/magpie`, or
- use a community installer (e.g. the `opencode-skills-collection` npm
  package) pointed at this repo.

### Not supported

- **Windsurf** — has no skills/rules marketplace; project rules are plain
  `.windsurfrules` files with no install mechanism. Skills would have to be
  converted by hand; there is no distribution channel.
- **Goose (Block)** — its extension registry is Model Context Protocol
  (MCP) servers, not `SKILL.md` skills. Distributing Magpie there would
  require wrapping skills behind an MCP server (a rebuild, not packaging).

## Automatic upgrade detection

When the marketplace updates the plugin to a new version, Magpie prompts you
to run **`/magpie-setup upgrade`** — which reconciles the gitignored snapshot,
the agentic overrides, and drift. This is **detect-and-prompt, not auto-run**:
a plugin hook cannot invoke a slash command, and Magpie never mutates an
adopter repo without the guided skill's confirmation, so the *trigger* is
automatic while the *changes* stay confirmed.

| Agent | Mechanism |
|---|---|
| **Claude Code** | `SessionStart` hook [`hooks/check-upgrade.sh`](../../hooks/check-upgrade.sh) compares the installed version to a marker in the plugin's persistent data dir and prompts on change. Deterministic. |
| **Codex CLI** | The same [`hooks/check-upgrade.sh`](../../hooks/check-upgrade.sh), wired inline via the plugin's `hooks` block — Codex uses the same event schema and the same `SessionStart` event. Codex sets `PLUGIN_ROOT`/`PLUGIN_DATA` (and the `CLAUDE_*` pair for compatibility), which the script reads. See the caveat below. |
| **VS Code / Copilot, Cursor, Kiro (AP1)** | None. Agent Plugins 1.0 specifies no hook component and VS Code ignores client extension directories, so there is nothing to fire. Re-run `/magpie-setup upgrade` after updating. |
| **Gemini CLI** | No lifecycle hook; the extension context file [`GEMINI.md`](../../GEMINI.md) instructs the agent to compare the extension version to a recorded marker and prompt on change (LLM-driven, advisory). |
| Other agents | Re-run `/magpie-setup upgrade` manually after updating the package. |

> [!WARNING]
> **Codex plugin-local hooks may not fire yet.** [openai/codex#16430](https://github.com/openai/codex/issues/16430)
> reports that the runtime executes only the global `hooks.json` even though the
> plugin docs describe plugin-local hooks. The manifest is written to the
> documented schema so it starts working when the runtime catches up; until
> then, treat the Codex upgrade prompt as best-effort and re-run
> `/magpie-setup upgrade` manually.

The hook writes its prompt to **stdout**, which is what a `SessionStart` hook
exiting 0 has added to the session context — stderr on a zero exit reaches only
the debug log. It is read-only apart from writing its own version marker, which
goes to the client-provided persistent data directory (`CLAUDE_PLUGIN_DATA` /
`PLUGIN_DATA`), falling back to `$XDG_STATE_HOME/magpie` — never inside the
plugin checkout, which a plugin update may replace wholesale. It makes no
network calls and touches nothing in the adopter repo.

## Versioning

The plugin version tracks the framework version in `pyproject.toml`, which is
the single authority every manifest mirrors verbatim — **including the `.devN`
suffix**. Between releases the manifests therefore read `0.2.0.dev0`, not
`0.2.0`: a bare `0.2.0` would advertise a release that does not exist yet. Only
a tagged release carries a bare version, and only released versions are ever
published to a marketplace, so the PEP 440 suffix never reaches a consumer.

Nothing is hand-edited. `pyproject.toml` feeds the four ecosystem manifests,
and the all-in-one [`.claude-plugin/plugin.json`](../../.claude-plugin/plugin.json)
in turn feeds the ten per-family manifests and the marketplace entries, which
also inherit `author`, `homepage`, `repository`, and `license`. Bump
`project.version` and run `python3 tools/dev/check-family-plugins.py --fix`; the
same script, run as a prek hook, fails the build on any manifest left behind at
the old version. See
[`release-management-config.md`](../../projects/magpie/release-management-config.md)
(`version_manifest_files`).

## Verification status

Every manifest here has been checked against the vendor's **published
documentation**; what varies is whether it has also been exercised against a
**live install**.

| Manifest | Schema source | Status |
|---|---|---|
| root `plugin.json` | [Agent Plugins 1.0.0 spec](https://github.com/agentplugins/agent-plugins-spec/blob/main/spec/1.0.0.md) + [`plugin.schema.json`](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json) | Conforms to the published closed schema; enforced by `check-family-plugins.py`. Not yet live-installed |
| `.claude-plugin/*` | Claude Code plugins reference | Verified live — `claude plugin validate . --strict` passes with 0 warnings; a family plugin installs and loads from a local marketplace replica |
| `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` | Codex plugin docs (`Package your plugin`) | Matches the documented entry point, field set, and repo-marketplace path. Not yet live-installed; see the plugin-local hooks caveat above |
| root `marketplace.json` | Copilot / VS Code plugin marketplace docs | Legacy-format catalog, explicitly still supported alongside AP1. Not yet live-installed |
| `gemini-extension.json` | Gemini CLI extensions docs | Follows the published schema. Google has joined the AP1 TSC but has published no migration for this file — keep both |
| `apm.yml` | `microsoft/apm` schema **v0.1** | Pre-1.0 and the most likely to churn; re-check before publish |

Re-check each against the vendor's current documentation before a marketplace
publish. Manifests that fail live validation should be fixed here and
re-released — none of them change how the ASF source release is built or
signed.
