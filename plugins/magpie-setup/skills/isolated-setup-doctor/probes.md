<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# What each probe result means

Read from `SKILL.md` § *The probes* when a probe prints any line other than ✓.

## Probe 1 — SSH agent / Yubikey reachable

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ N identities listed` | Pass | `ssh-add -l` returned the key list. |
| `✓ agent reachable, no identities` | Pass | `ssh-add -l` returned rc=1 (the documented "no keys" exit). |
| `✗ socket not stat-able` | Fail | Sandbox blocks `stat(2)` on the socket file. |
| `✗ agent unreachable` | Fail | Sandbox blocks `connect(2)` to the socket. |
| `⊘ SSH_AUTH_SOCK not set` | Skip | Either the user does not run `ssh-agent`, or `claude-iso`'s env whitelist dropped it (separate bug — verify). |

## Probe 2 — Localhost port bind

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ bound + loopback GET → HTTP 200` | Pass | Both bind and loopback HTTP work. |
| `✗ bind: [Errno 1] Operation not permitted` | Fail | The sandbox refuses listening sockets outright; `sandbox.network.allowLocalBinding` is unset. Fails before any egress rule is consulted, so `allowedDomains` changes do not help. |
| `✗ bind: ...` (other errno) | Fail | The sandbox blocks `bind(2)` on `127.0.0.1` for another reason. Rare; report the literal error. |
| `✗ bind ok, loopback GET: ...` | Fail | Bind works but the sandbox egress proxy refuses `127.0.0.1` as a destination. Common shape. |

## Probe 3 — Podman / Docker through the container gateway

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ <rt> reaches the container gateway at <sock>` | Pass | CLI → gateway → daemon all answer. |
| `✗ … unset — gateway not wired into settings` | Fail | The reference `env` block is missing from project settings. |
| `✗ gateway socket missing` | Fail | The `SessionStart` hook did not start the gateway, or it exited and no `PreToolUse` `ensure` hook started it again before the probe's container command (check 12a of `setup-isolated-setup-verify` flags a missing one); check `container-gateway.log` in the gateway's run directory — `<project>/.apache-magpie-local/run/` when adopted, else `<git-common-dir>/apache-magpie/run/<worktree-id>/`. |
| `✗ gateway status refused the run directory` | Fail | `status` exited 2 without a report: a run-directory component is a symlink or has the wrong owner, type or mode. Inspect the run directory from outside the sandbox; do not point the CLI around it. |
| `✗ gateway status unavailable` | Fail | The probe could not get a report from `status`: no gateway source was found (install the operator copy, install Step L.1), the operator copy is not readable inside the sandbox (`gateway source at … is not readable`: the `allowRead` grant in the project's gateway wiring is missing), or `status` exited without one (`rc=N`; typically a `python3` on `PATH` too old to import the gateway). The socket may still work, but nothing confirms it is the gateway's. |
| `✗ gateway running without a <rt> backend` | Fail | `status` reports the gateway up but `serving` does not list this CLI's backend — the Podman machine or Docker daemon behind it is not running. Start it from outside the sandbox, then restart the gateway. |
| `✗ connect … denied` | Fail | The gateway socket is not in `sandbox.network.allowUnixSockets`. |
| `✗ gateway up, backend down` | Fail | Podman machine / Docker not running on the host; start it from your own terminal. |
| `✗ no response in 15s — <rt> info hung` | Fail | `_probe_timeout` killed a stalled `<rt> info` call; the backend daemon behind the gateway is likely wedged — restart it from outside the sandbox. |
| `⊘ <rt> not on PATH` | Skip | Runtime not installed; not a sandbox restriction. |

## Probe 4 — Per-project scratch directory (`TMPDIR`)

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ per-project + writable` | Pass | `TMPDIR` resolves under this project's path slug and accepts writes. |
| `✓ writable; shared session root` | Pass | The expected value on current Claude Code. Every project on the machine shares this directory, so write through the per-session scratchpad beneath it, or use unique filenames — but there is nothing to fix. |
| `✗ TMPDIR not set` | Fail | Tooling falls back to `/tmp`, which is read-only inside the sandbox. |
| `✗ directory missing` | Fail | `TMPDIR` names a path nothing has created yet. |
| `✗ not writable inside sandbox` | Fail | `TMPDIR` points outside `sandbox.filesystem.allowWrite`. |

