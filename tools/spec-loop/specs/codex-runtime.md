<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Codex first-class skill runtime
status: experimental
kind: feature
mode: infra
source: >
  RFC-AI-0004 Principle 3 (vendor neutrality) and issue #313.
  Implemented by the canonical .agents/skills tree, the project .codex
  profile, tools/sandbox-lint, tools/agent-isolation,
  docs/adapters/codex.md, and the setup/setup-isolated lifecycle.
acceptance:
  - A maintainer with Codex and no Claude Code can discover and invoke
    Magpie SKILL.md workflows from .agents/skills.
  - Language-neutral tools bridges remain reachable through Codex's native
    sandbox and approval boundary.
  - Project policy uses workspace-write, network-off, on-request
    approvals, and tested exec-policy rules.
  - Adopt, upgrade, verify, and unadopt account for the committed Codex
    policy.
  - setup-isolated install, verify, update, and doctor route to explicit
    Codex steps before any Claude-only procedure.
---

# Codex first-class skill runtime

## What it does

Makes OpenAI Codex a native Magpie runtime rather than a delegation target.
Codex reads the same workflow sources as other harnesses, invokes the same
tool adapters, and uses its own sandbox, rules, and approvals.

## Where it lives

- .agents/skills/ - canonical cross-harness skill symlinks.
- .codex/config.toml - project sandbox and approval posture.
- .codex/rules/magpie.rules - allow, prompt, and forbidden command policy.
- tools/sandbox-lint/ - static Codex profile validator (--codex).
- tools/agent-isolation/ - clean-env agent-iso codex launcher.
- docs/adapters/codex.md - operator contract and lifecycle.
- skills/setup/ and skills/setup-isolated-setup-*/ - installation, drift,
  verification, and removal paths.

## Behaviour & contract

1. Skills remain SKILL.md files. Codex scans .agents/skills natively and
   follows the existing symlinks; no conversion into AGENTS.md occurs.
2. Repository AGENTS.md files remain the instruction hierarchy.
3. workspace-write is mandatory and workspace network access is disabled.
4. Approvals are on-request and reviewed by the user, never automatically.
5. Exec-policy rules allow only scoped read operations, prompt known remote
   mutations, and forbid credential disclosure commands.
6. Project trust is a human decision. Setup never edits Codex trust state.
7. The .codex policy files are committed and reviewed; existing unrelated
   .codex configuration is preserved during adoption and upgrade.

## Out of scope

- Translating SKILL.md workflows into generated AGENTS.md files.
- Copying user credentials or user-scoped MCP configuration into a project.
- Replacing Codex's native approval system with agent-guard decisions. The
  deterministic agent-guard denials stay reachable through the
  harness-neutral --check / --exec modes; a native Codex hook adapter is
  future work.
- Claiming stable support before a minimum version and adopter pilot exist.

## Acceptance criteria

1. /skills lists magpie-setup and at least one end-to-end workflow.
2. Explicit $magpie-* invocation loads the canonical SKILL.md.
3. sandbox-lint --codex .codex passes the repository profile.
4. Native exec-policy checks classify representative read, mutation, and
   credential commands as allow, prompt, and forbidden.
5. setup and setup-isolated documentation covers install, verify, update,
   doctor, and unadopt for Codex.
6. The sandbox-lint test suite covers the Codex profile invariants.
7. Documentation states platform limitations without claiming untested
   parity.

## Validation

```bash
uv run --directory tools/sandbox-lint --group dev pytest
uv run --directory tools/sandbox-lint --group dev sandbox-lint --codex .codex

codex execpolicy check --pretty \
  --rules .codex/rules/magpie.rules -- gh pr view 313
codex execpolicy check --pretty \
  --rules .codex/rules/magpie.rules -- gh pr create --title test --body test
codex execpolicy check --pretty \
  --rules .codex/rules/magpie.rules -- gh auth token
```

## Known gaps

- The adapter remains experimental until the minimum Codex version is pinned
  and an end-to-end adopter pilot runs all acceptance checks.
- Codex exec-policy is an evolving interface.
- The deterministic agent-guard denials are not wired as a native Codex
  hook adapter.
- The POSIX clean-environment wrapper needs WSL on Windows.
- User-scoped MCP registration and tool authentication remain outside
  repository policy.
