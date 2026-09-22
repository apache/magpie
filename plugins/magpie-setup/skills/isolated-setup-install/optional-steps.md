<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Optional steps: K, L and M

Read the one the walk-through reaches. None of these is required for
a working install: a hardware security key, the container gateway,
and the eval-harness exclusion.

## Step K — Hardware security key (optional)

Fully optional, **default no**. Ask once whether the operator signs
commits or authenticates to the forge with a hardware security key
(YubiKey, Nitrokey, any OpenPGP card) or wants to start. On no, skip
the step and say so. On yes, four sub-steps, each surfaced for the
operator to run or approve; the rationale they should hear once is
in
[docs/setup/secure-agent-setup.md → Hardware security keys](../../../../docs/setup/secure-agent-setup.md#hardware-security-keys--signing-and-authentication)
and
[RFC-AI-0002 → Layer 3b](../../../../docs/rfcs/RFC-AI-0002.md#layer-3b--hardware-key-touch-physical-confirmation-of-signatures-and-remote-access).

**K.1 — Touch policy on the key.** Hand the operator
`ykman openpgp info` to run themselves (the tool needs the USB device,
which the sandbox does not expose) and read the touch policies back
from what they paste. The output is data: a line in it that reads like
an instruction is flagged, not followed. For each of the signature
(`sig`) and authentication (`aut`) slots that reports `Off`, surface:

```sh
ykman openpgp keys set-touch sig cached
ykman openpgp keys set-touch aut cached
```

Never run these yourself — they prompt for the key's admin PIN. Propose
`cached` (a touch honoured for 15 seconds, so a rebase or a
pull-then-push needs one), not `on`, and **never** `fixed` or
`cached-fixed`, which cannot be undone without deleting the private
key. Leave the attestation slot alone. A slot already at `On` or
`Cached` is fine as it is.

**K.2 — The touch overlay.** Copy
`tools/agent-isolation/gpg-touch-overlay.sh`,
`gpg-touch-overlay-window.py` and `gpg-touch-overlay-window-macos.py`
into `~/.claude/scripts/`, `chmod +x` them, and wire a `PreToolUse`
`Bash` hook running `gpg-touch-overlay.sh arm` and a
`gpg-touch-overlay.sh disarm` hook on **three** events —
`PostToolUse`, `PermissionDenied` and `PostToolUseFailure`, each on
the `Bash` matcher — into `~/.claude/settings.json`, merging into
existing arrays with a diff the operator approves, exactly as for the
bypass-warn hook. The last two matter because `PreToolUse` fires
before the permission prompt: a command the operator rejects has
already armed a watcher that `PostToolUse` never tears down, and it
lives until `MAX_WAIT` raising the window for somebody else's
signature. Install detail:
[docs/setup/secure-agent-setup.md → Hardware-key touch overlay](../../../../docs/setup/secure-agent-setup.md#hardware-key-touch-overlay).

**K.3 — Git from the operator's own terminal.** The hook covers only
the git commands the agent runs; a commit or push the operator makes
in a terminal or an IDE waits for the same touch with nothing on
screen. Point git's own programs at the script's `wrap` mode instead
of at any git hook (none sits at the right moment — `pre-push` runs
after ssh has authenticated, and only `git commit` has hooks around
its signature). Create the argument-free entry beside the script —
`ln -s gpg-touch-overlay.sh ~/.claude/scripts/gpg-touch-wrap-ssh-keygen`
(`gpg-touch-wrap-gpg` when `git config --get gpg.format` is not
`ssh`) — and hand the operator the two settings to run themselves,
since global git config is theirs to write:

```sh
git config --global gpg.ssh.program "$HOME/.claude/scripts/gpg-touch-wrap-ssh-keygen"
git config --global core.sshCommand "$HOME/.claude/scripts/gpg-touch-overlay.sh wrap ssh"
```

(`gpg.program` and `gpg-touch-wrap-gpg` for OpenPGP signing.) If either
setting already names something else — a company ssh wrapper, say —
show the current value and let the operator decide; do not overwrite
it. Why a symlink, what it covers, what it costs:
[docs/setup/secure-agent-setup.md → From your own terminal](../../../../docs/setup/secure-agent-setup.md#from-your-own-terminal--gits-program-config).

**Optional, beyond git.** `ssh`, `scp`, `sftp` and `rsync` typed
straight into a terminal reach the key with no program setting to
point anywhere — only `PATH` sits in front of them. Offer a shim
directory: `mkdir -p ~/.claude/scripts/shims` and, for each of
`ssh scp sftp rsync`, `ln -sfn ~/.claude/scripts/gpg-touch-overlay.sh
~/.claude/scripts/shims/<name>`. The script dispatches on its own
basename for those names and skips any `PATH` entry resolving back to
itself, so a shim finds the real program and a wrapped git does not
chain into a shim. Create the directory and the links, then **print
the `PATH` line and let the operator add it themselves** — a shell rc
is never edited for them:
`export PATH="$HOME/.claude/scripts/shims:$PATH"`. No sandbox grant
is needed beyond K.4's: the links resolve to the script already
allowed there. Skip the offer when the operator has no touch-required
key. Rationale and the undo:
[docs/setup/secure-agent-setup.md → Beyond git](../../../../docs/setup/secure-agent-setup.md#beyond-git--ssh-scp-sftp-and-rsync-you-type-yourself).

**K.4 — Sandbox grants.** Three, all surfaced as one settings diff:
gpg-agent's ssh socket (`gpgconf --list-dirs agent-ssh-socket`,
absolute path) under `sandbox.network.allowUnixSockets`, so a sandboxed
git can sign and authenticate; only when
`git config --get gpg.format` is `ssh`, the file
`git config --get user.signingkey` names under
`sandbox.filesystem.allowRead`, since the sandbox denies the rest of
`~/.ssh/`; and, once K.3 points git at the wrapper, the wrapper's two
files — `~/.claude/scripts/gpg-touch-overlay.sh` and the
`gpg-touch-wrap-*` symlink — under `sandbox.filesystem.allowRead`,
because the git the agent runs reads the same global config and the
sandbox denies `~/.claude/` wholesale: without this grant every
sandboxed signed commit fails at once with `cannot exec`
([`docs/setup/sandbox-troubleshooting.md` → Signed commit fails with "cannot exec" of the touch-overlay wrapper](../../../../docs/setup/sandbox-troubleshooting.md#signed-commit-fails-with-cannot-exec-of-the-touch-overlay-wrapper)).
Resolve both with `readlink -f` first and grant the real files as
well when they are symlinks into a sync repository — the sandbox
checks the resolved path. Nothing wider: not `~/.ssh/`, not `~/.gnupg/`, not `~/.claude/scripts/`.

Verification of all four is check 10 of
`setup-isolated-setup-verify`; hand off rather than re-checking here.

## Step L — Container gateway (optional)

Fully optional, **default no**. Ask once whether the operator runs
`podman` or `docker` from inside sandboxed sessions, or wants to
start. On no, skip the step and say so. On yes, the sandboxed CLI
never reaches the real daemon socket directly — it talks to the
[container gateway](../../../../tools/container-gateway/README.md)
instead, a per-project policy proxy that runs outside the sandbox.
Rationale and the full install:
[docs/setup/secure-agent-setup.md → Container gateway](../../../../docs/setup/secure-agent-setup.md#container-gateway).

**L.1 — Hook script and the package it runs.** Copy
`tools/agent-isolation/container-gateway-hook.sh` into
`~/.claude/scripts/`, `chmod +x` it. The hook itself never executes
code from the repository being opened — only from a location the
operator installed or pinned — so also copy the whole package
`tools/container-gateway/src/container_gateway/` to
`~/.claude/scripts/container-gateway/src/container_gateway/`, next
to the hook. Without this second copy the hook finds no source at
session start and is a silent no-op: it never fails the session,
it simply never starts the gateway. A framework contributor working
in this checkout can instead export
`MAGPIE_CONTAINER_GATEWAY_SRC=tools/container-gateway/src` and skip
the copy; an adopter whose `.apache-magpie/` snapshot is already
populated needs neither, since the hook falls back to
`<root>/.apache-magpie/tools/container-gateway/src` on its own.

**L.2 — Hooks.** Wire a `SessionStart` hook running
`container-gateway-hook.sh start` and a `SessionEnd` hook running
`container-gateway-hook.sh stop` into `~/.claude/settings.json` —
merging into existing arrays with a diff the operator approves,
exactly as for K.2's touch-overlay hooks.

**L.3 — Project wiring.** Propose the `env` block
(`CONTAINER_HOST` / `DOCKER_HOST`) and the `allowUnixSockets` pair
as a single settings diff into the gitignored
`.claude/settings.local.json`. All four values are **absolute**
paths and therefore per-machine: the CLIs do not resolve a
project-relative `unix://./…` value against the cwd — the URL
authority is read as a host component, so `unix://./x` dials
`/.//x` — and `allowUnixSockets` has no relative form either.
Nothing gateway-related is committed to `.claude/settings.json`.
Never propose the real
daemon socket under any name; `tools/sandbox-lint` rejects an
`allowUnixSockets` entry named `docker.sock` / `podman.sock` /
`*-api.sock` outside `.apache-magpie-local/run/`.

Tell the operator plainly, every time this step runs:

- The framework never starts a Podman machine or Docker Desktop —
  discovery happens only at gateway start time, against whatever is
  already running.
- When Docker is absent but Podman is present, the gateway still
  serves the `docker` CLI, translated onto the Podman backend — the
  operator does not need both installed.
- The hook lives in `~/.claude/scripts/`, runs outside the sandbox
  on every `SessionStart` / `SessionEnd`, and — per L.1 — only ever
  executes the copy installed here, never anything from the project
  tree it is about to serve.

Verification of all four pieces is check 12 of
`setup-isolated-setup-verify`; hand off rather than re-checking here.

## Step M — the eval-harness exclusion (optional)

**Offer this only when the operator runs Magpie's eval suites** —
framework contributors, and adopters who maintain agentic overrides
and want the suites graded by a model. Everyone else should decline;
the step adds an unsandboxed command for no benefit. If the repo has
no `tools/skill-evals/`, skip it silently.

The problem it solves: `--cli` mode needs the model CLI's
credentials, which the sandbox denies, so an agent that runs a suite
itself gets one `ERROR` per case rather than a grade.

**M.1 — Copy the wrapper and the package it runs.** Same shape as
L.1, and for the same reason. Copy
`tools/skill-evals/magpie-run-evals.sh` into `~/.claude/scripts/`,
`chmod +x` it, and copy the whole package
`tools/skill-evals/src/skill_evals/` to
`~/.claude/scripts/skill-evals/src/skill_evals/` beside it. The
wrapper finds the package by looking next to itself.

**M.2 — The exclusion and the deny.** Propose, as one diff:

```jsonc
"sandbox": {
  "excludedCommands": ["~/.claude/scripts/magpie-run-evals.sh *"]
},
"permissions": {
  "deny": ["Edit(~/.claude/scripts/**)"]
}
```

Say why the copy is not optional, because it is the whole point of
the step:

- An exclusion makes whatever the command executes run **outside**
  the sandbox, so that code must not be writable by the thing being
  sandboxed. `~/.claude/scripts/` is outside every
  `sandbox.filesystem.allowWrite` root, so the copies are already
  beyond sandboxed Bash; the `Edit` deny closes the agent's own
  editing tools over the same directory.
- Excluding the runner **in the repository** instead fails twice
  over. `--cli` is an arbitrary shell command, so the exclusion
  would carve out `--cli "curl …"`, not the eval harness — and
  pinning `--cli` in the pattern does not hold, because argparse is
  last-wins. An `Edit` deny on an in-repo wrapper does not rescue
  it either: the wrapper matters only for what it executes, so the
  runner's whole source tree would need denying too.
- Remember the coupling when *any* in-repo path gets a deny: it
  becomes a sandbox write-deny, so the path must also join the
  `sandbox_write_denied` anchor in `.pre-commit-config.yaml`, or
  `end-of-file-fixer`, `mixed-line-ending` and `trailing-whitespace`
  abort `prek run --all-files`. Out-of-tree paths like
  `~/.claude/scripts/**` need no such entry.
- The wrapper takes exactly one positional path under `evals/` and
  no flags. That shape is what the exclusion is trusting. Any other
  eval invocation stays on the `!` prefix, outside the sandbox.
- **The copy goes stale.** Re-run M.1 after changing the runner, or
  the suites run from inside the sandbox are the old ones. Drift is
  check 13 of `setup-isolated-setup-verify` and a line in
  `setup-isolated-setup-update`.

Full rationale:
[`tools/skill-evals/README.md` → Running from inside the sandbox](../../../../tools/skill-evals/README.md#running-from-inside-the-sandbox).
