<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Installing Apache Magpie from agent marketplaces](#installing-apache-magpie-from-agent-marketplaces)
  - [Choosing a plugin: all-in-one vs per-family](#choosing-a-plugin-all-in-one-vs-per-family)
  - [Skill names differ by install method](#skill-names-differ-by-install-method)
  - [Supported agents](#supported-agents)
    - [Claude Code](#claude-code)
    - [OpenAI Codex CLI](#openai-codex-cli)
    - [GitHub Copilot](#github-copilot)
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

> [!WARNING]
> **Marketplace/plugin support is experimental in most agentic CLIs.** The
> plugin and marketplace mechanisms of Claude Code, Codex, Copilot, Gemini,
> `apm`, and others are new and evolving — manifest schemas and install
> commands change between releases (see [Verification status](#verification-status)).
> If a marketplace install breaks, or your agent has no marketplace at all, the
> **non-marketplace install is always available, universal, and portable**:
> adopt Magpie with `/magpie-setup` from either the **signed SVN release**
> (`dist.apache.org`) or the **GitHub repo** (git tag or branch) — see
> [`install-recipes.md`](install-recipes.md). That path is **harness-neutral**:
> it wires the skills into *any* agent's directory via the universal
> `.agents/skills/` layout, so it works on **every** agentic CLI — not only the
> ones with a marketplace. Rule of thumb: use a marketplace for a quick trial
> on a supported agent; use `/magpie-setup` for a stable, portable install.

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
| **Claude Code** | `/plugin marketplace add apache/magpie` → `/plugin install magpie@apache-magpie` | `.claude-plugin/marketplace.json` + `plugin.json` |
| **OpenAI Codex CLI** | `codex plugin marketplace add apache/magpie` → install `magpie` | `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` |
| **GitHub Copilot** | add `apache/magpie` as a plugin marketplace → install `magpie` | `marketplace.json` (repo root) |
| **Google Gemini CLI** | `gemini extensions install https://github.com/apache/magpie` | `gemini-extension.json` |
| **Cursor** | add via the plugin/skill install flow pointing at the repo | the plugin manifests above |
| **microsoft/apm** | `apm install apache/magpie` (compiles to Claude/Cursor/Codex/Copilot/Gemini) | `apm.yml` |
| **Kiro** | install per-skill from a GitHub subdirectory | native `skills/<name>/SKILL.md` |
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

### GitHub Copilot

Copilot treats a GitHub repo with a root `marketplace.json` as a plugin
marketplace.

1. Add `apache/magpie` as a plugin marketplace in Copilot (CLI or the
   coding-agent settings).
2. Install the `magpie` plugin from it.
3. The skills become available to the agent under the plugin.

> Copilot's plugin-marketplace commands are still stabilising (enterprise-
> managed plugins are in preview). Confirm the exact `add` / `install`
> syntax in the current Copilot documentation.

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

Cursor consumes the same plugin/skill manifests. Add Magpie through Cursor's
plugin/skill install flow (Customize → Plugins/Skills) pointing at
`github.com/apache/magpie`.

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
| **Codex CLI** | The same [`hooks/check-upgrade.sh`](../../hooks/check-upgrade.sh) wired via the plugin's `hooks` block. Codex's hook schema is **not yet verified** — confirm before publish. |
| **Gemini CLI** | No lifecycle hook; the extension context file [`GEMINI.md`](../../GEMINI.md) instructs the agent to compare the extension version to a recorded marker and prompt on change (LLM-driven, advisory). |
| Other agents | Re-run `/magpie-setup upgrade` manually after updating the package. |

The hook script is read-only apart from writing its own version marker, makes
no network calls, and touches nothing in the adopter repo.

## Versioning

The plugin version tracks the framework release (`0.2.0`). The manifest
version strings are kept in sync with `pyproject.toml` by the
`release-prepare` version bump — see
[`release-management-config.md`](../../projects/magpie/release-management-config.md)
(`version_manifest_files`).

The per-family plugin manifests do not carry their own version: they inherit
`version`, `author`, `homepage`, `repository`, and `license` from the
all-in-one [`.claude-plugin/plugin.json`](../../.claude-plugin/plugin.json), so
a bump has one edit point. Propagate it with
`python3 tools/dev/check-family-plugins.py --fix`; the same script, run as a
prek hook, fails the build on any manifest left behind at the old version.

## Verification status

The Claude Code and Gemini CLI manifests follow the current published
schemas. The Codex CLI, GitHub Copilot, and `apm` (schema v0.1) formats
move quickly; re-check each against the vendor's current documentation
before a marketplace publish. Manifests that fail live validation should be
fixed here and re-released — they never change how the ASF source release
is built or signed.
