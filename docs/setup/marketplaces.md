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
    - [JetBrains IDEs (IntelliJ IDEA, PyCharm, GoLand, …)](#jetbrains-ides-intellij-idea-pycharm-goland-)
    - [Not supported](#not-supported)
  - [Auto-install: arriving Magpie-ready](#auto-install-arriving-magpie-ready)
    - [What each harness supports](#what-each-harness-supports)
    - [Claude Code: the default set](#claude-code-the-default-set)
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
> 74 skills into your agent so you can use them immediately. It does **not**
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

- ✅ One install; all 74 skills; nothing to decide. Uses the real `skills/`
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
| **JetBrains IDEs** (IntelliJ, PyCharm, …) | nothing of its own — install for the agent you run inside the IDE, e.g. Claude Code's `/plugin marketplace add apache/magpie` | none; a host, not a distribution target |

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

Only the **all-in-one** `magpie` plugin is offered here — the per-family
plugins are Claude Code-only, for the reason recorded
[above](#choosing-a-plugin-all-in-one-vs-per-family). The catalog is checked
against that rule by `tools/dev/check-family-plugins.py`, so it cannot drift
into advertising a plugin Codex could not install.

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

Either way the 74 skills become available to the agent under the plugin. As
with Codex, only the **all-in-one** `magpie` plugin is offered — the per-family
plugins are Claude Code-only, for the reason recorded
[above](#choosing-a-plugin-all-in-one-vs-per-family).

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

### JetBrains IDEs (IntelliJ IDEA, PyCharm, GoLand, …)

A JetBrains IDE is a **host for an agent, not a distribution target of its
own** — which is why it appears in no table above and ships no manifest in this
repo. Nothing here needs installing *for* IntelliJ; you install for the agent
you run inside it.

With the **Claude Code plugin for JetBrains**, the install is the ordinary
Claude Code one, run from the IDE's Claude Code window:

```text
/plugin marketplace add apache/magpie
/plugin install magpie-setup@apache-magpie
/plugin install magpie-utilities@apache-magpie
```

You do not have to run it twice. Claude Code keeps its plugin state in one
user-scope store — `~/.claude/plugins/` (`known_marketplaces.json` and
`installed_plugins.json`) — and every host that launches the same CLI reads it:
the terminal, the VS Code extension, and the JetBrains plugin alike. Install
from any one of them and the skills are there in the others. The same holds for
the [auto-install](#auto-install-arriving-magpie-ready) block: it lives in the
project's `.claude/settings.json`, so opening that project in IntelliJ picks it
up exactly as opening it in a terminal does.

Project-scope installs are keyed by the project's **path**, so a repo opened at
the same path in the IDE and in a terminal shares them; a second clone
elsewhere is a separate project and installs separately.

> [!NOTE]
> This is about running *Claude Code* (or another agent with a JetBrains
> plugin) inside a JetBrains IDE. **JetBrains' own agent, Junie, is a separate
> harness port** — tracked as
> [#321](https://github.com/apache/magpie/issues/321) and listed *Not yet
> ported* in [`CONTRIBUTING.md`](../../CONTRIBUTING.md) and
> [`vendor-neutrality.md`](../vendor-neutrality.md). Junie does not read
> Magpie's skills today.

### Not supported

- **Windsurf** — has no skills/rules marketplace; project rules are plain
  `.windsurfrules` files with no install mechanism. Skills would have to be
  converted by hand; there is no distribution channel.
- **Goose (Block)** — its extension registry is Model Context Protocol
  (MCP) servers, not `SKILL.md` skills. Distributing Magpie there would
  require wrapping skills behind an MCP server (a rebuild, not packaging).

## Auto-install: arriving Magpie-ready

Everything above is a person typing an install command. A project can instead
commit the wiring, so a contributor who clones it and opens their agent finds
Magpie already there. **Only Claude Code can actually do this**, and the
difference is structural rather than a gap someone forgot to fill.

### What each harness supports

| Harness | Auto-install | Mechanism |
|---|---|---|
| **Claude Code** | ✅ per-family | `extraKnownMarketplaces` + `enabledPlugins` in the project's `.claude/settings.json` |
| **OpenAI Codex CLI** | ⚠️ all-or-nothing | `policy.installation: "INSTALLED_BY_DEFAULT"` in `.agents/plugins/marketplace.json` — installs **all ten families**, so Magpie does not use it |
| **VS Code / GitHub Copilot** | ❌ | No repo-side mechanism. The catalogue advertises; it cannot pre-install |
| **Google Gemini CLI** | ❌ | Install is explicit-only. Gemini does **not** load a workspace `.gemini/extensions/` directory — verified against the CLI, which reports "No extensions installed" for a repo-local extension |
| **JetBrains IDEs** | ✅ inherited | Whatever the agent running inside the IDE supports. With Claude Code's JetBrains plugin that is the row above — the project's `.claude/settings.json` applies unchanged, because plugin state is one user-scope store shared by every host of the same CLI |

The Codex and Copilot rows are the same constraint that keeps those catalogues
listing only the all-in-one plugin: a family plugin reaches its skills through
symlinks that resolve outside its own root, which Agent Plugins 1.0 forbids, so
**per-family is a Claude Code feature**. Codex can therefore only default-install
*everything*, which contradicts the load-only-what-you-use argument this page
makes — so the catalogue pins `installation: "AVAILABLE"`, and
`check-family-plugins.py` fails the build if that value drifts.

> [!WARNING]
> Codex parses its catalogue strictly and its policy values are closed
> SCREAMING_SNAKE enums (`NOT_AVAILABLE` / `AVAILABLE` /
> `INSTALLED_BY_DEFAULT`, and `ON_INSTALL` / `ON_USE` for the optional
> `authentication`). An unknown variant does not mis-label the plugin — it
> makes `codex plugin marketplace add` reject the **whole file**, so nothing
> installs. This catalogue shipped invented values (`manual`, `none`) for a
> release before anyone ran the command.

### Claude Code: the default set

Add to the project's `.claude/settings.json` — committed, so it applies to
everyone who trusts the repo:

```json
{
  "extraKnownMarketplaces": {
    "apache-magpie": {
      "source": { "source": "github", "repo": "apache/magpie" }
    }
  },
  "enabledPlugins": {
    "magpie-setup@apache-magpie": true,
    "magpie-utilities@apache-magpie": true,
    "magpie-agent-guard@apache-magpie": true
  }
}
```

Three plugins, for two different reasons.

`setup` and `utilities` are the framework's two **always-on families** — the
same pair the pinned-snapshot install wires unconditionally, with no way to ask
for them or opt out. Between them a newcomer gets `/magpie-setup` to adopt and
maintain the framework and `/magpie-utilities:list-skills` to discover
everything else, at the smallest always-on cost. Every other family stays
opt-in, which is the point.

`magpie-agent-guard` is not a family at all — it is a
[substrate plugin](#choosing-a-plugin-all-in-one-vs-per-family), a `PreToolUse`
hook that denies shell commands which would break a hard framework rule
(pinging maintainers, a `Co-Authored-By` trailer, marking a PR ready
prematurely, leaking security language onto a public thread, emptying a PR via
force-push). It is in the default set because a guard nobody remembered to
install guards nothing: it costs no always-on context — it is a hook, not
skills — and it is most valuable in exactly the sessions where nobody was
thinking about it. It only ever *denies*, so the failure mode of having it on
is a blocked command with a stated reason, not a silent action.

> [!NOTE]
> The guard runs from the installed plugin, so no repository or worktree needs
> a local copy — and a contributor who has not enabled it is not protected by
> it. That asymmetry is the argument for defaulting it on rather than
> documenting it as optional.

Pin the marketplace to a released tag by using `"repo": "apache/magpie@0.2.0"`
if the project would rather not track `main`.

Contributors keep the last word: a plugin enabled this way still appears in
`/plugin`, and anyone can disable it locally.

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
suffix**. Between releases the manifests therefore read
`0.2.0.dev<YYYYMMDDHHMM>`, not `0.2.0`: a bare `0.2.0` would advertise a
release that does not exist yet. Only a tagged release carries a bare version.

**The dev suffix is a UTC timestamp, and it has to move for adopters to pick
anything up.** This marketplace is served straight from the `main` branch of a
git repo, so consumers *do* install dev versions — the suffix reaching them is
the normal case, not the exception. `claude plugin update` compares version
strings, not commit SHAs: while the suffix stays frozen at a constant like
`.dev0`, an adopter's `claude plugin update` answers "already at the latest
version" and never moves the pinned commit, however far behind `main` the
installed copy has fallen. Their only recovery is
`claude plugin marketplace update` followed by a full uninstall + reinstall of
every plugin, which nobody discovers on their own.

**When to bump.** Not every PR — that would put every contributor in conflict
with every other over one line, for no gain on changes nobody is waiting for.
Bump when the work needs to reach installed copies: before pointing anyone at
`claude plugin update`, before announcing a change adopters should take, or
when a batch of merged work has piled up behind a stale stamp. A bump is a
one-line edit plus a regeneration, so it costs little whenever it is actually
wanted.

The stamp is minute-resolution and **UTC**, not local time: a repo with
contributors in several timezones needs the string to sort in the order the
bumps were actually made, and a date alone would collide whenever a day carries
more than one.

Nothing is hand-edited. `pyproject.toml` feeds the four ecosystem manifests,
and the all-in-one [`.claude-plugin/plugin.json`](../../.claude-plugin/plugin.json)
in turn feeds the ten per-family manifests and the marketplace entries, which
also inherit `author`, `homepage`, `repository`, and `license`. Bump
`project.version` and run `python3 tools/dev/check-family-plugins.py --fix`; the
same script runs as a prek hook in `--fix` mode, so a manifest left behind at
the old version is regenerated in place and the run fails until the corrected
file is staged. See
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
| `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` | Codex plugin docs (`Package your plugin`) + the `codex` binary's own enums | **Verified live** — `codex plugin marketplace add` + `plugin list` against codex 0.154.0. The first live run is what caught the invented `policy` values the documentation check could not; the enums are now enforced by `check-family-plugins.py`. See the plugin-local hooks caveat above |
| root `marketplace.json` | Copilot / VS Code plugin marketplace docs | Legacy-format catalog, explicitly still supported alongside AP1. Not yet live-installed |
| `gemini-extension.json` | Gemini CLI extensions docs | Follows the published schema. Google has joined the AP1 TSC but has published no migration for this file — keep both |
| `apm.yml` | `microsoft/apm` schema **v0.1** | Pre-1.0 and the most likely to churn; re-check before publish |

The skills themselves are checked against the
[Agent Skills specification](https://agentskills.io/specification), which AP1
defers to. Worth stating explicitly, because it looks like a problem and is
not: 45 of the 74 `description` fields contain the framework's
`<placeholder>` syntax (`<tracker>`, `<upstream>`, …). The spec constrains
`description` on **length only** — 1–1024 characters, non-empty — and places no
restriction on angle brackets; the character-class rules apply to `name`, which
every skill satisfies. So the placeholders are conformant, not a portability
risk to design around.

Re-check each against the vendor's current documentation before a marketplace
publish. Manifests that fail live validation should be fixed here and
re-released — none of them change how the ASF source release is built or
signed.
