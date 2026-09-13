<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Prerequisite: install Magpie from your agent's marketplace](#prerequisite-install-magpie-from-your-agents-marketplace)
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

`magpie-setup` is the one plugin to always take — it installs, upgrades and
adopts the framework, and it carries the secure-isolation skills. Add families
to match a problem you have today; you can install more at any time, and
[What each family solves](../quick-start/families.md) is the menu.

## Claude Code

Add the marketplace, then install the families you want:

```text
/plugin marketplace add apache/magpie
/plugin install magpie-setup@apache-magpie
/plugin install magpie-pr-management@apache-magpie
```

The pattern is `/plugin install magpie-<family>@apache-magpie`. Confirm what
landed with `/plugin`.

To track a released version instead of `main`, add the marketplace from a tag:
`/plugin marketplace add apache/magpie@0.2.0`.

## OpenAI Codex CLI

```bash
codex plugin marketplace add apache/magpie
codex plugin install magpie-setup
```

`magpie-setup` installs by default when you add the marketplace, so the second
command is only needed if you removed it. Add further families the same way.
Verify with `/plugins` inside Codex, or `codex plugin list` from the shell.

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
gemini extensions install https://github.com/apache/magpie
```

Verify with `gemini extensions list`; update with
`gemini extensions update magpie`.

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
`apm.lock.yaml`; commit it to pin the resolved commit.

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
