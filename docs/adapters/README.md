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

- [**Codex**](codex.md) — first-class harness.
- [**Cursor**](cursor.md) — Composer and the Agent CLI.
- [**Gemini CLI**](gemini.md) — extension install, `BeforeTool` guard, tool
  sandboxing and policies. Experimental.
- [**Kiro CLI**](kiro.md) — per-skill installs, no marketplace; guard on
  `preToolUse`.
- [**Local LLM**](local-llm.md) — Ollama, llama.cpp, vLLM.
- [**OpenCode**](opencode.md) — guard plugin on `tool.execute.before`.

### What isolation each harness actually gets

Not the same thing, and the differences matter more than the similarities.
Every harness gets the clean-environment layer; the action guard reaches four
of six.

| Harness | Clean environment | Filesystem sandbox | Action guard |
|---|---|---|---|
| **Claude Code** | `claude-iso` | Seatbelt / bubblewrap, plus a per-repo allowlist | ✅ `PreToolUse` |
| **Gemini CLI** | `agent-iso gemini` | tool sandboxing + policies | ✅ `BeforeTool` |
| **OpenCode** | `opencode-iso` | from the OS-level sandbox | ✅ `tool.execute.before` |
| **Kiro CLI** | `kiro-iso` | from the OS-level sandbox | ✅ `preToolUse` |
| **OpenAI Codex CLI** | `agent-iso codex` | Codex's own sandbox and exec policy, statically validated by [sandbox-lint](../../tools/sandbox-lint/README.md) | ❌ **none** |
| **Cursor** | `agent-iso cursor` | Cursor's own policy | ❌ **none** |

**What the last column costs.** The action guard is what deterministically
refuses a command that would break a hard framework rule — pinging maintainers,
a `Co-Authored-By` trailer, `--no-verify`, marking a PR ready prematurely,
emptying a PR by force-push. On Codex and Cursor those rules are instructions
the model is asked to follow, not a gate that stops it. Both harnesses have
their own approval prompts, and neither knows Magpie's rules.

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
