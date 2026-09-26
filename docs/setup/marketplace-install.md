<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Prerequisite: install Magpie from your agent's marketplace](#prerequisite-install-magpie-from-your-agents-marketplace)
  - [The recommended baseline](#the-recommended-baseline)
  - [Claude Code](#claude-code)
  - [OpenAI Codex CLI](#openai-codex-cli)
  - [VS Code / GitHub Copilot](#vs-code--github-copilot)
  - [Google Gemini CLI](#google-gemini-cli)
  - [Cursor](#cursor)
  - [microsoft/apm](#microsoftapm)
  - [Kiro CLI](#kiro-cli)
  - [JetBrains IDEs](#jetbrains-ides)
  - [Where to go next](#where-to-go-next)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Prerequisite: install Magpie from your agent's marketplace

You do this **once per machine**, for whichever agent you use. It writes
nothing to any repository, your teammates are unaffected, and every other page
in this documentation assumes it is done.

Every path below uses the [`apache/magpie`](https://github.com/apache/magpie)
repository directly as the marketplace. No vendor directory, no account, no
registry sits in between.

## The recommended baseline

Take these three on every machine, whichever agent you use:

| Plugin | Why |
|---|---|
| `magpie-setup` | **Install this one first — nothing else installs without it.** It installs, upgrades, configures and adopts the framework, and carries the secure-isolation skills that sandbox your agent. |
| `magpie-agent-guard` | The deterministic pre-execution guard — a hook that inspects each shell command before it runs and denies the dangerous shapes outright. Not a family; a safety net under everything else. |
| `magpie-utilities` | `list-skills` and the rest of the small tools you reach for when you want to know what is actually installed. |

These three are exactly the **floor** a project commits when it adopts Magpie,
so taking them yourself is taking what a project would recommend to every
contributor. Then add families against a problem you have today —
[What each family solves](../quick-start/families.md) is the menu — and run the
[secure-agent setup](../quick-start.md#step-3--isolate--guard), which is
part of setting up rather than a later hardening pass.

## Claude Code

Add the marketplace, then install the baseline and whichever families you want:

```text
/plugin marketplace add apache/magpie
/plugin install magpie-setup@apache-magpie
/plugin install magpie-agent-guard@apache-magpie
/plugin install magpie-utilities@apache-magpie
/plugin install magpie-pr-management@apache-magpie
```

The pattern is `/plugin install magpie-<family>@apache-magpie`. Confirm what
landed with `/plugin`.

To track a released version instead of `main`, add the marketplace from a tag:
`/plugin marketplace add apache/magpie@0.2.0`.

**Turn auto-update on — it is off by default here.** Claude Code enables
auto-update for its own official marketplaces, but *third-party* marketplaces,
which `apache-magpie` is, start with it **disabled**. Left alone, your installed
copy never moves: `claude plugin update` answers *"already at the latest
version"* however far ahead `main` has gone, because the check compares version
strings and nothing refreshed the catalogue. Enable it once:

1. run `/plugin`
2. go to **Marketplaces**
3. select **apache-magpie**
4. choose **Enable auto-update**

Claude Code then refreshes the catalogue and updates installed plugins in the
background shortly after each session starts, and tells you to run
`/reload-plugins` if anything moved. Administrators can turn it on for everyone
by setting `"autoUpdate": true` on the marketplace's `extraKnownMarketplaces`
entry in managed settings.

If you would rather stay manual, the equivalent is two commands, and the first
is the one people forget:

```bash
claude plugin marketplace update apache-magpie
claude plugin update magpie-setup@apache-magpie
```

Updating brings in the new skills.
It does not check your project against them.
Magpie does that when you next run a skill:
each skill checks whether it changed since the project was last reconciled,
and the first run after an upgrade proposes any fixes your configuration or overrides now need.
To run the whole check at once, use `/magpie-setup:setup reconcile`.
See [Reconciliation when a skill first runs after an upgrade](marketplace.md#reconciliation-when-a-skill-first-runs-after-an-upgrade).

**After `magpie-setup` is in, you never have to type these again.** Ask for
the rest in plain language and the setup skill runs the installs for you:

> install the Magpie families for PR review and release management

or call it by name — `/magpie-setup:install`. Both take you through the same
picker and the same install. The commands above are the bootstrap, needed only
because nothing is installed yet to hear the request.

## OpenAI Codex CLI

```bash
codex plugin marketplace add apache/magpie
codex plugin install magpie-setup
codex plugin install magpie-agent-guard
codex plugin install magpie-utilities
```

`magpie-setup` installs by default when you add the marketplace, so its line is
only needed if you removed it; the other two baseline plugins are not, so take
them here. Add further families the same way. Verify with `/plugins` inside
Codex, or `codex plugin list` from the shell.

Codex has no auto-update setting for marketplaces, so refreshing is a manual
step — `codex plugin marketplace upgrade` re-pulls the configured Git snapshots.
Run it when you want the newer skills; nothing moves on its own.

Once the baseline is in, ask for the rest in plain language — *install the
Magpie families for PR review* — or invoke the skill by name.

## VS Code / GitHub Copilot

Point VS Code's plugin install at the repository URL — it clones the repo and
loads Magpie as an [Agent Plugins 1.0](https://agent-plugins.org/specification)
package:

```text
https://github.com/apache/magpie
```

You can also add `apache/magpie` as a plugin marketplace and install
individual families from it.

## Google Gemini CLI

```bash
gemini extensions install https://github.com/apache/magpie --auto-update
```

`--auto-update` is worth taking at install time: without it the extension stays
at the commit you installed and only moves when you run
`gemini extensions update magpie` yourself.

Gemini installs Magpie as one extension rather than per-plugin, so the
baseline arrives with it and there is nothing further to pick. Verify with
`gemini extensions list`; update manually at any time with
`gemini extensions update magpie`.

From then on, ask in plain language — *set up Magpie for this project* — or
name the skill: `Use the magpie-setup skill.`

## Cursor

Cursor reads the repository's Agent Plugins 1.0 manifest. Add Magpie through
Cursor's plugin/skill install flow (Customize → Plugins/Skills) pointing at
`github.com/apache/magpie`.

## microsoft/apm

From your project root:

```bash
apm install apache/magpie
```

`apm` deploys the skills into each supported agent's directory and writes an
`apm.lock.yaml`; commit it to pin the resolved commit. There is no auto-update
here by design — the lockfile is the point. Move deliberately by re-running
`apm install` and committing the changed lockfile.

## Kiro CLI

Kiro has **no marketplace**: it installs skills one at a time from a GitHub
subdirectory. Point its *install from GitHub* at the skill you want, on a
pinned tag:

```text
https://github.com/apache/magpie/tree/0.2.0/skills/setup
```

Pin a tag rather than tracking `main` — without a marketplace there is no
update command later, so what you install is what you keep until you install
again. [The Kiro harness guide](../adapters/kiro.md) covers the guard hook and
the rest of the wiring.

## JetBrains IDEs

Nothing extra to install. A JetBrains IDE hosts an agent rather than
distributing skills itself, so you run the install above for the agent you use
inside it — with the Claude Code plugin for JetBrains, the Claude Code commands
from the IDE's Claude Code window.

You only do it once: Claude Code keeps plugin state in a single user-scope
store, so a marketplace added in the terminal is already there in the IDE.

## Where to go next

- [**Quick start**](../quick-start.md) — what to run once the plugins are in.
- [**The Apache Magpie Marketplace**](marketplace.md) — the reference behind
  these commands: which families to pick, how the manifests work, versioning,
  what is verified against a live client and what is not, and the OpenCode
  path, which installs skills directly rather than through a marketplace.
- [**Prerequisites for running framework skills**](../quick-start/prerequisites.md)
  — what individual skills need at run time (a tracker, a mail backend, and so
  on). Separate from this page, and needed only for the skills that use them.
