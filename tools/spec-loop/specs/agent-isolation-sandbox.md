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
  - The reference setup uses an OS-level sandbox with default-deny
    filesystem reads and network egress; runtime-specific exceptions
    are documented in the adapter and this spec.
  - Credential-shaped env vars are stripped before the agent execs.
  - State-mutating shell calls (git push and every gh write subcommand,
    each listed explicitly) require a confirmation prompt; read-only gh
    subcommands do not; secrets/cred files are deny-read.
---

# Agent isolation / layered sandbox

## What it does

Runs reference agent invocations inside a layered sandbox so that even a
successful prompt injection cannot read credentials or reach a
non-allowed host. The fallback when prompt engineering fails is the OS
saying "no".

Gemini CLI uses tool sandboxing rather than whole-process isolation.
Its native file tools restrict reads to allowed directories, but the tested
Linux backend exposes host files broadly read-only to approved shell commands.
Native credential-path policy denies do not block equivalent shell reads.
Tool network restrictions do not cover the CLI, hooks, or MCP servers;
existing sandbox grants can widen the baseline. See `docs/adapters/gemini.md`.

## Where it lives

- `tools/agent-isolation/` — the harness (clean-env wrapper +
  sandbox profiles).
- `tools/agent-isolation/gpg-touch-overlay.sh` (+ the two window
  scripts) — the hardware-key touch overlay: a window on screen while a
  signing key or ssh authentication key with a touch policy blocks
  waiting for a touch. Two entry points to one watcher: `arm` /
  `disarm` as a `PreToolUse` / `PostToolUse` `Bash` hook around the
  agent's git commands, and `wrap` as git's own signing program and ssh
  command (`gpg.ssh.program` / `gpg.program` through an argument-free
  `gpg-touch-wrap-<program>` symlink, `core.sshCommand … wrap ssh`) for
  the commits and pushes the operator makes by hand — no git hook type
  sits at the right moment for those. Never two windows for one
  signature: inside an agent session (`CLAUDECODE=1`) the wrapper only
  runs the program and the hook's watcher shows the window; outside
  one, a watcher already recorded in the pid file is left alone. The
  git the agent runs reads the same global config, so the wrapper's
  two files are a `sandbox.filesystem.allowRead` grant of their own
  (nothing wider under `~/.claude/`), or every sandboxed signed commit
  fails with `cannot exec`. Installed by `setup-isolated-setup-install` Step K,
  checked by `setup-isolated-setup-verify` check 10. Capability:
  `substrate:sandbox`.
- `tools/agent-guard/` — deterministic pre-execution guard dispatcher
  (`stdlib`-only). Wired as a `PreToolUse` hook (Claude Code) or a
  `tool.execute.before` plugin (OpenCode), with a `--gemini` adapter for
  Gemini CLI's `BeforeTool` event (wired in the repository's
  `.gemini/settings.json`; registration for snapshot adopters); inspects every shell command
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
- `.gemini/settings.json` and `.gemini/policies/magpie.toml` — Magpie's Gemini profile: tool-sandboxing and an explicitly loaded User-tier approval policy.
  Scoped shell reads are allowed; other shell calls, native edits, and MCP calls ask; listed commands and credential paths deny.
  Credential-path denies name the canonical `grep_search`; the native probe verifies its `search_file_content` alias, canonical policy names, and search/multi-file/web/resource argument schemas against the loaded runtime.
  `google_web_search`, `web_fetch`, and `read_mcp_resource` require approval for each call in every mode, including auto-edit and Plan Mode; headless calls are refused.
  Web search and URL fetching run outside shell network isolation; native MCP resource reads need an explicit rule because the MCP server-tool wildcard does not match them.
  `list_mcp_resources` retains the built-in allow for cached resource discovery.
  The native probe executes resource listing against a synthetic cache, asserts that metadata reaches the model, and rejects access to an MCP client.
  Plan Mode permits the scoped reads and approved web/resource reads, and denies other shell calls, file edits, and MCP server tools; YOLO and remembered tool approvals are disabled.
  `sandbox-lint --gemini .gemini` checks the static profile, with opt-in pytest integration tests against native 0.59.0 APIs for settings, policies, headless refusal, and Linux enforcement.
  Every Gemini upgrade requires revalidating the native probe against that version; static CI checks alone do not establish effective policy precedence.
