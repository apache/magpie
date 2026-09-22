---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-setup-isolated-setup-doctor
family: setup
mode: Meta
description: >-
  Probe the secure-agent setup for restrictions that block legitimate
  work — SSH agent reachability, port binding, containers, the scratch
  directory, the signing key, `gh` outside the sandbox. Names the
  troubleshooting entry and settings fix for each. Read-only.
when_to_use: >-
  When the user says "doctor my sandbox", "why is the sandbox blocking
  X", or reports a failure that smells sandbox-shaped — agent
  unreachable, socket errors, permission errors on a port. Also worth
  running after an agent harness upgrade, since the sandbox profile
  moves.
capability:
  - capability:platform
  - capability:reassess
surface_hash: sha256:42ee88aec8f2e3ad
license: Apache-2.0
---

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> → adopting project's `.apache-magpie/` directory -->

# setup-isolated-setup-doctor

## Runtime routing (run before the Claude-specific probes)

Use the operator's explicitly requested runtime when supplied; otherwise use the active session's runtime.
An installed executable or configuration directory alone does not select a runtime.
For the routing below, treat that selection as the active harness.

When the active harness is Codex, first require the static verification in
[docs/adapters/codex.md](../../../../docs/adapters/codex.md#verify), then run the
shared live environment probes inside the active Codex sandbox. Attribute
failures separately to native sandbox/network denial, approval policy, or
the POSIX agent-iso layer. Do not prescribe a `.claude` settings change for
a Codex failure. Then stop before the Claude-specific branch below.

When the selected runtime is Gemini CLI, follow
[docs/adapters/gemini.md](../../../../docs/adapters/gemini.md#doctor): verify the profile first, then diagnose the actual tool result in the active Gemini session.
Distinguish policy refusal, sandbox expansion, hook or trust failures, and wrapper or authentication problems.
Do not require Claude configuration or prescribe Claude settings changes; then stop before the Claude-specific probes below.

When the harness is Claude Code, continue below. If the harness cannot be
determined, ask once.

The **diagnostic** layer over the secure agent setup.
[`verify`](../isolated-setup-verify/SKILL.md) asks whether the setup is
*installed* right — static checks that catch drift and missing pieces.
This skill asks whether common workflows are *functionally blocked* by
the sandbox as configured, which catches over-restrictive allowlists.
([`install`](../isolated-setup-install/SKILL.md) puts it in place;
[`update`](../isolated-setup-update/SKILL.md) reports framework drift.)

Run `verify` first when the install itself is in doubt — fresh machine,
recent upgrade, sandbox-state surprise. Run `doctor` when the install is
known good and a workflow fails in a sandbox-shaped way: agent
unreachable, socket error, port permission error.

Every probe maps to a numbered entry in
[`docs/setup/sandbox-troubleshooting.md`](../../../../docs/setup/sandbox-troubleshooting.md);
the doctor's job is to identify *which* entry applies right now,
not to re-explain the remediation. If a fail surfaces a failure
mode not catalogued there, propose appending a new entry per the
catalog's *Adding a new entry* section.

## Golden rules

- **Read-only.** Each probe runs a small, deterministic,
  side-effect-free check. The skill never edits any settings
  file, never runs a command with `dangerouslyDisableSandbox`,
  never installs anything. If a check fails, surface the failure
  and point at the catalog entry; do not auto-fix.
- **Run every probe, even on early failure.** Do not stop at the
  first ✗. The value of the report is in the full picture — a
  user may have one of six independent restrictions, or all
  six, and discovering them one re-run at a time is annoying.
- **Distinguish ✗ (failing) from ⊘ (not applicable).** ✗ means
  the probe ran and the sandbox blocked it. ⊘ means the probe
  was skipped because the prerequisite is absent (e.g. no
  `docker` / `podman` on `PATH` → docker probe ⊘, not ✗).
- **Surface evidence.** Each report line names the probe command,
  the exit code, and the relevant stderr snippet. "Looks
  blocked" is not a useful report; "ssh-add -l → rc=2 →
  `Could not open a connection to your authentication agent`" is.
- **Map each ✗ to a catalog entry.** The fail report includes a
  direct link to the matching section of
  [`docs/setup/sandbox-troubleshooting.md`](../../../../docs/setup/sandbox-troubleshooting.md).
  Do not paraphrase the remediation — the catalog is the single
  source of truth.

## The 6 probes

The current set covers the six failure modes the catalog
documents. New probes are added when new entries land in the
catalog; the two stay in lock-step.

### Probe 1 — SSH agent / Yubikey reachable

Tests whether `ssh-agent` is reachable from inside the sandbox.
Failure modes: `SSH_AUTH_SOCK` is passed through `claude-iso`'s
env whitelist but the socket file is not in
`sandbox.filesystem.allowRead`, so the agent's `ssh` /
`git push` subprocesses cannot even `stat(2)` it; or — on macOS —
the file is readable but its path is missing from
`sandbox.network.allowUnixSockets`, so `connect(2)` is denied and
the agent reports as unreachable while the socket is plainly
there. The second is the one a signed commit hits as
`No private key found for public key`.

**Command:**

```bash
bash <skill-dir>/scripts/probe-1-ssh-agent.sh
```

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ N identities listed` | Pass | `ssh-add -l` returned the key list. |
| `✓ agent reachable, no identities` | Pass | `ssh-add -l` returned rc=1 (the documented "no keys" exit). |
| `✗ socket not stat-able` | Fail | Sandbox blocks `stat(2)` on the socket file. |
| `✗ agent unreachable` | Fail | Sandbox blocks `connect(2)` to the socket. |
| `⊘ SSH_AUTH_SOCK not set` | Skip | Either the user does not run `ssh-agent`, or `claude-iso`'s env whitelist dropped it (separate bug — verify). |

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — SSH agent / Yubikey appears unreachable from inside the sandbox](../../../../docs/setup/sandbox-troubleshooting.md#ssh-agent--yubikey-appears-unreachable-from-inside-the-sandbox).

### Probe 2 — Localhost port bind

Tests whether a process inside the sandbox can bind to a
loopback port AND then talk to itself over loopback. The
failure mode the catalog documents is the second half (egress
proxy blocks `127.0.0.1`).

**Command:**

```bash
bash <skill-dir>/scripts/probe-2-localhost-bind.sh
```

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ bound + loopback GET → HTTP 200` | Pass | Both bind and loopback HTTP work. |
| `✗ bind: [Errno 1] Operation not permitted` | Fail | The sandbox refuses listening sockets outright; `sandbox.network.allowLocalBinding` is unset. Fails before any egress rule is consulted, so `allowedDomains` changes do not help. |
| `✗ bind: ...` (other errno) | Fail | The sandbox blocks `bind(2)` on `127.0.0.1` for another reason. Rare; report the literal error. |
| `✗ bind ok, loopback GET: ...` | Fail | Bind works but the sandbox egress proxy refuses `127.0.0.1` as a destination. Common shape. |

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — Test cannot bind to a localhost port](../../../../docs/setup/sandbox-troubleshooting.md#test-cannot-bind-to-a-localhost-port).

### Probe 3 — Podman / Docker through the container gateway

Tests whether the runtime CLI can talk to the [container
gateway](../../../../tools/container-gateway/README.md), not the
real daemon socket — the sandbox never gets a route to the daemon
itself. Run for each of `podman` / `docker` that is on `PATH`; ⊘
each that is not installed (this is not a sandbox failure, just an
absent prerequisite). Each remaining check narrows down which of
the three wiring pieces (env var, running gateway, allowed socket)
is missing, in the order a fresh install would hit them.

**Command:**

```bash
bash <skill-dir>/scripts/probe-3-container-gateway.sh
```

`status_json` comes from the gateway's own read-only `status`
subcommand — the doctor may call it from inside the sandbox,
since it neither binds a socket nor touches the daemon. `gw_src`
picks the adopter's pinned snapshot
(`.apache-magpie/tools/container-gateway/src`) when present, else
the framework repo's own tree (`tools/container-gateway/src`), so
the same probe runs in both an adopter checkout and this
framework's own worktree. The `gw_state` check runs **before** the
raw socket-file test: a backend `status` does not list under
`serving` never gets a socket file in the first place, so testing
`-S "$sock"` first would misreport "gateway not running" for the
"running, but this backend's machine/daemon is down" case — the
`-S` test below is a defensive fallback for an already-serving
backend whose socket vanished mid-probe, not the primary check.

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ <rt> reaches the container gateway at <sock>` | Pass | CLI → gateway → daemon all answer. |
| `✗ … unset — gateway not wired into settings` | Fail | The reference `env` block is missing from project settings. |
| `✗ gateway socket missing` | Fail | The `SessionStart` hook did not start the gateway, or it exited; check `<project>/.apache-magpie-local/run/container-gateway.log`. |
| `✗ gateway running without a <rt> backend` | Fail | `status` reports the gateway up but `serving` does not list this CLI's backend — the Podman machine or Docker daemon behind it is not running. Start it from outside the sandbox, then restart the gateway. |
| `✗ connect … denied` | Fail | The gateway socket is not in `sandbox.network.allowUnixSockets`. |
| `✗ gateway up, backend down` | Fail | Podman machine / Docker not running on the host; start it from your own terminal. |
| `✗ no response in 15s — <rt> info hung` | Fail | `_probe_timeout` killed a stalled `<rt> info` call; the backend daemon behind the gateway is likely wedged — restart it from outside the sandbox. |
| `⊘ <rt> not on PATH` | Skip | Runtime not installed; not a sandbox restriction. |

An empty `podman machine list` from inside the sandbox is a read
denial on the machine's directory, not proof that no machine
exists — decide the machine's real state from outside the sandbox,
per the catalog entry below.

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — Docker / Podman command fails with a socket error](../../../../docs/setup/sandbox-troubleshooting.md#docker--podman-command-fails-with-a-socket-error).

### Probe 4 — Per-project scratch directory (`TMPDIR`)

Tests whether the session has a **writable** scratch directory. The
sandbox mounts the host `/tmp` read-only and punches only specific
subpaths writable, so a session whose `TMPDIR` falls back to `/tmp`
gets no scratch area at all.

`TMPDIR` landing on the shared session root rather than a
per-project directory is **not** a finding. Claude Code sets
`TMPDIR` itself when it builds the sandbox and that assignment wins
over `env.TMPDIR` from any settings file, so the shared root is the
expected value and no configuration changes it. Each session still
gets a per-project, per-session scratchpad underneath it.

**Command:**

```bash
bash <skill-dir>/scripts/probe-4-scratch-dir.sh
```

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ per-project + writable` | Pass | `TMPDIR` resolves under this project's path slug and accepts writes. |
| `✓ writable; shared session root` | Pass | The expected value on current Claude Code. Every project on the machine shares this directory, so write through the per-session scratchpad beneath it, or use unique filenames — but there is nothing to fix. |
| `✗ TMPDIR not set` | Fail | Tooling falls back to `/tmp`, which is read-only inside the sandbox. |
| `✗ directory missing` | Fail | `TMPDIR` names a path nothing has created yet. |
| `✗ not writable inside sandbox` | Fail | `TMPDIR` points outside `sandbox.filesystem.allowWrite`. |

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — Temp files fail with "Read-only file system" under `/tmp`](../../../../docs/setup/sandbox-troubleshooting.md#temp-files-fail-with-read-only-file-system-under-tmp).

Do **not** propose `env.TMPDIR` in a settings file as the fix.
Claude Code overrides it when it builds the sandbox, so the setting
is accepted and silently has no effect; the giveaway is a directory
that exists, is named exactly as configured, and stays empty. The
catalog entry above covers what is actually actionable.

### Probe 5 — Signing key readable (`gpg.format=ssh`)

Tests whether the public key git hands to `ssh-keygen -Y sign` can
be opened from inside the sandbox. Failure mode: the framework
denies `~/.ssh/` wholesale, so with `gpg.format=ssh` every signed
commit fails before the hardware key is asked for a touch — and the
touch overlay, which waits for `ssh-keygen` to block, never sees it
block.

**Command:**

```bash
bash <skill-dir>/scripts/probe-5-signing-key.sh
```

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ readable inside sandbox` | Pass | `ssh-keygen` will be able to open the public key. |
| `✓ literal key` | Pass | `user.signingkey` holds the key text itself; no file is involved. |
| `✗ not readable inside sandbox` | Fail | The sandbox's `~/.ssh/` read deny covers the public key; add that one file to `allowRead`. |
| `⊘ gpg.format is not ssh` | Skip | Signing goes through gpg (or is off); the previous entry's socket rules are what matter. |
| `⊘ user.signingkey unset` | Skip | Misconfigured signing, not a sandbox problem — mention it, do not fail the probe. |
| `signing-program → ✓` | Pass | git's signing program (the touch overlay's `gpg-touch-wrap-*` wrapper, or whatever `gpg.ssh.program` / `gpg.program` names) can be started from inside the sandbox. Nothing printed when neither key is set: git uses its default `ssh-keygen` / `gpg` from `PATH`. |
| `signing-program → ✗` | Fail | The program git is configured to sign with is read-denied inside the sandbox — for the overlay wrapper, `~/.claude/scripts/` is. Every sandboxed signed commit fails at once with `cannot exec`; add the wrapper's two files to `allowRead`. |

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — Signed commit fails before any touch when git signs with ssh](../../../../docs/setup/sandbox-troubleshooting.md#signed-commit-fails-before-any-touch-when-git-signs-with-ssh)
for the key, and
[`docs/setup/sandbox-troubleshooting.md` — Signed commit fails with "cannot exec" of the touch-overlay wrapper](../../../../docs/setup/sandbox-troubleshooting.md#signed-commit-fails-with-cannot-exec-of-the-touch-overlay-wrapper)
for the program.

### Probe 6 — `gh` runs outside the sandbox

Tests whether `gh` can reach GitHub from a sandboxed Bash call, and
if not, whether the `sandbox.excludedCommands: ["gh *"]` exclusion
that the framework reference relies on is in place. On macOS a
sandboxed `gh` cannot verify TLS or read the keychain
(`x509: OSStatus -26276` / `HTTP 401`), so the exclusion is the only
thing that makes it work — and the exclusion applies only when
every segment of a Bash invocation is `cd …` or `gh …`.

The probe deliberately runs `gh` through `sh -c` so that the
exclusion cannot apply to the probe itself: that shows what an
*un-excluded* `gh` does on this machine.

**Command:**

```bash
bash <skill-dir>/scripts/probe-6-gh-outside-sandbox.sh
```

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ gh works inside the sandbox` | Pass | Platform lets `gh` verify TLS and read its token inside the sandbox (typical on Linux). |
| `✓ … "gh *" is in excludedCommands` | Pass | The known macOS shape, and the framework's exclusion is present. Calls still fail if they are not `cd`/`gh`-only invocations — see the catalog entry. |
| `✗ … NOT found in excludedCommands` | Fail | `gh` cannot work inside the sandbox on this machine and nothing runs it outside. |
| `⚠ gh failed for another reason` | Warn | Not the catalogued shape (network down, not logged in, …); inspect the message. |
| `⚠ catch-all "Bash(gh *)" in permissions.ask` | Warn | Ask beats allow regardless of specificity, so this rule prompts on every read-only `gh` call. Replace it with the explicit write-subcommand list from the reference `.claude/settings.json`. Extra line, printed after the main result. |
| `⊘ gh not on PATH` | Skip | `gh` not installed; not a sandbox restriction. |

`~/.claude/settings.json` is usually unreadable from inside the
sandbox, so the exclusion check may only see the project-scope
files; if the user keeps the exclusion at user scope, a ✗ here is
a false alarm — say so when reporting.

Even with the exclusion present, a `gh` call is only excluded when
every part of the Bash invocation is `cd …` or `gh …`: a pipe, a
`$(…)` substitution, a loop, or any file redirection (`> file`,
even `> /dev/null`) puts it back in the sandbox. The redirection
case is a Claude Code regression tracked in
[anthropics/claude-code#95532](https://github.com/anthropics/claude-code/issues/95532);
the catalog entry shows the `gh tofile` alias that works around it.
When the user reports a `gh` failure that this probe does not
reproduce, ask for the exact command line — the shape is usually
the answer.

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — `gh` fails with TLS `OSStatus -26276` or `HTTP 401` inside the sandbox](../../../../docs/setup/sandbox-troubleshooting.md#gh-fails-with-tls-osstatus--26276-or-http-401-inside-the-sandbox).

## After the report

If every probe is ✓ or ⊘:

> All six probes pass (or are not applicable). The sandbox is
> not currently blocking the known failure modes catalogued in
> `docs/setup/sandbox-troubleshooting.md`. If you hit a different
> sandbox-shaped failure, follow the catalog's *Adding a new
> entry* section and (optionally) extend this skill with another
> probe so future runs catch the same shape automatically.

If any probe is ✗:

1. Surface every fail in one report (do not stop at the first).
2. For each fail, print the troubleshooting-doc anchor link from
   the probe's *On ✗ → remediation* row above.
3. Suggest the user open the catalog entry to read the symptom →
   root cause → fix shape, then apply the settings.json widening
   themselves. Do **not** propose to apply the widening from this
   skill — settings.json widenings are sandbox-bypass-adjacent
   and need an explicit user-driven edit.
4. After the user has applied the widening (in a separate flow),
   re-run `setup-isolated-setup-doctor` to confirm the probe now
   passes.

If a probe surfaces a fail shape not catalogued in
[`docs/setup/sandbox-troubleshooting.md`](../../../../docs/setup/sandbox-troubleshooting.md):

1. Report the fail with the literal probe command + exit code +
   stderr.
2. Suggest the user add a new entry to the catalog per its
   *Adding a new entry* section (symptom verbatim, root cause,
   fix, notes).
3. Once the catalog has the new entry, extend this skill with a
   matching probe in the same shape so the next doctor run
   catches it automatically.

## Adding a probe

When the troubleshooting catalogue grows an entry, add a matching probe:
[`scripts/README.md`](scripts/README.md).
