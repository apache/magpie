---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: isolated-setup-doctor
family: setup
mode: Meta
description: >-
  Probe the secure-agent setup for restrictions that block legitimate
  work — SSH agent reachability, port binding, containers, the scratch
  directory, the signing key, `gh` outside the sandbox, `prek` and
  `uv` inside it, the global git hook dir. Names the
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
surface_hash: sha256:cd9060f872e88f60
license: Apache-2.0
measured_tokens: 4637
---

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> → per file: the personal layer, else `.apache-magpie-overrides/` -->

# setup-isolated-setup-doctor

<!-- BEGIN MAGPIE BLOCK: sandbox-golden-rule — generated from tools/dev/blocks/sandbox-golden-rule.md -->

**Golden rule — a step the sandbox blocks becomes a vetted operation, never
a bypass.** This holds for the whole run. When anything you need to do fails
on a sandbox restriction (a blocked host or transport, a read-only path, a
denied credential or socket):

1. Never leave the sandbox for it: no sandbox-disabling flag, and no wider
   exclusion or allow rule proposed as the fix.
2. Look for a route that stays safe: a spelling the sandbox allows (fetch in
   the main checkout, rewrite history in a scratch clone), or a vetted
   operation that already covers it (`vetted-op-read`, `vetted-op`,
   `vetted-op-tracker`, `vetted-op-git`), launched with the literal `~` path.
   Publishing a change is covered end to end by `vetted-op-git`:
   `git-worktree-add`, `git-fetch`, `git-stage`, `git-commit`,
   `git-push-branch`, `git-pr-create`. Run the checks in the sandbox first
   with `vetted-op-checks` (`git-commit` refuses what they did not pass),
   and never hand those steps to the user as commands to paste.
3. If none exists, do the rest of the work, give the user the one command to
   run this time, and propose `/magpie-setup:upstream-fix` for it: a
   closed-shape vetted operation (fixed argv, validated parameters, destination
   from the approved policy, no repository code or configuration steering it,
   behind a confirmation) or a documented in-sandbox route. Opening that PR
   needs the user's go-ahead, like any other publication.

<!-- END MAGPIE BLOCK: sandbox-golden-rule -->

## Runtime routing (run before the Claude-specific probes)

Use the operator's explicitly requested runtime when supplied; otherwise use the active session's runtime.
An installed executable or configuration directory alone does not select a runtime.
For the routing below, treat that selection as the active harness.

When it is Codex, Antigravity, Goose, Pi or Copilot CLI, follow that harness's paragraph in [`runtime-routing.md`](runtime-routing.md).

When the harness is Claude Code, continue below.
If the harness cannot be determined, ask once.

This is the diagnostic layer over the secure agent setup.
[`verify`](../isolated-setup-verify/SKILL.md) checks statically that the setup is *installed* right, catching drift and missing pieces.
This skill checks whether common workflows are *functionally blocked* by the sandbox as configured, catching over-restrictive allowlists.
([`install`](../isolated-setup-install/SKILL.md) puts the setup in place; [`update`](../isolated-setup-update/SKILL.md) reports framework drift.)

Run `verify` first when the install itself is in doubt: fresh machine, recent upgrade, sandbox-state surprise.
Run `doctor` when the install is known good and a workflow fails in a sandbox-shaped way: agent unreachable, socket error, port permission error.

Every probe maps to a numbered entry in [`docs/setup/sandbox-troubleshooting.md`](../../../../docs/setup/sandbox-troubleshooting.md).
The doctor identifies *which* entry applies now; it does not re-explain the remediation.
If a fail shows a failure mode not catalogued there, propose appending a new entry per the catalog's *Adding a new entry* section.

## Golden rules

- **Read-only.** Each probe is a small, deterministic, side-effect-free check.
  The skill **never** edits a settings file, **never** runs a command with `dangerouslyDisableSandbox`, and **never** installs anything.
  If a check fails, surface it and point at the catalog entry; do not auto-fix.
- **Run every probe, even on early failure.** Do not stop at the first ✗.
  A user may have one of eight independent restrictions or all eight, and finding them one re-run at a time is annoying.
- **Distinguish ✗ (failing) from ⊘ (not applicable).** ✗ means the probe ran and the sandbox blocked it.
  ⊘ means the probe was skipped because a prerequisite is absent (e.g. no `docker` / `podman` on `PATH` → docker probe ⊘, not ✗).