- Skills: `setup-isolated-setup-install`, `-update`, `-verify`,
  `-doctor`. The diagnostic side — the failure catalog in
  `docs/setup/sandbox-troubleshooting.md`, the `sandbox-error-hint.sh`
  hook, the doctor's live probes and the verify checks — is specified
  in [`sandbox-diagnostics.md`](sandbox-diagnostics.md).
- `docs/setup/secure-agent-internals.md` — the three-layer model.

## Behaviour & contract

The reference model is four layers, layered:

1. **Clean environment** — a wrapper strips the process env to a
   project-declared whitelist before exec (no `$GH_TOKEN`, `$AWS_*`,
   `$ANTHROPIC_API_KEY` leakage).
   `AGENT_ISO_ALLOW` explicitly names additional variables required by runtime authentication or tooling.
   It replaces `CLAUDE_ISO_ALLOW` when set, including an empty value; the legacy name remains supported otherwise.
   Unlisted variables stay stripped and values are never printed by the wrapper.
2. **Filesystem + network sandbox** — Linux `bubblewrap` + `socat` SNI
   proxy; macOS `sandbox-exec`. Default-deny reads outside the tree and
   egress to non-allowed hosts. `sandbox.excludedCommands` carves out
   commands that need host auth the sandbox blocks — `gh` (OS keyring
   and, on macOS, Security.framework TLS verification); the blast
   radius is held by layers 3 (`gh auth token` / `gh auth refresh`
   denied) and 4 (`gh` writes gated by `ask`). The exemption applies
   only to invocations made of `cd …` / `gh …` parts; the shape rule
   and its failure signature are in
   [`sandbox-diagnostics.md`](sandbox-diagnostics.md).
3. **Tool permissions** — the host's `permissions.deny` blocks denied
   paths/binaries (`Read(~/.ssh/**)`, `Bash(curl *)`, …).
4. **Forced confirmation** — `permissions.ask` on `git push` and,
   on every `gh` **write** subcommand, listed one by one (`gh pr merge`,
   `gh issue close`, `gh release delete`, `gh api`, …). Not on a
   catch-all `Bash(gh *)`: Claude Code evaluates deny, then ask, then
   allow, and a matching ask rule prompts even when a more specific
   allow rule also matches, so a catch-all would silently defeat the
   read-only allows (`gh pr view`, `gh * list`, …) and prompt on every
   read. A subcommand in neither list falls through to the mode's
   default (prompt in default mode, classifier in auto).

Pinned system tools (`bubblewrap`, `socat`, agent CLI) are aged through a
cooldown window; bumps are PRs, not silent updates.

## Out of scope

- The human-in-the-loop *confirmation* itself (that is the modes' job);
  this area provides the OS-level enforcement underneath it.
- Editing `.claude/settings.json` (it is in the `deny` list).

## Acceptance criteria

1. Filesystem and network default-deny with explicit allow-lists in the
   reference setup; Gemini's different boundaries are documented above.
2. The clean-env wrapper strips credential-shaped vars before exec.
3. `git push` and every `gh` write subcommand are in `permissions.ask`,
   the read-only `gh` subcommands are in `allow`, and no catch-all
   `Bash(gh *)` sits in `ask`; secret/cred files are in `permissions.deny`.

## Validation

```bash
uv run --project tools/agent-isolation --group dev pytest
uv run --directory tools/agent-guard --group dev pytest
uv run --project tools/permission-audit --group dev pytest
uv run --project tools/egress-gateway --group dev pytest
python3 -c "import json,sys; s=json.load(open('.claude/settings.json')); \
  ask=s['permissions']['ask']; \
  sys.exit(0 if any(a.startswith('Bash(git push') for a in ask) \
    and 'Bash(gh pr merge *)' in ask and 'Bash(gh *)' not in ask else 1)"
```

## Known gaps

- `stable`; drift shows up when a new state-mutating command is added to a
  skill without a matching `ask` rule — the plan pass flags it.
- **`tools/agent-guard/` and `tools/egress-gateway/` are new additions**
  since the last pilot cycle; end-to-end integration with a real adopter
  session has not yet been exercised.

## Gemini setup lifecycle

The four `setup-isolated-setup-*` skills route Gemini requests to
`docs/adapters/gemini.md` and stop before the Claude-specific procedure.
The install route merges the workspace profile and a single guard registration
from the existing extension, snapshot, or framework checkout, preserving
unrelated settings and requiring review of conflicts.
Extension setup must not introduce a second snapshot installation.
Verification distinguishes static configuration from live enforcement;
update and doctor report drift or diagnoses without applying changes.
Generic setup reconciles installed profiles and removes their guard references
before uninstalling the source.
