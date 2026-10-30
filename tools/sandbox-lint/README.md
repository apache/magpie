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
    - [Codex guard ownership](#codex-guard-ownership)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `sandbox-lint`

**Capability:** substrate:sandbox

**Harness:** Claude Code, Codex, Cursor, Antigravity, OpenCode, Kiro, Grok

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
issue` mutations) must `prompt`, the `gh api` passthrough must `prompt`
or be `forbidden`, `gh auth token` and `gh auth refresh` must be
`forbidden`, at least one scoped read-only `allow` rule must exist, no
`allow` rule may end in a mutation verb (`merge`, `delete`, `push`, …),
and `gh release download` must not be unconditionally allowed. Invariants only — adopters may keep unrelated Codex
configuration in the same files.

```bash
uv run --project tools/sandbox-lint sandbox-lint --codex .codex
```

**Antigravity profile.** `--antigravity <profile>` checks a user-scope Antigravity profile: the terminal sandbox, the approval mode, workspace-only file access, wildcard allow grants, and a single `--antigravity` guard registration.
The required ask and deny rules are derived from the Claude Code baseline in [`expected.json`](expected.json), so the two profiles cannot drift apart.
Pass the shipped template directory, or the user's live `settings.json` together with the hooks file that registers the guard:

```bash
uv run --project tools/sandbox-lint sandbox-lint --antigravity tools/agent-isolation/antigravity
uv run --project tools/sandbox-lint sandbox-lint \
  --antigravity ~/.gemini/antigravity-cli/settings.json \
  --antigravity-hooks ~/.gemini/config/hooks.json
```

These are static checks; the account's permission preset and live enforcement require [runtime verification](../../docs/adapters/antigravity.md#verify).

**Harnesses without a dedicated config profile (Cursor, Grok, …).** `--any-harness`
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
   - When a `Bash(...)` permission rule or a `sandbox.excludedCommands`
     entry names a vetted-op dispatcher (the defensive `Edit` deny rules
     alone do not count), the read dispatcher never prompts:
     `permissions.allow` carries `vetted-op-read` for both launchers
     (`uv run --project`, `uvx --from`) on the
     `~/.claude/magpie/vetted-ops` base, no `permissions.ask` rule
     matches a `vetted-op-read` command (matched as a pattern, so a
     broad `Bash(uvx *)` counts),
     `permissions.blockReadsOutsideWorkingDirectories` is not `true`,
     and `permissions.deny` carries the three vetted-ops `Edit`
     tamper-protection rules. See
     [Read-only vetted ops never prompt](../../docs/setup/secure-agent-setup.md#read-only-vetted-ops-never-prompt).
   - `sandbox.network.allowUnixSockets` contains no entry that names a
     container daemon socket (`docker.sock`, `podman.sock`, or anything
     ending in `-api.sock`, matched case-insensitively) unless it sits in the
     container gateway's run directory — `.apache-magpie-local/run` in a
     project that adopted Magpie, `<git-common-dir>/apache-magpie/run/<worktree-id>` in
     one that did not — see [Residual risk](#residual-risk) for
     the one case this cannot fully verify.
   - When `sandbox.network.allowAllUnixSockets` is `true`,
     `sandbox.filesystem.denyRead` hides the host sockets it would
     otherwise open to every sandboxed command: an entry for, or a
     directory above, each of `/run/docker.sock`, `/var/run/docker.sock`,
     `/run/docker-cli.sock`, `/run/podman`, `/run/user/<uid>` (the current
     user's uid, or a glob matching it), `/run/dbus`, `/tmp/.X11-unix`,
     `/run/WSL` and `/mnt/wslg`. Claude Code skips a `denyRead` path the
     host lacks, so the full list is safe on every host. See
     [Linux needs `allowAllUnixSockets`](../../docs/setup/secure-agent-setup.md#linux-needs-allowallunixsockets).
   - No `sandbox.filesystem.allowRead` entry is a strict parent of an
     `allowWrite` entry unless the parent is itself writable: bubblewrap
     then mounts the write path read-only and every Bash call fails. The
     trap was observed under `denyRead: ["~/"]`; the check applies
     everywhere, failing closed (see
     [Every Bash call fails with `bwrap: Can't create file`](../../docs/setup/sandbox-troubleshooting.md#every-bash-call-fails-with-bwrap-cant-create-file--read-only-file-system)).
   - No setting switches a control off wholesale, in any layer (the
     committed file, the local template, or a contributor's own
     `.claude/settings.local.json`): no `sandbox.excludedCommands` entry,
     and no `Bash(...)` allow, whose command is `*`, starts with a shell or
     interpreter by name or path (`bash`, `/bin/sh`, `env`, `python3`, … —
     `ANY_COMMAND_LAUNCHERS`, plus versioned interpreters such as
     `python3.12`), or is a package runner not pinned to a path (`uv run`
     without `--project`, `uv tool run`, `uvx` without `--from`, `npx`,
     `pipx run`, or any `npm`/`pnpm`/`yarn`/`pipx` subcommand but the
     read-only ones). Leading `NAME=value` assignments are skipped first. Only
     a runner pinned to an absolute or `~/` path outside the checkout, every
     `allowWrite` directory, every working directory and the temp directories
     counts as pinned; the same
     goes for a command word that is a path to a script (`./scripts/run.sh *`,
     `~/.cache/x.sh *` fail). A pinned runner is judged by the command it runs, so
     `uv run --project ~/x python *` and `uv run --project . anything *` both
     fail; every other `uv` subcommand (`sync`, `lock`, `pip`, `build`) counts
     too, since each can run a project's build backend. No bare `Bash` allow; no `permissions.defaultMode: bypassPermissions`,
     and no `*` in `sandbox.network.allowedDomains`.
   - Every `sandbox.excludedCommands` entry, in any layer, is on the
     exclusion allowlist (`EXCLUDED_COMMAND_ALLOWLIST`: `gh *`, `roborev *`,
     the four vetted-ops forms, the adversarial-review runner and
     `~/.claude/scripts/magpie-run-evals.sh *`) or narrows one of them
     (`gh auth *`, `gh`). The shape check above cannot recognise every
     command that runs its arguments (`find -exec`, `git -c`, `make`), and an
     excluded command runs outside the sandbox, so exclusions are an
     allowlist, not a denylist. A project that needs another exclusion lists
     it, one per line (`#` comments), in
     `.apache-magpie-overrides/sandbox-lint/excluded-commands.txt` under its
     root; such an entry still has to pass the shape check, so it cannot add
     a shell or an unpinned runner.
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

Run from the repository root, with `--project` rather than `--directory` —
`--directory` changes the process's working directory before it runs, so the
tool would then look for `.claude/settings.json` inside
`tools/sandbox-lint/` instead of at the repository root; `--project` only
tells `uv` where to find this tool's `pyproject.toml` and leaves the working
directory alone:

```sh
uv run --project tools/sandbox-lint --group dev sandbox-lint
```

Run with explicit paths (useful for tests):

```sh
uv run --project tools/sandbox-lint --group dev sandbox-lint \
  --settings .claude/settings.json \
  --expected tools/sandbox-lint/expected.json
```

Exit code is `0` on a clean pass, `1` on any invariant violation or
baseline drift.

## Harness-neutral posture check (any runtime)

For runtimes that do not expose a per-harness sandbox configuration file
(Cursor, Grok, and any other agent harness not listed under
`--settings`, `--opencode`, `--kiro`, `--codex`, or `--antigravity`), the security posture
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

Where the project ships a local settings template
(`tools/agent-isolation/claude-settings.local.template.json`, found under the
project root of the `--settings` file, or passed with `--local-template`), the
lint merges it over `.claude/settings.json` the way Claude Code layers
`.claude/settings.local.json`, compares the merge with the baseline, and
enforces the split: every `deny` and `ask` stays in the committed file, its only
`allow` entries are derived MCP tools and the `vetted-op-read` pair, and the
template neither adds MCP allows nor overrides a value the committed file sets.

Any legitimate edit to `.claude/settings.json` or the template must be paired with
the same edit to `tools/sandbox-lint/expected.json` in the same PR.
This is the explicit acknowledgement that mitigation M.29 requires:
two files, two edits, one review surface. The lint refuses to pass
if the two diverge.

## Residual risk

The wholesale-weakening check (`_runs_anything`) recognises *shapes* of rule
that run arbitrary code: shells and interpreters, globbed command words, and
package runners not pinned to a path. It cannot prove an arbitrary rule safe.
For `excludedCommands` the allowlist closes that gap, except for what a
project adds to its own extension file. For `Bash(...)` allows there is no
allowlist (approving a tool such as `zizmor *` without a prompt is
legitimate), so a tool that executes its arguments and is not on the list
would pass. Review new `Bash(...)` allows and extension entries on their
merits; the check is a backstop, not a substitute for that review.

A pinned runner is only as safe as the files it runs, and the check looks at
the pin's source path alone. The writable set it uses is `allowWrite`, the
working directories (`permissions.additionalDirectories`, which the sandbox
also makes writable), the checkout and the temp directories; a working
directory that covers the vetted-ops checkout fails on its own. It does not
cover the environment uv builds from a pin, which lives in the writable uv
cache (`~/.cache/uv/`) or the project's `.venv`. An agent that edits it can
change what an excluded vetted-ops command runs outside the sandbox.

A maintainer running an agent locally can edit `.claude/settings.json`
to weaken the sandbox without ever opening a PR. This lint catches
the *shipped* configuration but not local overrides during a single
agent run. The companion threat-model document records this under
section *X3, Sandbox bypass via developer override* and *Residual
risk #4*; consult that document once it lands on `main`.

The container-daemon-socket check in `check_invariants` accepts a
`project_root` argument to anchor its run-directory
exemption: an `allowUnixSockets` entry is exempt only when it resolves to
exactly `<project_root>/.apache-magpie-local/run/<name>` or
`<git-common-dir>/apache-magpie/run/<worktree-id>/<name>`, where the git common directory
is read from `<project_root>/.git` (the main checkout's `.git` for a linked
worktree). The CLI entry
point always infers `project_root` from `--settings` (when the path ends
in `.claude/settings.json`) and passes it, so `sandbox-lint` itself is not
exposed to the gap below. A caller that invokes `check_invariants` directly
without a `project_root` — including this lint's own invariant self-check
on a `--settings` path that does not sit under a `.claude/` directory —
falls back to an unanchored suffix match on the parent directory string,
under which a decoy path such as `/tmp/evil/.apache-magpie-local/run/podman.sock`
or `/tmp/evil/apache-magpie/run/main/podman.sock` is indistinguishable from a legitimate project-scoped socket, since both
end in the same suffix.

### Codex guard ownership

`sandbox-lint --codex .codex` requires a synchronous project `PreToolUse` guard and checks that the referenced engine exists in the framework or `.apache-magpie/` snapshot.
For a guard owned by the installed `magpie-agent-guard` plugin, use `--guard-from-plugin` with `--codex` and omit the duplicate project hook.
That mode checks sandbox and native rule invariants but reports plugin registration and trust as uninspected; verify both in Codex’s `/hooks` browser.
It still rejects a profile that explicitly disables hooks.