- **Surface evidence.** Each report line names the probe command, the exit code, and the relevant stderr snippet.
  "Looks blocked" is not useful; "ssh-add -l → rc=2 → `Could not open a connection to your authentication agent`" is.
- **Sandbox placeholders are not files.** Inside the Claude Code sandbox a denied path that does not exist on the host can appear as a `/dev/null` bind mount: `stat -c '%F %t,%T' <path>` prints `character special file 1,3`.
  `git status` lists such placeholders as untracked (`.bash_profile`, `.claude/settings.json`, `.mcp.json`), and reading one returns nothing.
  Take the host state from git (`git ls-files <path>`, `git log -- <path>`) or from a read the user runs outside the sandbox, and never delete the placeholder.
- **Map each ✗ to a catalog entry.** The fail report links directly to the matching section of [`docs/setup/sandbox-troubleshooting.md`](../../../../docs/setup/sandbox-troubleshooting.md).
  Do not paraphrase the remediation; the catalog is the single source of truth.

## The probes

The probes cover the catalog's failure modes that a sandboxed command can detect on its own; the signing entries that need a live touch or a terminal are verified by `setup-isolated-setup-verify` check 10 instead.
New probes are added when new entries land in the catalog, so the two stay in lock-step.

### Probe 1 — SSH agent / Yubikey reachable

Tests whether `ssh-agent` is reachable from inside the sandbox.
Two failure modes:
`SSH_AUTH_SOCK` passes through `claude-iso`'s env whitelist but the socket file is not in `sandbox.filesystem.allowRead`, so the agent's `ssh` / `git push` subprocesses cannot even `stat(2)` it;
or, on macOS, the file is readable but its path is missing from `sandbox.network.allowUnixSockets`, so `connect(2)` is denied and the agent looks unreachable while the socket is plainly there.
A signed commit hits the second as `No private key found for public key`.

**Command:**

```bash
bash <skill-dir>/scripts/probe-1-ssh-agent.sh
```

