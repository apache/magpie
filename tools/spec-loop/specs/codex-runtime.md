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
  - Native PreToolUse guards deny framework violations while ordinary calls
    remain subject to Codex approvals; hook trust is reviewed separately.
  - Fixed installed vetted-op-read prefixes allow reads; both write entry
    points prompt, with per-machine native rules rendered for review.
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
- tools/agent-guard/ - native --codex PreToolUse adapter.
- tools/vetted-ops/ - native per-machine prefix-rule renderer.
- plugins/magpie-agent-guard/ and plugins/magpie-vetted-ops/ - self-contained
  installed runtimes advertised by the Codex marketplace catalogue.
- docs/adapters/codex.md - operator contract and lifecycle.
- plugins/magpie-setup/skills/setup/ and
  plugins/magpie-setup/skills/isolated-setup-*/ (linked from skills/setup and
  skills/setup-isolated-setup-*) - installation, drift, verification, and
  removal paths.
- tools/adversarial-review/ - Codex as an adversarial reviewer backend, and
  the Codex command file for asking other models to review a change
  (see [adversarial review](adversarial-review.md)).

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
8. Codex as a reviewer runs read-only: the adversarial-review tool invokes
   `codex exec -s read-only --ephemeral -c mcp_servers={}` with an output
   schema, pinned by `tools/adversarial-review/tests/test_backends.py`, and
   skips it when Codex is the harness running the review.
9. From a Codex session, `setup config adversarial-review` can write
   `~/.codex/prompts/magpie-adversarial-review.md`, rendered by
   `adversarial-review commands --harness codex`, under the user's home and
   never in a repository.
   The prompt resolves the newest installed plugin version at run time and
   tells the agent to ask for an unsandboxed run, because the reviewer CLIs
   need network and their own credentials.

10. The native Bash PreToolUse adapter uses Codex's canonical event and JSON
    deny schema, including unified exec. Ordinary commands never receive an
    implicit hook approval. Source and snapshot project registrations resolve
    the engine from the git root; plugin-owned or user-scope engines outside
    writable roots are preferred for routine adopters.
11. Project trust and /hooks definition trust are independent operator decisions.
    Hook errors can fail open, interactive write_stdin input is not rechecked,
    and editing a workspace-owned engine does not renew definition trust.
12. Static lint checks the project engine's existence, accepts absolute
    user-scope paths, and offers --guard-from-plugin for separately verified
    plugin registration and trust without a duplicate project hook.
13. Vetted reads use exact installed paths for both uv launchers. Writes keep
    native prompt decisions; generated rules never allowlist a general uv
    command or a mutable checkout. Code and policy tamper limitations and the
    remaining differences from Claude are reported explicitly.
14. The Codex catalogue (`.agents/plugins/marketplace.json`) marks
    `magpie-vetted-ops` `INSTALLED_BY_DEFAULT`, beside `magpie-setup`
    (#1761). Installing it grants nothing: its native rules, like the
    Claude allow rules and sandbox exclusions, are wired only where the
    isolated setup is configured.

## Out of scope

- Translating SKILL.md workflows into generated AGENTS.md files.
- Copying user credentials or user-scoped MCP configuration into a project.
- Replacing Codex's native approval system with agent-guard decisions.
  Harness-neutral --check / --exec modes remain available alongside native hooks.
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
8. Source and snapshot native hooks deny synthetic forbidden commands; the
   validator rejects missing engines and disabled hooks, while plugin mode
   explicitly leaves plugin trust uninspected.
9. The native rule evaluator classifies both vetted read prefixes as allow
   and the four write prefixes as prompt; extra launcher flags do not match.
10. Source-only edits trigger plugin-copy regeneration in commit and PR checks.

## Validation

```bash
uv run --directory tools/sandbox-lint --group dev pytest
uv run --project tools/sandbox-lint --group dev sandbox-lint --codex .codex

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
- Static registration does not prove live hook trust. Workspace-owned engines
  remain mutable, and the profile supplies no home-directory read denylist.
- The container-gateway hook and optional eval/adversarial-review prefixes do
  not have native Codex wiring in this profile.
- The POSIX clean-environment wrapper needs WSL on Windows.
- User-scoped MCP registration and tool authentication remain outside
  repository policy.
- As a reviewer, `codex -s read-only` restricts writes and network but not
  reads, so an instruction injected into a reviewed diff could have it read
  files elsewhere on the machine; the adversarial-review README tells
  operators to leave `codex` out of the reviewer list on machines that hold
  private checkouts.
