<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`sandbox-lint`](#sandbox-lint)
  - [Prerequisites](#prerequisites)
  - [What it checks](#what-it-checks)
  - [How to use](#how-to-use)
  - [Harness-neutral posture check (any runtime)](#harness-neutral-posture-check-any-runtime)
  - [CI wiring](#ci-wiring)
  - [Updating the baseline](#updating-the-baseline)
  - [Residual risk](#residual-risk)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `sandbox-lint`

**Capability:** substrate:sandbox

**Harness:** Claude Code, Codex, Cursor, Gemini CLI, OpenCode, Kiro

Lints `.claude/settings.json` against the shipped baseline at
`tools/sandbox-lint/expected.json`, and against the security
invariants documented in `docs/security/threat-model.md`
(mitigation **M.29**). The threat-model document lands in a
companion PR; the lint stands on its own and runs immediately on
merge.

**OpenCode.** `--opencode opencode.json` lints the other harness's
security config. OpenCode has no `sandbox.filesystem` allow/deny model
(its filesystem isolation comes from the OS-level sandbox of the
secure-agent setup), so there is no baseline to diff — instead the lint
asserts **invariants on the `permission` policy**
([OpenCode permissions](https://opencode.ai/docs/permissions/)): the
policy must not be a blanket `"allow"`, `permission.bash` must not default
to `"allow"`, no rule may auto-approve a dangerous command family
(`git push`, `sudo`, `curl`/`wget`, `rm -rf`, cloud CLIs, `kubectl`,
`docker run`, `ssh`, interpreters, …) via last-match-wins evaluation, and
`webfetch` / `external_directory` must not be blanket-`"allow"`.

```bash
uv run --project tools/sandbox-lint sandbox-lint --opencode opencode.json
```

**Kiro.** `--kiro .kiro/agents/<name>.json` lints a Kiro CLI agent
config. Kiro's shell posture is an allowlist/denylist rather than a
per-command decision map
([Kiro shell tool](https://kiro.dev/docs/cli/reference/built-in-tools#execute-shell-commands)):
`allowedCommands` / `deniedCommands` are full-string-anchored regex,
deny is evaluated before allow, `denyByDefault` is the native
allowlist-safe posture, and Kiro's default (no config) is to prompt —
so, unlike OpenCode, a *missing* policy is not flagged. The invariants:
the shell tool (`shell` / `execute_bash` / `*` / `@builtin`) must not be
in `allowedTools` (that auto-approves every shell command and overrides
`toolsSettings`), no `allowedCommands` regex may auto-approve a dangerous
family (and stay unblocked by `deniedCommands`), `aws` / `web_fetch` must
not be blanket-allowed in `allowedTools`, and `web_fetch.trusted` must
not be a blanket `.*`.

```bash
uv run --project tools/sandbox-lint sandbox-lint --kiro .kiro/agents/<name>.json
```

**Codex.** `--codex .codex` validates the committed project profile:
`config.toml` and `rules/magpie.rules`. It requires the `workspace-write`
sandbox with workspace network access disabled, `on-request` approvals
(Codex's native per-action human confirmation), and representative
exec-policy coverage — known remote mutations (`git push`, `gh pr`/`gh
issue` mutations) must `prompt`, `gh auth token` must be `forbidden`, at
least one scoped read-only `allow` rule must exist, and `gh release
download` must not be unconditionally allowed. Invariants only — adopters
may keep unrelated Codex configuration in the same files.

```bash
uv run --project tools/sandbox-lint sandbox-lint --codex .codex
```

**Any other harness (Cursor, Gemini CLI, …).** `--any-harness`
validates the harness-neutral OS-level security posture: checks that the
two enforcement components shared across all runtimes —
`tools/agent-isolation/agent-iso.sh` (layer 0, clean-env credential strip)
and `tools/agent-guard/` dispatch core (layer 3, harness-neutral `--exec`
command gating) — are present in the framework tree. Runtimes without a
dedicated `settings.json` or `opencode.json` get the same enforcement
posture through these two OS-level layers rather than through a
harness-specific config file.

```bash
uv run --project tools/sandbox-lint sandbox-lint --any-harness
# or with an explicit framework root:
uv run --project tools/sandbox-lint sandbox-lint --any-harness /path/to/magpie
```

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv` (stdlib only, no third-party deps).
- **CLIs:** None beyond the runtime.
- **Credentials / auth:** None.
- **Network:** Runs fully offline/local — it only reads local JSON, TOML, and rules files.

## What it checks

1. **Baseline parity.** Every key/value in the live settings file
   must match the baseline. Lists tagged as set-typed (`denyRead`,
   `allowRead`, `allowWrite`, `allowedDomains`, `excludedCommands`,
   `deny`, `ask`) are
   compared as sets so a re-order does not trip the lint, but every
   addition or removal does. Any drift fails CI.
2. **Hard invariants.** Independent of the baseline, the live
   settings must satisfy the security boundaries the threat model
   commits to:
   - `sandbox.enabled` is `true`.
   - `sandbox.filesystem.denyRead` contains `~/`.
   - `sandbox.filesystem.allowRead` contains no credential or root
     paths (`~/.aws`, `~/.ssh`, `~/.netrc`, `~/.docker`, `~/.kube`,
     `~/.azure`, `~/.config/gcloud`, `/`, `~/`).
   - `sandbox.filesystem.allowWrite` is a subset of `allowRead` and
     contains no credential, config-root, or homedir-root path.
   - `permissions.deny` contains the verbatim entries listed in
     [`src/sandbox_lint/__init__.py`](src/sandbox_lint/__init__.py)
     (`REQUIRED_PERMISSIONS_DENY`).
3. **Baseline self-check.** The same invariants are applied to
   `expected.json` itself, so a PR cannot weaken the baseline in
   lockstep with the live settings without the lint catching the
   underlying boundary violation.
4. **Codex profile invariants.** The dedicated `--codex` mode validates
   the sandbox mode, workspace network access, approval policy, and
   representative exec-policy rule coverage as one contract. It validates
   invariants rather than byte-for-byte equality, so adopters may retain
   unrelated Codex configuration.

## How to use

Run from the repository root:

```sh
uv run --directory tools/sandbox-lint --group dev sandbox-lint
```

Run with explicit paths (useful for tests):

```sh
uv run --directory tools/sandbox-lint --group dev sandbox-lint \
  --settings .claude/settings.json \
  --expected tools/sandbox-lint/expected.json
```

Exit code is `0` on a clean pass, `1` on any invariant violation or
baseline drift.

## Harness-neutral posture check (any runtime)

For runtimes that do not expose a per-harness sandbox configuration file
(Cursor, Gemini CLI, and any other agent runtime not listed under
`--settings`, `--opencode`, `--kiro`, or `--codex`), the security posture
is enforced at the OS level by two harness-agnostic components:

Layer numbers follow the
[RFC-AI-0002](https://magpie.apache.org/docs/rfcs/rfc-ai-0002/) four-layer model
(Layer 0 clean-env, Layer 1 filesystem sandbox, Layer 2 tool permissions, Layer
3 forced confirmation). This presence check covers the two layers that need no
per-harness `settings.json`:

| Layer | Component | Purpose |
|---|---|---|
| Layer 0 (clean-env) | `tools/agent-isolation/agent-iso.sh` | Strips credential-shaped env vars (`GH_TOKEN`, `AWS_*`, `ANTHROPIC_API_KEY`, …) before exec, so even a fully sandboxed session cannot exfiltrate secrets via the environment. Made harness-agnostic (`agent-iso <cli>`) by `harness-posture-portability`. |
| Layer 3 (forced confirmation / action guard) | `tools/agent-guard/` dispatch core | The harness-neutral equivalent of Claude Code's `permissions.ask`. Inspects every shell command before execution and denies the ones that break a hard framework rule (`git push`, wrong commit trailer, premature `--ready-for-review`, …). The `--exec` path (added by `harness-guard-exec-mode`) lets any harness or shell wrapper enforce these rules without a harness-specific hook adapter. |

`sandbox-lint --any-harness [FRAMEWORK_ROOT]` checks that both components
are present. `FRAMEWORK_ROOT` is auto-detected by walking up from CWD: the
nearest ancestor that either contains `tools/agent-isolation/` directly (the
framework tree) or ships the installed snapshot at
`.apache-magpie/tools/agent-isolation/` (an adopter repo).

```bash
# From an adopter repo root — the .apache-magpie/ snapshot is auto-detected:
uv run --project tools/sandbox-lint sandbox-lint --any-harness

# From the Magpie framework tree itself:
uv run --project tools/sandbox-lint sandbox-lint --any-harness

# Or point at an explicit framework root:
uv run --project tools/sandbox-lint sandbox-lint --any-harness /path/to/magpie
```

Exit code is `0` when both components are present, `1` when any are
missing. A `0` confirms the enforcement components are **present**, not that a
harness is actively wired to them (see Scope below). The output identifies which
layer is missing and points to the relevant setup documentation.

**Scope.** This check validates the *presence* of the enforcement components,
not their live runtime behaviour. To probe whether the OS sandbox is
actually active in a running agent session (SSH-agent reachability,
localhost port binding, docker/podman socket), use
[`setup-isolated-setup-doctor`](../../skills/setup-isolated-setup-doctor/SKILL.md).

## CI wiring

The lint runs in two places:

- The
  [`sandbox-lint`](../../.github/workflows/sandbox-lint.yml)
  GitHub Actions workflow, on every PR that touches
  `.claude/settings.json`, the baseline, or the lint code itself.
- The repository's `prek` config
  ([`.pre-commit-config.yaml`](../../.pre-commit-config.yaml)) runs
  `pytest`, `ruff check`, `ruff format --check`, and `mypy` against
  this project, so contributors hit the same checks locally.

## Updating the baseline

Any legitimate edit to `.claude/settings.json` must be paired with
the same edit to `tools/sandbox-lint/expected.json` in the same PR.
This is the explicit acknowledgement that mitigation M.29 requires:
two files, two edits, one review surface. The lint refuses to pass
if the two diverge.

## Residual risk

A maintainer running an agent locally can edit `.claude/settings.json`
to weaken the sandbox without ever opening a PR. This lint catches
the *shipped* configuration but not local overrides during a single
agent run. The companion threat-model document records this under
section *X3, Sandbox bypass via developer override* and *Residual
risk #4*; consult that document once it lands on `main`.