## Probe 5 — Signing key readable (`gpg.format=ssh`)

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ readable inside sandbox` | Pass | `ssh-keygen` will be able to open the public key. |
| `✓ literal key` | Pass | `user.signingkey` holds the key text itself; no file is involved. |
| `✗ not readable inside sandbox` | Fail | The sandbox's `~/.ssh/` read deny covers the public key; add that one file to `allowRead`. |
| `⊘ gpg.format is not ssh` | Skip | Signing goes through gpg (or is off); the agent-socket rules behind Probe 1 are what matter. |
| `⊘ user.signingkey unset` | Skip | Misconfigured signing, not a sandbox problem — mention it, do not fail the probe. |
| `signing-program → ✓` | Pass | git's signing program (the touch overlay's `gpg-touch-wrap-*` wrapper, or whatever `gpg.ssh.program` / `gpg.program` names) can be started from inside the sandbox. Nothing printed when neither key is set: git uses its default `ssh-keygen` / `gpg` from `PATH`. |
| `signing-program → ✗` | Fail | The program git is configured to sign with is read-denied inside the sandbox — for the overlay wrapper, `~/.claude/scripts/` is. Every sandboxed signed commit fails at once with `cannot exec`; add the wrapper's two files to `allowRead`. |

## Probe 6 — `gh` runs outside the sandbox

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ gh works inside the sandbox` | Pass | Platform lets `gh` verify TLS and read its token inside the sandbox (typical on Linux). |
| `✓ … "gh *" is in excludedCommands` | Pass | The known macOS shape, and the framework's exclusion is present. Calls still fail if they are not `cd`/`gh`-only invocations — see the catalog entry. |
| `✗ … NOT found in excludedCommands` | Fail | `gh` cannot work inside the sandbox on this machine and nothing runs it outside. |
| `⚠ gh failed for another reason` | Warn | Not the catalogued shape (network down, not logged in, …); inspect the message. |
| `⚠ catch-all "Bash(gh *)" in permissions.ask` | Warn | Ask beats allow regardless of specificity, so this rule prompts on every read-only `gh` call. Replace it with the explicit write-subcommand list from the reference `.claude/settings.json`. Extra line, printed after the main result. |
| `⊘ gh not on PATH` | Skip | `gh` not installed; not a sandbox restriction. |

`~/.claude/settings.json` is usually unreadable from inside the sandbox, so the exclusion check may see only the project-scope files.
If the user keeps the exclusion at user scope, a ✗ here is a false alarm; say so when reporting.

## Probe 7 — `prek` and `uv` usable inside the sandbox

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ (found: …; ~/.cache writable)` | Pass | `prek` / `uv` run inside the sandbox and can write their caches. |
| `✗ (found: …; ~/.cache not writable …)` | Fail | The tools start but cannot write their cache or state. |
| `⚠ (… not found; ~/.local/bin is not in … settings.local.json)` | Warn | The grant is missing; the tools are most likely installed but hidden. |
| `⊘ (… not found; ~/.local/bin is granted …)` | Skip | The grant is present and neither tool is installed there; not a sandbox restriction. |

## Probe 8 — Global git hook dir readable (whole-user scope)

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ (… readable; hooks visible: …)` | Pass | Sandboxed git runs the listed hooks. |
| `✗ (core.hooksPath … not readable inside sandbox …)` | Fail | The hook dir is hidden; every sandboxed commit skips every hook. |
| `✗ (… readable, but not the target of: …)` | Fail | The dir is visible but a hook's symlink target is not — typically hooks symlinked from a sync repo the sandbox does not grant. |
| `⚠ (… holds none of pre-commit, commit-msg, pre-push, post-checkout)` | Warn | `core.hooksPath` is set to a dir with none of the common hooks; check it is the intended one. |
| `⊘ (no global core.hooksPath …)` | Skip | Per-project scope: hooks live in each repo's `.git/hooks`, inside the project root. |

## Probe 9 — Working directories under the read block

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✗ … is a working directory overlapping …` | Fail | `$HOME/.claude/magpie`, a directory inside it, or a parent of it is listed, usually by an older `sandbox-add-project-root.sh`; re-run the updated script with `--all-worktrees` to remove it. |
| `✓ … is a working directory` | Pass | The resolved scratch root is listed (normally in `.claude/settings.local.json`, written by `sandbox-add-project-root.sh`). |
| `⚠ not a working directory: …` | Warn | The scratch root is missing; reads under it prompt. |
| `⚠ … the glob entry … is never matched` | Warn | A glob such as `/tmp/claude-*` is listed as a working directory but does not match; replace it with the resolved path. |
| `⊘ … blockReadsOutsideWorkingDirectories is off` | Skip | No read block, so nothing prompts. |
| `⊘ HOME is not set` | Skip | The paths cannot be resolved; nothing to compare. |
| `⊘ … user-scope settings unreadable from the sandbox` | Skip | The entries are missing from the readable project files, but the read block is usually set in user scope, which the sandbox cannot read; `setup-isolated-setup-verify` check 15 reads it from outside the sandbox. |
