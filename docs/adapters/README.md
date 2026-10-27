<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Adapters and runtimes](#adapters-and-runtimes)
  - [Harnesses](#harnesses)
    - [What isolation each harness actually gets](#what-isolation-each-harness-actually-gets)
  - [Adapters](#adapters)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Adapters and runtimes

A Magpie skill names no vendor. It says *what* it needs — open a pull
request, fetch a mail thread, read a committee roster — and an **adapter**
binds that request to one concrete service. A **runtime** is the other half:
the agentic harness that executes the skill in the first place.

Both are swappable by configuration rather than by rewriting a skill, which
is what [vendor neutrality](../vendor-neutrality.md) means in practice. This
section is the map of what exists and how to add what does not.

## Harnesses

One page per supported agentic harness, each declaring
`capability:platform`:

- [**Aider**](aider.md) — terminal pair programming agent harness.
- [**Antigravity**](antigravity.md) — plugin install, user-scope `PreToolUse`
  guard, terminal sandbox and permission rules. Experimental.
- [**Codex**](codex.md) — first-class harness.
- [**Copilot CLI**](copilot.md) — standalone CLI and Coding Agent.
- [**Cursor**](cursor.md) — Composer and the Agent CLI.
- [**Grok Build**](grok.md) — `PreToolUse` action-guard integration.
- [**JetBrains Junie**](junie.md) — native `.agents/skills/` and `AGENTS.md`, plus an Early Access `PreToolUse` action guard.
- [**Goose**](goose.md) — per-user plugin with a `PreToolUse` guard hook;
  `agent-iso goose` runs the whole process in sandbox-runtime, in approve mode. Experimental.
- [**Kiro CLI**](kiro.md) — per-skill installs, no marketplace; guard on
  `preToolUse`.
- [**Local LLM**](local-llm.md) — Ollama, llama.cpp, vLLM.
- [**OpenCode**](opencode.md) — guard plugin on `tool.execute.before`.
- [**Pi**](pi.md) — one per-user package install: skills, action guard,
  permission rules and an OS sandbox for bash. Experimental.

### What isolation each harness actually gets

Not the same thing, and the differences matter more than the similarities.
Eleven of twelve harnesses get the clean-environment layer; the action guard
reaches nine of twelve.

| Harness | Clean environment | Filesystem sandbox | Action guard |
|---|---|---|---|
| **Claude Code** | `claude-iso` | Seatbelt / bubblewrap, plus a per-repo allowlist | ✅ `PreToolUse` |
| **Antigravity** | `agent-iso agy` | terminal sandbox + user-scope permission rules | ✅ `PreToolUse` |
| **OpenCode** | `opencode-iso` | from the OS-level sandbox | ✅ `tool.execute.before` |
| **Pi** | `agent-iso pi` | sandbox-runtime (Seatbelt / bubblewrap) for bash, from the Claude baseline | ✅ `tool_call` extension |
| **Kiro CLI** | `kiro-iso` | from the OS-level sandbox | ✅ `preToolUse` |
| **Grok Build** | ❌ **none** | ❌ **none** | ✅ `PreToolUse` |
| **JetBrains Junie** | `junie --sandbox` (srt; MCP and hooks unsandboxed) | `/brave` levels and `~/.junie/allowlist.json` | ✅ `PreToolUse` (Early Access) |
| **OpenAI Codex CLI** | `agent-iso codex` | Codex's own sandbox and exec policy, statically validated by [sandbox-lint](../../tools/sandbox-lint/README.md) | ❌ **none** |
| **Cursor** | `agent-iso cursor` | Cursor's own policy | ❌ **none** |
| **Goose** | `agent-iso goose` | sandbox-runtime around the whole Goose process, from the Claude baseline; approve mode | ✅ `PreToolUse` plugin hook |
| **Aider** | `agent-iso aider` | Aider's own policy / git repository map | ❌ **none** |
| **Copilot CLI** | `agent-iso copilot` | Copilot's own approval prompts | ✅ `preToolUse` |

**What the last column costs.** The action guard is what deterministically
refuses a command that would break a hard framework rule — pinging maintainers,
a `Co-Authored-By` trailer, `--no-verify`, marking a PR ready prematurely,
emptying a PR by force-push. On Codex, Cursor and Aider those rules are instructions
the model is asked to follow, not a gate that stops it. These harnesses have
their own approval prompts, and none of them know Magpie's rules out of the box.

That is a gap in the framework, not in those tools: `agent-guard`'s core is
harness-neutral and each supported harness needed only a thin adapter. See
[`tools/agent-guard/README.md`](../../tools/agent-guard/README.md) for the shape
one takes, and [adding a harness](add-a-harness.md) for where it plugs in.

Running something else? [**Adding a new agent harness**](add-a-harness.md)
names every step to wire a new runtime in so it loads skills and enforces
the action guard like the rest.

## Adapters

- [**Adapter registry**](registry.md) — the discovery index of the tool
  adapters that ship with the framework, and the organizations they come
  from.
- [**Authoring an adapter**](authoring.md) — what to do when Magpie ships no
  adapter for your backend: a forge, a CNA tool, a chat system.
