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

Harness: Claude Code.

cat ~/.claude/agents/magpie-gatherer.md (frontmatter):

```yaml
---
name: magpie-gatherer
description: Read-only state gatherer for Apache Magpie skills that fan out across many trackers, issues or PRs (pr-management-code-review prefetch, pr-management-stack-review layer readers). Dispatched by a Magpie skill's orchestrator to assess ONE item and return a structured report. Never mutates anything. Do not use for non-Magpie work, and do not use when the orchestrator wants an item applied rather than assessed.
tools: Read, Grep, Glob, Bash, Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-read *)
color: cyan
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: >-
            python3 -I -c 'import json,re,sys; c=json.load(sys.stdin).get("tool_input",{}).get("command",""); ok=re.fullmatch(r"uvx --from ~/\.claude/magpie/vetted-ops vetted-op-read( [A-Za-z0-9_.:=/@,+-]+)+", c) and not re.search(r"(^| )--(config|save)(=| |$)", c); ok or print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"magpie-gatherer runs only `uvx --from ~/.claude/magpie/vetted-ops vetted-op-read --caller <caller> <operation> [param ...]`, without --config or --save"}}))'
            || { echo "magpie-gatherer: the Bash guard could not run, so the command is blocked" >&2; exit 2; }
---
```

diff against tools/agent-isolation/agents/magpie-gatherer.md: only the `tools:` line differs (the local copy adds a bare `Bash`); the hook and the body are identical.

User-scope `permissions.deny` includes `Edit(~/.claude/agents/**)`.
