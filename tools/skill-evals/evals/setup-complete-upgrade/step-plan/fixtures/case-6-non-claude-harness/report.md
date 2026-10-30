<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Codex (no `dangerouslyDisableSandbox` equivalent exists). Personal layer: `.apache-magpie-local/`. Isolated setup: configured.

Findings:
- slug: gateway-hook-stale. `~/.claude-config/hooks/container-gateway-hook.sh` lacks the hardening of the framework copy; writing it needs leaving the sandbox.
- slug: checker-copy-stale. The pre-flight checker copy in `.apache-magpie-local/` is older than the shipped one. Writable inside the sandbox.
