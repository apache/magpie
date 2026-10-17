<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [JetBrains Junie](#jetbrains-junie)
  - [Harness contract](#harness-contract)
  - [Installation](#installation)
  - [Action guard](#action-guard)
  - [Verify](#verify)
  - [Known limitations](#known-limitations)
  - [Upstream references](#upstream-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# JetBrains Junie

**Capability:** platform:harness

Junie is JetBrains' own coding agent, available as a CLI and as a JetBrains IDE plugin.
It is a different harness from Claude Code running inside a JetBrains IDE, which needs nothing extra (see [`marketplace.md`](../setup/marketplace.md#jetbrains-ides-intellij-idea-pycharm-goland-)).
Tracking issue: [#321](https://github.com/apache/magpie/issues/321).

## Harness contract

| Surface | Junie contract | Magpie integration |
|---|---|---|
| Skills | Open Agent Skills format; reads `<project>/.agents/skills/` (trusted projects), `~/.agents/skills/`, `<project>/.junie/skills/`, `~/.junie/skills/` | The `universal` registry row; no Junie-specific relay |
| Invoke a skill | Automatically, as `/<skill-name>`, or as `$<skill-name>` | Same skill files as every other harness |
| Instructions | `AGENTS.md` in the project root, `.junie/rules/*.md`, `~/.junie/AGENTS.md` | `AGENTS.md` is read as is |
| MCP | `.junie/mcp/mcp.json` (project) with the usual `mcpServers` shape | Adopter-owned; Magpie writes none |
| Action guard | `PreToolUse` hook in `~/.junie/config.json` (Early Access) | `agent-guard --junie` |
| Sandbox | `junie --sandbox` (sandbox-runtime, macOS and Linux) | Not managed by Magpie |
| Approvals | `/brave` levels and `~/.junie/allowlist.json` | Not managed by Magpie |

## Installation

Install an adopted project with the `universal` target, which is the default.
Junie loads `.agents/skills/` only in a trusted project; trust it from Junie itself, Magpie never grants it.

## Action guard

Junie's hook payload is Claude-shaped (`tool_name`, `tool_input.command`) but its block semantics differ.
Junie honours exit code 2 and a top-level `decision`, and ignores Claude's `hookSpecificOutput`.
The no-argument `agent-guard` would route the payload to the Claude adapter, exit 0, and let every command through.
Hooks must therefore pass `--junie`.

Add to `~/.junie/config.json` (or a file passed with `--config-location`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 <framework>/tools/agent-guard/src/agent_guard/__init__.py --junie",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

Replace `<framework>` with the absolute path of the checkout, or of `.apache-magpie/` for a snapshot adopter.
Junie hooks live in user configuration, so Magpie does not write the file; the adopter adds the entry.

The adapter blocks with exit 2, the denial reason on stderr, and a `{"decision": "deny", "reason": ...}` object on stdout.
Malformed events, other tools, and allowed commands exit 0 silently.
Other non-zero exits only warn in Junie and let the tool run, so the adapter never uses them.

## Verify

1. Confirm the hook is listed in `~/.junie/config.json` and the command path exists.
2. Run `git status` through Junie and confirm it runs.
3. Run `git commit --no-verify --dry-run` and confirm Junie reports a block from `agent-guard[no-verify]`.
4. Run `echo '{"tool_name":"Bash","tool_input":{"command":"git commit --no-verify"}}' | python3 <framework>/tools/agent-guard/src/agent_guard/__init__.py --junie; echo $?` and expect exit 2.

A static check of the config does not replace the live denial probe.

## Known limitations

- Hooks are in Junie's Early Access Program; the schema may change, so re-verify after upgrades.
- The guard covers shell commands only.
  Native file tools, MCP servers, and hooks themselves are outside it, and outside `junie --sandbox` too.
- The sandbox policy is the global `~/.junie/sandbox.json`; a project-local one is ignored, and network is unrestricted unless `allowedDomains` is set.
- The payload shape was taken from the Junie documentation, not a captured live event.
  Capture one and add it to `tools/agent-guard/tests/test_junie.py` when a build is available.
- There is no spec-loop runner profile for Junie yet.

## Upstream references

- Junie skills: https://junie.jetbrains.com/docs/agent-skills.html
- Junie hooks: https://junie.jetbrains.com/docs/junie-cli-hooks.html
- Junie sandbox: https://junie.jetbrains.com/docs/junie-cli-sandbox.html
