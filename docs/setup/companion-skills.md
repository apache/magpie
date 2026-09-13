<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Companion skill packages](#companion-skill-packages)
  - [Aikido Security](#aikido-security)
  - [Claude Security](#claude-security)
  - [Code Review](#code-review)
  - [Superpowers](#superpowers)
  - [Adding to this page](#adding-to-this-page)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- BEGIN generated: companion-skills (tools/dev/check-companion-skills.py --fix) -->

# Companion skill packages

Magpie ships skills for maintaining a project. Some of the things a
maintainer wants next are not maintenance — scanning your own code for
vulnerabilities, or having a method for thinking through a change before
writing it — and other people have built those well. This page names them.

**None of them is a dependency.** Every Magpie family works with none of these
installed. Magpie bundles no third-party skill, fetches none automatically,
and takes no position on which vendor you should prefer; each entry says
whose it is and which agents can run it, so the choice stays yours.

Where a package exists for only one agent, that is stated rather than
smoothed over. A recommendation you cannot act on is worse than none.

## [Aikido Security](https://www.aikido.dev/)

**Vendor:** Aikido · **Pairs with:** `repo-health`, `security`

SAST, secrets and infrastructure-as-code scanning surfaced in the session.

**Claude Code**

```text
/plugin install aikido
```

Not available on OpenAI Codex CLI, VS Code / GitHub Copilot, Google Gemini CLI, Cursor, OpenCode.

## [Claude Security](https://code.claude.com/docs/en/claude-security)

**Vendor:** Anthropic · **Pairs with:** `repo-health`, `security`

A multi-agent vulnerability scan of your own repository, run inside the session; each finding carries a severity, a CWE category and reproduction steps, and the ones you pick become patch files you review before applying.

Claude Code only: it drives subagents and a scan workflow that Agent Plugins 1.0 has no component for. Listed with its harness named rather than presented as the answer for everyone.

**Claude Code**

```text
/plugin install claude-security
```

Not available on OpenAI Codex CLI, VS Code / GitHub Copilot, Google Gemini CLI, Cursor, OpenCode.

## [Code Review](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/code-review)

**Vendor:** Anthropic · **Pairs with:** `pairing`, `pr-management`

Automated pull-request review through several specialised agents, scored by confidence.

**Claude Code**

```text
/plugin install code-review
```

Not available on OpenAI Codex CLI, VS Code / GitHub Copilot, Google Gemini CLI, Cursor, OpenCode.

## [Superpowers](https://github.com/obra/superpowers)

**Vendor:** obra (community) · **Pairs with:** `pairing`, `utilities`

A skills library and development methodology: brainstorming, plan writing, subagent-driven execution, systematic debugging.

Ships a plugin manifest per harness and one shared skills/ tree, the same shape Magpie uses, so it is not a Claude Code-only package.

**Claude Code**

First point Claude Code at the marketplace this package is published in. It is **not** Magpie's — adding it is a trust decision, so it is a step of its own:

```text
/plugin marketplace add obra/superpowers-marketplace
```

Then:

```text
/plugin install superpowers@superpowers-marketplace
```

**OpenAI Codex CLI**

First point OpenAI Codex CLI at the marketplace this package is published in. It is **not** Magpie's — adding it is a trust decision, so it is a step of its own:

```text
codex plugin marketplace add obra/superpowers-marketplace
```

Then:

```text
codex plugin install superpowers
```

**VS Code / GitHub Copilot**

```text
install from github.com/obra/superpowers
```

**Google Gemini CLI**

```text
gemini extensions install https://github.com/obra/superpowers
```

**Cursor**

```text
install from github.com/obra/superpowers through Cursor's plugin flow
```

**OpenCode**

```text
clone the skills you want into .opencode/skills/ from github.com/obra/superpowers
```

## Adding to this page

The source is [`tools/dev/companion-skills.json`](../../tools/dev/companion-skills.json),
whose header carries the rules an entry has to meet — chiefly that it can say
what it adds to a *named* Magpie family, and that it lists every agent it runs
on with that agent's own install command. Run
`python3 tools/dev/check-companion-skills.py --fix` to regenerate this page and
the blocks in the family READMEs.

<!-- END generated: companion-skills -->
