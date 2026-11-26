<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Snapshot drift check

cat .apache-magpie.lock:
  method: git-branch
  url: https://github.com/apache/magpie.git
  ref: v0.9.1

cat .apache-magpie.local.lock:
  method: git-branch
  url: https://github.com/apache/magpie.git
  ref: v0.9.1

Result: lock files match — no drift.

---

## Check 16 — Read-only vetted ops never prompt

Harness: Claude Code. `.apache-magpie-overrides/tools/vetted-ops/config.toml` exists; effective `sandbox.enabled: true`.

Merged settings:
- `permissions.allow`: `Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-read *)`, `Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-read *)`
- `sandbox.excludedCommands`: both launcher forms of `vetted-op-read` and `vetted-op-tracker`
- no `permissions.ask` rule matching a `vetted-op-read` command
- `permissions.blockReadsOutsideWorkingDirectories`: absent in every scope
- `permissions.deny`: `Edit(~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/**)`, `Edit(~/.claude/magpie/**)`, `Edit(.apache-magpie-overrides/tools/vetted-ops/**)`, `Edit(//**/.apache-magpie-overrides/tools/vetted-ops/**)`, `Edit(~/.config/apache-magpie/vetted-ops/**)`, `Edit(//**/.git/**/apache-magpie/tools/vetted-ops/**)`, `Edit(//**/.svn/apache-magpie/tools/vetted-ops/**)`
- check 9: ✓ (the vetted-ops policy, dispatcher and tamper-protection rules all present)
- no `permissions.additionalDirectories` entry
- agent-guard plugin installed

---

## Check 21 — The read-only gatherer agent

cat ~/.claude/agents/magpie-gatherer.md (frontmatter):

```yaml
---
name: magpie-gatherer
description: Read-only state gatherer for Apache Magpie skills that fan out across many trackers, issues or PRs.
tools: Read, Grep, Glob, Bash, Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-read *), mcp__ponymail__search_list, mcp__ponymail__get_thread, mcp__ponymail__get_email, mcp__ponymail__get_source, mcp__ponymail__auth_status
model: sonnet
hooks:
  PreToolUse:
    - matcher: "mcp__ponymail__(search_list|get_thread|get_email|get_source)"
      hooks:
        - type: command
          command: >-
            printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
---
```

diff against tools/agent-isolation/agents/magpie-gatherer.md: the `tools:` line differs (the local copy adds a bare `Bash`); the body is identical.
