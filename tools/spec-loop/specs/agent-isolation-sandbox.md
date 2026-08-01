<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Agent isolation / layered sandbox
status: stable
kind: feature
mode: infra
source: >
  MISSION.md § Privacy, security and supply-chain integrity ("Clean-
  environment wrapper", "Layered sandbox by default", "Pinned, reviewed,
  signed dependencies"). Implemented in tools/agent-isolation/,
  tools/agent-guard/, tools/permission-audit/, tools/egress-gateway/,
  the setup-isolated-setup-* skills, and .claude/settings.json.
acceptance:
  - Every agent subprocess runs inside an OS-level sandbox with default-
    deny filesystem reads and network egress.
  - Credential-shaped env vars are stripped before the agent execs.
  - State-mutating shell calls (git push, and every gh command except
    allow-listed read-only ones) require a confirmation prompt;
    secrets/cred files are deny-read.
---

# Agent isolation / layered sandbox

## What it does

Runs every agent invocation inside a layered sandbox so that even a
successful prompt injection cannot read credentials or reach a
non-allowed host. The fallback when prompt engineering fails is the OS
saying "no".

## Where it lives

- `tools/agent-isolation/` — the harness (clean-env wrapper +
  sandbox profiles).
- `tools/agent-guard/` — deterministic pre-execution guard dispatcher
  (`stdlib`-only). Wired as a `PreToolUse` hook (Claude Code) or a
  `tool.execute.before` plugin (OpenCode); inspects every shell command
  before it runs and denies the ones that break a hard framework rule,
  independent of model memory. The guard decisions live in a single
  harness-agnostic `dispatch()` core so every wired harness enforces
  an identical rule set. Capability: `substrate:action-guard`.
- `tools/permission-audit/` — audits and atomically edits Claude Code's
  `permissions.allow[]` entries in `.claude/settings.json` and
  `.claude/settings.local.json`. Backs the `--apply-permission-audit`
  flag of `/magpie-setup verify` (check 8d). Also handles OpenCode
  `permission` config via `audit-opencode`. Capability: `substrate:sandbox`.
- `tools/egress-gateway/` — local HTTP(S) forward proxy for egress
  control. Framework tools point `HTTPS_PROXY`/`HTTP_PROXY` at it; the
  gateway rejects any connection to a host not on its allowlist before a
  socket is opened. Defence-in-depth per RFC-AI-0003: even a
  prompt-injection reaching for an arbitrary endpoint is blocked at the
  network layer. Capability: `substrate:sandbox`.
- `.claude/settings.json` — the `sandbox` block (filesystem
  allow/deny, network `allowedDomains`, `excludedCommands`) and
  `permissions` (`deny` / `ask`).
- Skills: `setup-isolated-setup-install`, `-update`, `-verify`,
  `-doctor` (probes live sandbox restrictions — SSH-agent reachability,
  localhost port binding, docker/podman socket — and maps each to a
  numbered troubleshooting entry; read-only, never modifies settings).
- `docs/setup/secure-agent-internals.md` — the three-layer model.

## Behaviour & contract

The reference model is four layers, layered:

1. **Clean environment** — a wrapper strips the process env to a
   project-declared whitelist before exec (no `$GH_TOKEN`, `$AWS_*`,
   `$ANTHROPIC_API_KEY` leakage).
2. **Filesystem + network sandbox** — Linux `bubblewrap` + `socat` SNI
   proxy; macOS `sandbox-exec`. Optionally a container-level backend
   (Eclipse Enclave) isolating the whole session instead of each
   subprocess — documented as an option, not yet wired; see
   `docs/setup/secure-agent-internals.md`. Default-deny reads outside
   the tree and
   egress to non-allowed hosts. `sandbox.excludedCommands` carves out
   commands that need host auth the sandbox blocks — `gh` (OS keyring);
   the blast radius is held by layers 3 (`gh auth token` / `gh auth
   refresh` denied) and 4 (`gh` writes gated by `ask`).
3. **Tool permissions** — the host's `permissions.deny` blocks denied
   paths/binaries (`Read(~/.ssh/**)`, `Bash(curl *)`, …).
4. **Forced confirmation** — `permissions.ask` on `git push` and,
   safe-by-default, on `Bash(gh *)`: every `gh` command prompts unless a
   more-specific read-only `allow` rule (`gh pr view`, `gh * list`, …)
   exempts it, so every destructive or unknown `gh` subcommand confirms.

Pinned system tools (`bubblewrap`, `socat`, agent CLI) are aged through a
cooldown window; bumps are PRs, not silent updates.

## Out of scope

- The human-in-the-loop *confirmation* itself (that is the modes' job);
  this area provides the OS-level enforcement underneath it.
- Editing `.claude/settings.json` (it is in the `deny` list).

## Acceptance criteria

1. Filesystem and network default-deny with explicit allow-lists.
2. The clean-env wrapper strips credential-shaped vars before exec.
3. `git push` and `Bash(gh *)` are in `permissions.ask` (read-only `gh`
   exempted via `allow`); secret/cred files are in `permissions.deny`.

## Validation

```bash
uv run --project tools/agent-isolation --group dev pytest
uv run --project tools/agent-guard --group dev pytest
uv run --project tools/permission-audit --group dev pytest
uv run --project tools/egress-gateway --group dev pytest
python3 -c "import json,sys; s=json.load(open('.claude/settings.json')); \
  asks=' '.join(s['permissions']['ask']); \
  sys.exit(0 if 'git push' in asks and 'gh *' in asks else 1)"
```

## Known gaps

- `stable`; drift shows up when a new state-mutating command is added to a
  skill without a matching `ask` rule — the plan pass flags it.
- **`tools/agent-guard/` and `tools/egress-gateway/` are new additions**
  since the last pilot cycle; end-to-end integration with a real adopter
  session has not yet been exercised.
- **The container-level Layer 2 backend is documented, not implemented.**
  Eclipse Enclave is incubating with no released artefact, so there is no
  pin entry, no backend selector in `agent-iso.sh`, and no check in
  `setup-isolated-setup-verify`. The framework states the contract it
  needs; wiring follows a stable Enclave release.
