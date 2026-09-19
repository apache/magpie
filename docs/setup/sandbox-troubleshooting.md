<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Sandbox troubleshooting](#sandbox-troubleshooting)
  - [Shape of each entry](#shape-of-each-entry)
  - [SSH agent / Yubikey appears unreachable from inside the sandbox](#ssh-agent--yubikey-appears-unreachable-from-inside-the-sandbox)
    - [Symptom](#symptom)
    - [Root cause](#root-cause)
    - [Fix](#fix)
    - [Notes](#notes)
  - [Signed commit fails before any touch when git signs with ssh](#signed-commit-fails-before-any-touch-when-git-signs-with-ssh)
    - [Symptom](#symptom-1)
    - [Root cause](#root-cause-1)
    - [Fix](#fix-1)
    - [Notes](#notes-1)
  - [Test cannot bind to a localhost port](#test-cannot-bind-to-a-localhost-port)
    - [Symptom](#symptom-2)
    - [Root cause](#root-cause-2)
    - [Fix](#fix-2)
    - [Notes](#notes-2)
  - [Docker / Podman command fails with a socket error](#docker--podman-command-fails-with-a-socket-error)
    - [Symptom](#symptom-3)
    - [Root cause](#root-cause-3)
    - [Fix](#fix-3)
    - [Notes](#notes-3)
  - [Temp files fail with "Read-only file system" under `/tmp`](#temp-files-fail-with-read-only-file-system-under-tmp)
    - [Symptom](#symptom-4)
    - [Root cause](#root-cause-4)
    - [Fix](#fix-4)
    - [Notes](#notes-4)
  - [Adding a new entry](#adding-a-new-entry)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Sandbox troubleshooting

The secure agent setup ([`secure-agent-setup.md`](secure-agent-setup.md))
runs every Bash subprocess inside a sandbox: Seatbelt on macOS,
bubblewrap on Linux, plus Claude Code's filesystem / network
allowlists. A correct sandbox restricts what the agent can read and
where it can talk; an *over-restrictive* one breaks legitimate
workflows in ways that look like unrelated bugs ("ssh-agent
unreachable", "address already in use", "Cannot connect to Docker
daemon"). This page is the catalog of those cases — the
**symptom** you see, the **root cause** in the sandbox config, and
the **fix** (a settings.json widening with a one-line rationale).

If you hit a sandbox-shaped failure not listed below, add it here
in the same shape — the catalog grows by experience, not by
prediction.

Two surfaces make these entries discoverable in-session so a
future reader does not have to remember the catalog exists:

- The [`setup-isolated-setup-doctor`](../../skills/setup-isolated-setup-doctor/SKILL.md)
  skill probes each catalogued failure mode on demand and links
  back to the matching entry. Invoke it when you suspect a
  sandbox restriction; it runs the full probe set even when only
  one is in question.
- The
  [Sandbox-error hint hook](secure-agent-setup.md#sandbox-error-hint-hook)
  fires after every Bash tool call, pattern-matches the result
  for the literal error strings catalogued below, and prints a
  `[sandbox-hint] …` line pointing at the matching entry — so
  the catalog reference appears next to the error automatically.

When the catalog grows a new entry, extend both surfaces too:
add a matching probe to the doctor skill, and add a matching
`match … hint=…` branch to the hint hook. The catalog stays the
source of truth; the doctor and the hook stay the discoverability
layer.

Related:

- [`secure-agent-setup.md`](secure-agent-setup.md) — full install
  walkthrough including the authoritative `~/.claude/settings.json`
  reference.
- [`secure-agent-internals.md`](secure-agent-internals.md) — how
  each layer of the sandbox works and why.

---

## Shape of each entry

Every entry follows the same four sections so a future reader can
pattern-match quickly:

1. **Symptom** — the exact error message text the agent (or the
   user, in a terminal) sees. Verbatim where possible so a grep
   into this page surfaces the matching entry.
2. **Root cause** — which sandbox layer (Seatbelt / bubblewrap /
   Claude Code filesystem allowlist / network allowlist /
   `permissions.deny`) is blocking the call, and why the
   restriction exists.
3. **Fix** — a concrete edit to `~/.claude/settings.json` (or the
   adopter's project-local `.claude/settings.local.json`, where
   that scope makes more sense) shown as a JSON snippet. Per-entry
   rationale so the widening is auditable.
4. **Notes** — platform-specific path variants, alternative paths
   the same agent / runtime might use, when *not* to apply the
   widening.

---

## SSH agent / Yubikey appears unreachable from inside the sandbox

### Symptom

Any of:

```text
sign_and_send_pubkey: signing failed for ED25519 "user@host": agent refused operation
Could not open a connection to your authentication agent.
ssh-add: error fetching identities for protocol 1: communication with agent failed
Permission denied (publickey).
```

…on `git push`, `ssh user@host`, `ssh-add -l`, or any operation
that consults `ssh-agent`. The variant the user reports as
"Yubikey badly detected" — the Yubikey is plugged in and works
outside the sandbox, but the agent inside the sandbox can't reach
its socket.

### Root cause

`SSH_AUTH_SOCK` is passed through the `claude-iso` clean-env
wrapper's whitelist (see [`secure-agent-setup.md` → The clean-env
wrapper](secure-agent-setup.md#the-clean-env-wrapper)), so the
environment variable is set inside the sandbox. The socket *path*
it points at is the missing piece: on macOS the path is typically
`/private/tmp/com.apple.launchd.*/Listeners`, which is not in any
`allowRead` entry; on Linux it is typically
`/run/user/<uid>/keyring/ssh` or a gpg-agent variant, only the
gpg-agent path of which is currently allowed
(`/run/user/*/gnupg/`).

Without read access to the socket file, the agent's `ssh` /
`git push` subprocesses get `Operation not permitted` when they
try to `connect(2)` the unix-domain socket — but the userland
error surfaces as the "agent unreachable" / "Permission denied"
strings above, which is what makes the cause non-obvious.

**On Linux, path access is necessary but not sufficient.** Recent
Claude Code builds sandbox Bash with a seccomp filter that rejects
`socket(AF_UNIX, ...)` outright, before any path is consulted, so no
`allowRead` / `allowWrite` entry can make an agent reachable:

```text
$ python3 -c 'import socket; socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)'
PermissionError: [Errno 1] Operation not permitted
# the same call with AF_INET succeeds, so this is not a path problem
```

Verified under bubblewrap with `~/.gnupg/` and `/run/user/<uid>/gnupg/`
in **both** `allowRead` and `allowWrite`: a signed `git commit` still
fails with `No agent running`, and `gpg-connect-agent` cannot start one
(`exit status 2`). Where that filter is active, an agent-dependent
command — a signed `git commit`, `git tag -s`, `ssh-add -l` — must run
with a per-call sandbox bypass, or outside the agent session entirely.
The allowlist entries below remain correct and still matter (gpg reads
the keyring through them); they simply do not restore the agent channel
on their own.

**On macOS, path access is likewise necessary but not sufficient.**
Seatbelt lets a sandboxed process `stat(2)` a socket whose path is in
`allowRead`, but `connect(2)` to a Unix socket is a separate grant:
`sandbox.network.allowUnixSockets`. With only the read entry the
symptom is exactly the one above — the socket file is visible and
the agent is "unreachable":

```text
$ ssh-add -l
Error connecting to agent: Operation not permitted
$ git commit …
error: No private key found for public key "~/.ssh/<key>.pub"?
fatal: failed to write commit object
```

(`ssh-keygen -Y sign` reports the unreachable agent as a missing
private key — it found the public half, asked the agent for the
private half, and got no answer.)

### Fix

Two entries on macOS — the socket path has to be both readable and
connectable — and one on Linux (see the `AF_UNIX` caveat above for
what the read entry can and cannot do there). Add the socket to
`sandbox.filesystem.allowRead` and, on macOS, to
`sandbox.network.allowUnixSockets`:

```jsonc
// ~/.claude/settings.json
{
  "sandbox": {
    "filesystem": {
      "allowRead": [
        // ...existing entries...
        "/private/tmp/com.apple.launchd.*/Listeners",   // macOS: system launchd-managed ssh-agent socket
        "/private/tmp/ssh-*/agent.*"                    // macOS: openssh-portable variant (rare)
        // Linux: `~/.gnupg/` and `/run/user/*/gnupg/` are already in the framework reference;
        // add `/run/user/*/keyring/` here if you use gnome-keyring or seahorse for SSH.
      ]
    },
    "network": {
      "allowUnixSockets": [                             // macOS only — ignored on Linux
        "/Users/<you>/.gnupg/S.gpg-agent.ssh"           // gpg-agent's ssh socket (enable-ssh-support); absolute path
        // "/private/tmp/com.apple.launchd.*/Listeners"   // instead, for the system ssh-agent
      ]
    }
  }
}
```

Per-entry rationale:

- `/private/tmp/com.apple.launchd.*/Listeners` — Apple's launchd
  manages per-session daemon sockets including the system
  `ssh-agent`. The wildcard `*` matches the launchd UUID; the
  `Listeners` directory holds the actual socket files. This is the
  default path on macOS.
- `/private/tmp/ssh-*/agent.*` — fallback for openssh-portable
  running outside launchd (uncommon on stock macOS, sometimes seen
  with Homebrew-installed openssh).

### Notes

- If you use **gpg-agent for SSH** (`enable-ssh-support` in
  `~/.gnupg/gpg-agent.conf`), the read side is already covered —
  the framework reference includes `~/.gnupg/` and
  `/run/user/*/gnupg/`, where `S.gpg-agent.ssh` lives. That is
  **not enough on macOS**: the socket also has to be listed in
  `sandbox.network.allowUnixSockets`, or `connect(2)` is denied and
  `ssh-add -l` reports the agent unreachable while the file is
  plainly there. On Linux, see the `AF_UNIX` caveat under *Root
  cause*: the read entries let gpg read the keyring, but do not by
  themselves make the agent socket reachable.
- If you use **Secretive** (an alternative macOS Yubikey
  agent), the socket lives under
  `~/Library/Group Containers/<bundle>/socket.ssh`; add that
  specific path to `allowRead` instead of the launchd glob.
- Do **not** widen `allowRead` to `/private/tmp/**` — that opens
  the entire system temp directory, which other processes use for
  arbitrary files including credentials. Stay specific.
- If git signs with **`gpg.format=ssh`**, the agent socket is only
  half of it: git also has to *read* the public key file, which the
  sandbox denies along with the rest of `~/.ssh/`. That is its own
  entry — [Signed commit fails before any touch when git signs with ssh](#signed-commit-fails-before-any-touch-when-git-signs-with-ssh).

---

## Signed commit fails before any touch when git signs with ssh

### Symptom

`git commit` with `commit.gpgsign=true` and `gpg.format=ssh` fails
at once — no touch is requested, the hardware-key touch overlay
never appears — and git reports:

```text
Couldn't load public key /Users/<you>/.ssh/<key>.pub: No such file or directory
fatal: failed to write commit object
```

The tell is the timing. A signature the key is actually waiting on
takes the key's full touch window (~15 s) before it gives up with
`agent refused operation`; this fails in well under a second. The
same deny reads differently from a plain `head -c 1 <that file>` in
a sandboxed Bash — `Operation not permitted` — which is what the
doctor probe and verify check report; `ssh-keygen` sees the hidden
path as missing.

### Root cause

Filesystem allowlist. With `gpg.format=ssh`, git does not sign
through gpg at all: it runs
`ssh-keygen -Y sign -f <user.signingkey> -n git`, and
`user.signingkey` names the **public** key file under `~/.ssh/`.
The framework's `permissions.deny` carries `Read(~/.ssh/**)`, which
the sandbox mirrors as a read deny on the whole directory, so
`ssh-keygen` cannot open the file. The agent socket (the entry
above) is the separate requirement that lets the *private* half
sign; this entry is about the public half git must read first.

### Fix

Allow that one file — and only that file — for reads:

```jsonc
// ~/.claude/settings.json
{
  "sandbox": {
    "filesystem": {
      "allowRead": [
        // ...existing entries...
        "~/.ssh/id_ed25519_sk.pub"   // the file `git config --get user.signingkey` prints
      ]
    }
  }
}
```

Per-entry rationale: it is the public key, which is not a secret
by definition; the private key stays on the token or in the agent.
Never widen this to `~/.ssh/` — that directory also holds private
keys, `config` and `known_hosts`.

### Notes

- Find the exact path with `git config --get user.signingkey`.
  With a hardware key that is the `.pub` file; the agent holds the
  private half.
- `permissions.deny`'s `Read(~/.ssh/**)` stays as it is. That rule
  governs the agent's own Read tool, which has no business in
  `~/.ssh/`; `sandbox.filesystem.allowRead` only widens what Bash
  subprocesses may open.
- The hardware-key touch overlay
  ([`secure-agent-setup.md` → Hardware-key touch overlay](secure-agent-setup.md#hardware-key-touch-overlay))
  cannot flag this: it watches for `ssh-keygen` *blocking* on the
  key, and here `ssh-keygen` exits before it ever blocks. If the
  overlay never shows for a commit that fails instantly, check this
  entry before suspecting the overlay.
- Linux: the `AF_UNIX` caveat in the entry above still applies on
  top of this one.

## Test cannot bind to a localhost port

### Symptom

```text
[Errno 13] Permission denied
[Errno 49] Can't assign requested address
OSError: [Errno 98] Address already in use   # red herring when sandbox-related
```

…from a test that starts a fixture server (`pytest` with
`live_server`, `requests-mock`, an integration test spinning up a
local HTTP listener, a webhook fixture). The same test passes
outside the sandbox.

### Root cause

Claude Code's `sandbox.network` block is allowlist-based on
**outbound hosts** (egress to named domains), not on inbound
binds. For most listener types this is fine — `bind(2)` on
`127.0.0.1` doesn't go through the network namespace at all on
macOS, and on Linux loopback is allowed by default.

The case that bites is **a test that needs to talk to its own
server over the loopback interface**: the test binds (works),
the test's HTTP client then tries to `GET http://127.0.0.1:NNNN/`
(may fail), because the sandbox's network allowlist does not
include `127.0.0.1` or `localhost` and the egress proxy treats it
as a disallowed destination.

The "Permission denied" / "Address already in use" texts the test
runner surfaces are *its own framework's* generic error strings,
not the sandbox's — which makes the root cause hard to spot.

### Fix

Add `localhost` and `127.0.0.1` to the network allowlist:

```jsonc
// ~/.claude/settings.json
{
  "sandbox": {
    "network": {
      "allowedDomains": [
        // ...existing entries...
        "localhost",                                    // local fixture servers, test webhooks
        "127.0.0.1"                                     // same; IP form for tests that use it directly
      ]
    }
  }
}
```

Per-entry rationale:

- `localhost` / `127.0.0.1` — loopback only. Adding these does
  not widen the egress surface (no traffic leaves the host); it
  just lets the sandbox proxy stop treating loopback as a
  disallowed destination.

### Notes

- For tests that need an *outbound* port (e.g. an integration test
  that listens on a port and then a separate process connects from
  outside the test's own runtime), `localhost` is not enough — you
  need to allow the actual remote IP in `allowedDomains`. Those
  are project-scope concerns; add to `.claude/settings.json` in
  the adopter repo rather than the user-scope file.
- If a test is genuinely incompatible with the sandbox (e.g. it
  expects raw socket access to a privileged port), the per-call
  escape hatch is `dangerouslyDisableSandbox: true` in the Bash
  tool call — but that surface should be visually loud (the
  `sandbox-bypass-warn.sh` hook ensures it is). Prefer the
  allowlist fix above when applicable.

---

## Docker / Podman command fails with a socket error

### Symptom

```text
Cannot connect to the Docker daemon at unix:///Users/<user>/.docker/run/docker.sock. Is the docker daemon running?
ERRO[0000] error connecting to /var/run/docker.sock: open /var/run/docker.sock: operation not permitted
Cannot connect to Podman. Please verify your connection to the Linux system using `podman system connection list`
```

…on any `docker` / `podman` / `nerdctl` invocation. The CLI is
installed and the runtime is running on the host — the sandbox is
just blocking access to its socket.

On macOS with Docker Desktop the failure usually arrives *earlier*
than that, as one of:

```text
zsh: operation not permitted: docker
docker: unknown command: docker compose
```

The first means the sandbox is blocking the `docker` binary itself;
the second means it is blocking the CLI plugins. Neither reaches the
socket at all, so the socket allowlist below does not fix them on its
own — see the CLI paths in the same block.

A third form appears once the CLI runs but the connection is still
refused, on every platform:

```text
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

That one is the missing `sandbox.network.allowUnixSockets` entry, not a
filesystem permission — see below.

### Root cause

The runtime CLI talks to its daemon via a unix-domain socket. The
framework's reference `~/.claude/settings.json` has
`Read(~/.docker/**)` in `permissions.deny` (to keep the agent
from reading Docker credentials stored under `~/.docker/config.json`)
and lists `~/.docker` in the broader filesystem `denyRead` set.
Both block the socket file under `~/.docker/run/docker.sock`,
which is where Docker.app for Mac drops its socket.

On macOS the same `~/.docker` denial also blocks two things that
are not the socket, and that a socket-only allowlist therefore
leaves broken:

- **The CLI binary.** Docker Desktop installs it *inside* the denied
  directory — `docker` on `PATH` is `~/.docker/bin/docker`, a symlink
  into `/Applications/Docker.app`. Denied, the shell cannot execute it
  at all (`operation not permitted: docker`).
- **The CLI plugins.** `docker compose` and `docker buildx` are not
  builtins; they are separate binaries in `~/.docker/cli-plugins/`.
  Denied, `docker ps` works while `docker compose` reports
  `unknown command`, which breaks any compose-driven workflow.

Separately, and on **every** platform: listing a socket in
`sandbox.filesystem.allowRead` grants permission to *read the file*,
not to *connect to it*. Socket connections are gated by their own
`sandbox.network.allowUnixSockets` list. With the path allowed for
reading but absent from that list, the CLI starts, finds the socket,
and is refused at `connect(2)`:

```console
$ docker ps
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

Both settings are required; neither substitutes for the other. This is
not macOS-specific — a Linux adopter using `/var/run/docker.sock` needs
the `allowUnixSockets` entry just the same.

For Colima the socket lives under `~/.colima/...` (not currently
covered by any allow / deny in the framework reference, so it
works by default), and for rootless Podman it lives under
`$XDG_RUNTIME_DIR/podman/...` (also not covered → works). The
case that fails is specifically Docker.app on macOS plus the
generic `~/.docker` denial.

### Fix

Allow Bash subprocesses to read the *socket file*, the CLI, and its
plugins without opening the `~/.docker/` directory generally:

```jsonc
// ~/.claude/settings.json
{
  "sandbox": {
    "filesystem": {
      "allowRead": [
        // ...existing entries...
        "~/.docker/run/docker.sock",                    // Docker.app for Mac socket
        "~/.colima/default/docker.sock",                // Colima default socket (defensive; usually not blocked)
        "/var/run/docker.sock",                         // Linux daemon socket (root-managed install)
        "~/.docker/bin/",                               // Docker Desktop CLI binaries (`docker` itself lives here on macOS)
        "~/.docker/cli-plugins/"                        // `docker compose`, `docker buildx` — separate plugin binaries
      ]
    },
    "network": {
      // Reading the socket file is not the same permission as connecting
      // to it. Without these, the CLI runs but every command is refused
      // with "permission denied while trying to connect to the docker API".
      "allowUnixSockets": [
        "/var/run/docker.sock",
        "~/.docker/run/docker.sock"
      ]
    }
  },
  "permissions": {
    "deny": [
      // ...existing entries...
      "Read(~/.docker/config.json)",                    // keep this denial — credentials live here
      "Read(~/.docker/contexts/**)"                     // keep this denial — saved contexts
      // (Replace the broad `Read(~/.docker/**)` with these two specific paths.)
    ]
  }
}
```

Per-entry rationale:

- `~/.docker/run/docker.sock` — Docker.app for Mac's socket
  location. Read access on the socket file is what the docker CLI
  needs to `connect(2)` to the daemon.
- `~/.colima/default/docker.sock` — Colima's default; explicit
  even though it works today, to anticipate a future widening of
  the generic `~/.` denial.
- `/var/run/docker.sock` — Linux systems with daemon Docker;
  socket is root-managed but world-readable by convention.
- `~/.docker/bin/` — Docker Desktop for Mac installs the `docker`
  CLI here (as a symlink into `/Applications/Docker.app`), so
  without it the binary cannot be executed and no socket entry
  matters. Not needed for Homebrew or Linux installs, where the
  CLI lives on a normal `PATH` directory outside `~/.docker`.
- `~/.docker/cli-plugins/` — `docker compose` and `docker buildx`
  are plugin binaries, not builtins. Without it `docker ps`
  succeeds but `docker compose` fails as `unknown command`.
- `sandbox.network.allowUnixSockets` — the connect-side permission,
  required on every platform. `allowRead` on the same path only
  lets a process *open the file*; the sandbox gates socket
  *connections* through this separate list. Verified by removing
  it while leaving the `allowRead` entries in place: `docker
  compose version` still ran, and `docker ps` failed with
  `permission denied while trying to connect to the docker API`.
- The narrowed `permissions.deny` keeps the agent's `Read` tool
  from seeing Docker auth tokens (`config.json`) and saved
  contexts (which include host IPs and credentials), while
  allowing the Bash subprocess to use the socket.

### Notes

- For **rootless Podman**, the socket is at
  `$XDG_RUNTIME_DIR/podman/podman.sock` (typically
  `/run/user/<uid>/podman/podman.sock`). Currently allowed by
  default because the framework reference does not deny
  `/run/user/<uid>/`; if a future widening adds such a denial,
  add `/run/user/*/podman/` to `allowRead`.
- For **CI / image-build workflows** that run inside an adopter
  repo, prefer adding the socket allow at project scope
  (`.claude/settings.local.json` in the adopter) rather than user
  scope — that keeps the framework's user-scope reference minimal
  and makes the widening visible to whoever audits the adopter's
  repo.
- Do **not** widen `allowRead` to `~/.docker/**` — the directory
  holds auth tokens and saved contexts; the whole point of the
  framework's `Read(~/.docker/**)` denial is to keep those out of
  the agent's reach.

---

## Temp files fail with "Read-only file system" under `/tmp`

### Symptom

```console
$ mktemp -d
mktemp: failed to create directory via template '/tmp/tmp.XXXXXXXXXX': Read-only file system

$ touch /tmp/scratch
touch: cannot touch '/tmp/scratch': Read-only file system
```

Python and other runtimes surface the same restriction through
`tempfile`:

```text
OSError: [Errno 30] Read-only file system: '/tmp/tmpXXXXXXXX'
```

### Root cause

The sandbox mounts the host `/tmp` **read-only** and punches only
specific subpaths writable — Claude Code's own scratch tree under
`/tmp/claude-<uid>/` plus anything listed in
`sandbox.filesystem.allowWrite`. Anything writing to `/tmp`
directly is refused.

Most tooling honours `$TMPDIR` and therefore lands inside the
writable tree without noticing. The failure shows up when either:

- `TMPDIR` is unset or has been overwritten (a login shell, an
  `env -i` wrapper, a Makefile that clears the environment), so the
  runtime falls back to the hardcoded `/tmp`; or
- `TMPDIR` names a path outside `sandbox.filesystem.allowWrite`.

A second, quieter failure mode: `TMPDIR` points at the shared
session root rather than a per-project directory, so concurrent
sessions in different repos write temp files into the same
directory and can collide on identical filenames.

### Fix

Point `TMPDIR` at a per-project directory inside the writable tree,
in the **project's** `.claude/settings.local.json` — that file is
per-project, so the value is per-project by construction:

```jsonc
// <adopter-repo>/.claude/settings.local.json
{
  "env": {
    // <uid> is your numeric uid; <path-slug> is the project's
    // absolute path with "/" replaced by "-".
    "TMPDIR": "/tmp/claude-<uid>/<path-slug>/shared"
  }
}
```

Per-entry rationale:

- `/tmp/claude-<uid>/` is already inside the sandbox's writable
  set, so no `allowWrite` widening is needed — this entry costs
  nothing in sandbox surface.
- `<path-slug>` matches the convention Claude Code already uses for
  its own scratch tree, so the directory sits alongside the
  session's existing state instead of introducing a second
  location.
- Scoping to `settings.local.json` rather than user-scope
  `settings.json` is what makes the value per-project. A
  user-scope `TMPDIR` would be shared by every repo and would
  reintroduce the collision mode.

Create the directory before first use — a `TMPDIR` naming a
non-existent path fails the same way.

### Notes

- **`env` is applied at session start.** The change does not take
  effect in the session that makes it; restart, then confirm with
  the doctor skill's *project-scratch* probe.
- The scratch directory **cannot** be remapped onto literal `/tmp`
  inside the sandbox. `sandbox.filesystem.*` accepts allow / deny
  path lists only — there is no bind-mount or path-remap key.
  `sandbox.bwrapPath` swaps the bwrap *binary*, not its flags, so
  it cannot inject `--bind`, and it is honored only from
  admin-controlled managed settings. Seatbelt exposes no
  profile-injection surface either. `TMPDIR` is the supported
  lever.
- Independently of that ceiling, mounting over `/tmp` would hide
  Claude Code's own IPC endpoints that live there
  (`cc-daemon-<uid>`, `claude-http-*.sock`) and would likely break
  the session.
- Do **not** widen `allowWrite` to `/tmp` as a whole — that opens
  the entire system temp directory, which other processes use for
  arbitrary files including credentials.

---

## Adding a new entry

When you hit a sandbox-shaped failure not in this list:

1. Capture the exact symptom (error text, command, what you were
   trying to do). The error text is what makes the entry
   greppable for the next person.
2. Identify the layer: filesystem (`Operation not permitted` on a
   path), network (refused / timed-out connection to an allowed
   host's friend), or `permissions.deny` (the agent's tool got an
   "I refuse" without the sandbox even being consulted).
3. Find the minimal widening — the most specific `allowRead` /
   `allowedDomains` entry that resolves the symptom without
   opening adjacent paths. Stay as specific as the runtime
   reasonably allows; never widen `~/`, `/var/`, or `/private/`
   as a whole.
4. Add an entry to this page in the *Shape of each entry* form
   above. Cross-reference adjacent entries when relevant.

If the fix involves `dangerouslyDisableSandbox: true` rather than
a settings.json widening, document it here too — the bypass is a
legitimate per-call escape hatch, but it should be visible in the
catalog so future readers can see when it's the right call.
