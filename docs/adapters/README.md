<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Adapters and runtimes](#adapters-and-runtimes)
  - [Runtimes](#runtimes)
  - [Adapters](#adapters)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Adapters and runtimes

A Magpie skill names no vendor. It says *what* it needs — open a pull
request, fetch a mail thread, read a committee roster — and an **adapter**
binds that request to one concrete service. A **runtime** is the other half:
the agentic tool that executes the skill in the first place.

Both are swappable by configuration rather than by rewriting a skill, which
is what [vendor neutrality](../vendor-neutrality.md) means in practice. This
section is the map of what exists and how to add what does not.

## Runtimes

One page per supported agentic runtime, each declaring
`capability:platform`:

- [**Codex**](codex.md) — first-class runtime.
- [**Cursor**](cursor.md) — Composer and the Agent CLI.
- [**Gemini CLI**](gemini.md) — extension install, `BeforeTool` guard, tool
  sandboxing and policies. Experimental.
- [**Local LLM**](local-llm.md) — Ollama, llama.cpp, vLLM.
- [**OpenCode**](opencode.md) — guard plugin on `tool.execute.before`.

Running something else? [**Adding a new agent harness**](add-a-harness.md)
names every step to wire a new runtime in so it loads skills and enforces
the action guard like the rest.

## Adapters

- [**Adapter registry**](registry.md) — the discovery index of the tool
  adapters that ship with the framework, and the organizations they come
  from.
- [**Authoring an adapter**](authoring.md) — what to do when Magpie ships no
  adapter for your backend: a forge, a CNA tool, a chat system.