On any result line other than ✓, read [Probe 1 in `probes.md`](probes.md#probe-1--ssh-agent--yubikey-reachable) for what it means before reporting it.

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — SSH agent / Yubikey appears unreachable from inside the sandbox](../../../../docs/setup/sandbox-troubleshooting.md#ssh-agent--yubikey-appears-unreachable-from-inside-the-sandbox).

### Probe 2 — Localhost port bind

Tests whether a process inside the sandbox can bind to a loopback port AND then talk to itself over loopback.
The catalog documents the second half failing (egress proxy blocks `127.0.0.1`).

**Command:**

```bash
bash <skill-dir>/scripts/probe-2-localhost-bind.sh
```

On any result line other than ✓, read [Probe 2 in `probes.md`](probes.md#probe-2--localhost-port-bind) for what it means before reporting it.

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — Test cannot bind to a localhost port](../../../../docs/setup/sandbox-troubleshooting.md#test-cannot-bind-to-a-localhost-port).

### Probe 3 — Podman / Docker through the container gateway

Tests whether the runtime CLI can talk to the [container gateway](../../../../tools/container-gateway/README.md), not the real daemon socket; the sandbox never gets a route to the daemon itself.
Run it for each of `podman` / `docker` on `PATH`; ⊘ each one not installed (an absent prerequisite, not a sandbox failure).
The remaining checks narrow down which of the three wiring pieces (env var, running gateway, allowed socket) is missing, in the order a fresh install would hit them.

**Command:**

```bash
bash <skill-dir>/scripts/probe-3-container-gateway.sh
```

On any result line other than ✓, read [Probe 3 in `probes.md`](probes.md#probe-3--podman--docker-through-the-container-gateway) for what it means before reporting it.

An empty `podman machine list` from inside the sandbox is a read denial on the machine's directory, not proof that no machine exists.
Decide the machine's real state from outside the sandbox, per the catalog entry below.

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — Docker / Podman command fails with a socket error](../../../../docs/setup/sandbox-troubleshooting.md#docker--podman-command-fails-with-a-socket-error).

### Probe 4 — Per-project scratch directory (`TMPDIR`)

Tests whether the session has a **writable** scratch directory.
The sandbox mounts the host `/tmp` read-only and makes only specific subpaths writable, so a session whose `TMPDIR` falls back to `/tmp` has no scratch area at all.

`TMPDIR` landing on the shared session root rather than a per-project directory is **not** a finding.
Claude Code sets `TMPDIR` itself when it builds the sandbox, and that wins over `env.TMPDIR` from any settings file, so the shared root is expected and no configuration changes it.
Each session still gets a per-project, per-session scratchpad beneath it.

**Command:**

```bash
bash <skill-dir>/scripts/probe-4-scratch-dir.sh
```

On any result line other than ✓, read [Probe 4 in `probes.md`](probes.md#probe-4--per-project-scratch-directory-tmpdir) for what it means before reporting it.

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — Temp files fail with "Read-only file system" under `/tmp`](../../../../docs/setup/sandbox-troubleshooting.md#temp-files-fail-with-read-only-file-system-under-tmp).

Do **not** propose `env.TMPDIR` in a settings file as the fix.
Claude Code overrides it when it builds the sandbox, so the setting is accepted and silently has no effect.
The giveaway is a directory that exists, is named exactly as configured, and stays empty.
The catalog entry above covers what is actually actionable.

### Probe 5 — Signing key readable (`gpg.format=ssh`)

Tests whether the public key git hands to `ssh-keygen -Y sign` can be opened from inside the sandbox.
Failure mode: the framework denies `~/.ssh/` wholesale, so with `gpg.format=ssh` every signed commit fails before the hardware key asks for a touch.
The touch overlay, which waits for `ssh-keygen` to block, never sees it block.

**Command:**

```bash
bash <skill-dir>/scripts/probe-5-signing-key.sh
```

On any result line other than ✓, read [Probe 5 in `probes.md`](probes.md#probe-5--signing-key-readable-gpgformatssh) for what it means before reporting it.

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — Signed commit fails before any touch when git signs with ssh](../../../../docs/setup/sandbox-troubleshooting.md#signed-commit-fails-before-any-touch-when-git-signs-with-ssh)
for the key, and
[`docs/setup/sandbox-troubleshooting.md` — Signed commit fails with "cannot exec" of the touch-overlay wrapper](../../../../docs/setup/sandbox-troubleshooting.md#signed-commit-fails-with-cannot-exec-of-the-touch-overlay-wrapper)
for the program.

### Probe 6 — `gh` runs outside the sandbox

Tests whether `gh` can reach GitHub from a sandboxed Bash call, and if not, whether the `sandbox.excludedCommands: ["gh *"]` exclusion the framework reference relies on is in place.
On macOS a sandboxed `gh` cannot verify TLS or read the keychain (`x509: OSStatus -26276` / `HTTP 401`), so only the exclusion makes it work.
The exclusion applies only when every segment of a Bash invocation is `cd …` or `gh …`.

The probe deliberately runs `gh` through `sh -c` so the exclusion cannot apply to it, showing what an *un-excluded* `gh` does on this machine.

**Command:**

```bash
bash <skill-dir>/scripts/probe-6-gh-outside-sandbox.sh
```

On any result line other than ✓, read [Probe 6 in `probes.md`](probes.md#probe-6--gh-runs-outside-the-sandbox) for what it means before reporting it.

Even with the exclusion present, a `gh` call is excluded only when every part of the Bash invocation is `cd …` or `gh …`.
A pipe, a `$(…)` substitution, a loop, or any file redirection (`> file`, even `> /dev/null`) puts it back in the sandbox.
The redirection case is a Claude Code regression tracked in [anthropics/claude-code#95532](https://github.com/anthropics/claude-code/issues/95532); the catalog entry shows the `gh tofile` alias that works around it.
When the user reports a `gh` failure this probe does not reproduce, ask for the exact command line; the shape is usually the answer.

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — `gh` fails with TLS `OSStatus -26276` or `HTTP 401` inside the sandbox](../../../../docs/setup/sandbox-troubleshooting.md#gh-fails-with-tls-osstatus--26276-or-http-401-inside-the-sandbox).

### Probe 7 — `prek` and `uv` usable inside the sandbox

Tests whether the dev tools the framework's hooks and Python tools run on are found and can write their cache from a sandboxed Bash call.
They live in `~/.local/bin`, which the harness reads only when the worktree's `.claude/settings.local.json` grants it; the committed project-scope entries are not applied.
Inside the sandbox a read-denied directory looks exactly like an absent one, so the probe reads `settings.local.json` to tell a missing grant from a tool that is not installed.

**Command:**

```bash
bash <skill-dir>/scripts/probe-7-dev-tools.sh
```

On any result line other than ✓, read [Probe 7 in `probes.md`](probes.md#probe-7--prek-and-uv-usable-inside-the-sandbox) for what it means before reporting it.

**On ✗ or ⚠ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — `prek` or `uv` not found, or cannot write its cache, inside the sandbox](../../../../docs/setup/sandbox-troubleshooting.md#prek-or-uv-not-found-or-cannot-write-its-cache-inside-the-sandbox).

### Probe 8 — Global git hook dir readable (whole-user scope)

Tests whether git run inside the sandbox can see the hooks a global `core.hooksPath` points at.
Git treats a hook it cannot see as one that does not exist, so an unreadable hook dir costs every hook — `pre-commit` and `prek` included — without an error.
Only a look from inside the sandbox shows it, which is where this probe runs.

**Command:**

```bash
bash <skill-dir>/scripts/probe-8-git-hooks.sh
```

On any result line other than ✓, read [Probe 8 in `probes.md`](probes.md#probe-8--global-git-hook-dir-readable-whole-user-scope) for what it means before reporting it.

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — Git hooks silently skipped for commits made inside the sandbox](../../../../docs/setup/sandbox-troubleshooting.md#git-hooks-silently-skipped-for-commits-made-inside-the-sandbox).

### Probe 9 — Working directories under the read block

Tests whether, with `permissions.blockReadsOutsideWorkingDirectories` on, the scratch root `/tmp/claude-<uid>` the skills read on every run is a working directory.
Without it nothing breaks, but each read there prompts, and a bulk sync multiplies that by its gatherer agents.
It also fails when `$HOME/.claude/magpie` (the fixed path the vetted-ops rules name) is one, read block or not: the sandbox makes working directories writable, and the vetted-ops commands run from there outside the sandbox.
The prompt comes before any command runs, so the [sandbox-error hint hook](../../../../docs/setup/secure-agent-setup.md#sandbox-error-hint-hook) never sees it; this probe is the only in-session pointer.
Where the vetted-ops dispatcher is used, a ✓ here is not enough: its commands spell `~` literally, which the read block cannot check, so every `vetted-op-read` call prompts while the block is on, and a background gatherer turns each prompt into a silent denial.
The setup requires the block off there ([Read-only vetted ops never prompt](../../../../docs/setup/secure-agent-setup.md#read-only-vetted-ops-never-prompt)); `setup-isolated-setup-verify` check 16 enforces it.

**Command:**

```bash
bash <skill-dir>/scripts/probe-9-working-dirs.sh
```

On any result line other than ✓, read [Probe 9 in `probes.md`](probes.md#probe-9--working-directories-under-the-read-block) for what it means before reporting it.

**On ✗ or ⚠ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — Reads of `~/.claude/magpie` or `/tmp/claude-<uid>` ask for approval every time](../../../../docs/setup/sandbox-troubleshooting.md#reads-of-claudemagpie-or-tmpclaude-uid-ask-for-approval-every-time).

## After the report

If every probe is ✓ or ⊘:

> All nine probes pass (or are not applicable). The sandbox is
> not currently blocking the known failure modes catalogued in
> `docs/setup/sandbox-troubleshooting.md`. If you hit a different
> sandbox-shaped failure, follow the catalog's *Adding a new
> entry* section and (optionally) extend this skill with another
> probe so future runs catch the same shape automatically.

If any probe is ✗:

1. Surface every fail in one report (do not stop at the first).
2. For each fail, print the troubleshooting-doc anchor link from the probe's *On ✗ → remediation* line above.
3. Suggest the user read the catalog entry's symptom → root cause → fix, then apply the settings.json widening themselves.
   Do **not** propose to apply the widening from this skill; settings.json widenings are sandbox-bypass-adjacent and need an explicit user-driven edit.
4. After the user has applied the widening (in a separate flow), re-run `setup-isolated-setup-doctor` to confirm the probe now passes.

If a probe surfaces a fail shape not catalogued in
[`docs/setup/sandbox-troubleshooting.md`](../../../../docs/setup/sandbox-troubleshooting.md):

1. Report the fail with the literal probe command + exit code + stderr.
2. Suggest the user add a new entry to the catalog per its *Adding a new entry* section (symptom verbatim, root cause, fix, notes).
3. Once the catalog has the new entry, extend this skill with a matching probe in the same shape so the next doctor run catches it automatically.

## Adding a probe

When the troubleshooting catalogue grows an entry, add a matching probe:
[`scripts/README.md`](scripts/README.md).
