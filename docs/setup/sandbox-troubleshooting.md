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
  - [Signed commit fails with "cannot exec" of the touch-overlay wrapper](#signed-commit-fails-with-cannot-exec-of-the-touch-overlay-wrapper)
    - [Symptom](#symptom-2)
    - [Root cause](#root-cause-2)
    - [Fix](#fix-2)
    - [Notes](#notes-2)
  - [Signed commit fails with the agent refusing, and the overlay never appeared](#signed-commit-fails-with-the-agent-refusing-and-the-overlay-never-appeared)
    - [Symptom](#symptom-3)
    - [Root cause](#root-cause-3)
    - [Fix](#fix-3)
    - [Notes](#notes-3)
  - [Test cannot bind to a localhost port](#test-cannot-bind-to-a-localhost-port)
    - [Symptom](#symptom-4)
    - [Root cause](#root-cause-4)
    - [Fix](#fix-4)
    - [Notes](#notes-4)
  - [Docker / Podman command fails with a socket error](#docker--podman-command-fails-with-a-socket-error)
    - [Symptom](#symptom-5)
    - [Root cause](#root-cause-5)
    - [Fix](#fix-5)
    - [Notes](#notes-5)
  - [Temp files fail with "Read-only file system" under `/tmp`](#temp-files-fail-with-read-only-file-system-under-tmp)
    - [Symptom](#symptom-6)
    - [Root cause](#root-cause-6)
    - [Fix](#fix-6)
    - [Notes](#notes-6)
  - [`gh` fails with TLS `OSStatus -26276` or `HTTP 401` inside the sandbox](#gh-fails-with-tls-osstatus--26276-or-http-401-inside-the-sandbox)
    - [Symptom](#symptom-7)
    - [Root cause](#root-cause-7)
    - [Fix](#fix-7)
    - [Notes](#notes-7)
  - [`prek` or `uv` not found, or cannot write its cache, inside the sandbox](#prek-or-uv-not-found-or-cannot-write-its-cache-inside-the-sandbox)
    - [Symptom](#symptom-8)
    - [Root cause](#root-cause-8)
    - [Fix](#fix-8)
    - [Notes](#notes-8)
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
- The socket grant makes **signing** work. Whether it also makes
  `git push` / `git fetch` over ssh work from inside the sandbox
  depends on the harness. A sandbox that routes network through its
  HTTP proxy only gives an ssh transport no DNS and no TCP —
  `ssh: Could not resolve hostname github.com` — before any key is
  consulted; push from your own terminal (the `!` prefix in Claude
  Code runs a command there), or use an https remote, which does go
  through the proxy. A harness that exports a `GIT_SSH_COMMAND` whose
  `ProxyCommand` points ssh at its SOCKS proxy changes the symptom,
  not the outcome, as long as that proxy wants credentials `nc`
  cannot offer — `This proxy requires authentication, and this
  client did not offer an authentication method` (Claude Code on
  macOS, 2026-09). Where the transport *does* get through, it then
  asks the key for its *authentication* touch — a `git pull` that
  hangs with no error is usually that, and the
  [touch overlay](secure-agent-setup.md#hardware-key-touch-overlay)
  covers it.
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

## Signed commit fails with "cannot exec" of the touch-overlay wrapper

### Symptom

Every `git commit` the agent runs fails at the signature, instantly,
after the touch overlay's wrapper has been installed as git's signing
program
([`secure-agent-setup.md` → From your own terminal](secure-agent-setup.md#from-your-own-terminal--gits-program-config)):

```text
fatal: cannot exec '/Users/<you>/.claude/scripts/gpg-touch-wrap-ssh-keygen': Operation not permitted
error:
fatal: failed to write commit object
```

Or, when the wrapper itself could be started but the script behind
it could not be read (see the symlink note under *Fix*):

```text
error: bash: /Users/<you>/.claude/scripts/gpg-touch-wrap-ssh-keygen: Operation not permitted
fatal: failed to write commit object
```

The same commit from your own terminal works, and signs with the
window up. A `git pull` or `git push` over ssh fails the same way when
`core.sshCommand` names the wrapper: `fatal: cannot exec
'…/gpg-touch-overlay.sh wrap ssh'` or a bare `Permission denied`
from the shell that tries to start it.

### Root cause

Filesystem allowlist. `gpg.ssh.program` (`gpg.program`,
`core.sshCommand`) is global git config, so the git the agent runs
inside the sandbox reads it too and tries to start the wrapper. The
wrapper lives in `~/.claude/scripts/`, and the sandbox denies reads
under `~/.claude/` wholesale — the interpreter cannot open the script,
and git reports the exec failure. Nothing about the key or the agent
socket is involved: the failure is one directory earlier.

Inside the sandbox the wrapper would do nothing anyway — it stands
aside in an agent session (`CLAUDECODE=1`) and only runs the real
program — but it has to be readable to get that far.

### Fix

Allow the two wrapper files — the script and the symlink git names —
for reads, and nothing else under `~/.claude/`:

```jsonc
// ~/.claude/settings.json
{
  "sandbox": {
    "filesystem": {
      "allowRead": [
        // ...existing entries...
        "~/.claude/scripts/gpg-touch-overlay.sh",
        "~/.claude/scripts/gpg-touch-wrap-ssh-keygen"   // or gpg-touch-wrap-gpg with OpenPGP signing
      ]
    }
  }
}
```

The symlink and its target are both listed because the sandbox
resolves the path git opens and the path the interpreter then reads
separately. The window scripts next to them need no entry: the
wrapper never reaches them from inside the sandbox.

**If your `~/.claude/scripts/` entries are themselves symlinks** —
into a dotfile sync repository, the layout
[`secure-agent-setup.md` → Syncing user-scope config across machines](secure-agent-setup.md#syncing-user-scope-config-across-machines)
recommends — the grant must name the **real** file, because the
sandbox checks the resolved path: with
`~/.claude/scripts/gpg-touch-overlay.sh -> ~/.claude-config/scripts/gpg-touch-overlay.sh`,
list `~/.claude-config/scripts/gpg-touch-overlay.sh` as well. The
tell is the second form of the symptom: git starts the wrapper, and
it is `bash:` that reports `Operation not permitted` on the script.
`readlink -f ~/.claude/scripts/gpg-touch-wrap-ssh-keygen` prints the
path to grant.

Per-entry rationale: these are two framework-authored scripts the
operator installed by hand; no credential, no configuration of the
agent's own lives in them. Never widen this to `~/.claude/scripts/`
or `~/.claude/` — the latter holds the agent's settings, hooks and
session state.

### Notes

- The verify skill's check 10d and the doctor's signing-key probe
  both report the wrapper unreadable before a commit trips over it.
- Until the grant is in place, a one-off `git -c
  gpg.ssh.program=/usr/bin/ssh-keygen commit …` signs without the
  wrapper; the hook still arms the window for the agent's commit.
- The failure is the mirror image of the previous entry: there git
  could not read the key file, here it cannot read the program. Both
  fail in well under a second, before the key is asked for anything.

## Signed commit fails with the agent refusing, and the overlay never appeared

### Symptom

A `git commit` the agent runs gets through every pre-commit hook and
then dies at the signature, with a write error from the wrapper
immediately before it and no touch window at any point:

```text
error: /Users/<you>/.claude/scripts/gpg-touch-wrap-ssh-keygen: line 340: /tmp/magpie-gpg-touch/watcher.pid: Operation not permitted
Signing file /tmp/claude-<uid>/.git_signing_buffer_tmpXXXXXX
Couldn't sign message (signer): agent refused operation?
fatal: failed to write commit object
```

The same commit succeeds when run outside the sandbox, or from your own
terminal.

### Root cause

The overlay keeps its owners registry, window lease, pid and log files
in `$XDG_RUNTIME_DIR/magpie-gpg-touch`. macOS sets no
`XDG_RUNTIME_DIR`, and the fallback used to be `/tmp`, which is outside
the sandbox's write set. The wrapper cannot create its pid file, so no
watcher starts; nothing puts a window on screen; the key is never
touched; and gpg-agent gives up with `agent refused operation`.

The error names the *watcher*, not the key, which is what makes this
read like a broken signing setup rather than a sandbox denial.

### Fix

Update the framework. The fallback is now
`${XDG_CACHE_HOME:-$HOME/.cache}/magpie-gpg-touch`, which is per-user,
not world-writable, and inside the reference `allowWrite`, so the
watcher starts under the sandbox with no widening.

A stale `/tmp/magpie-gpg-touch/` left by an older version is harmless
and can be removed.

Do **not** point the overlay at `$TMPDIR` instead. It differs between
the signing contexts that have to find one another — the agent's hooks
see the harness's scratch directory, a terminal `git` sees the login
one — and two contexts computing two runtime directories cannot share
an owners registry or a window lease.

### Notes

- The `/tmp` fallback was also a local-security weakness independent of
  the sandbox: `/tmp` is world-writable, so another user on the machine
  could pre-create the directory and sit on the pid files and the lock
  the window is leased through.
- Distinct from the two entries above: there git could not read the key
  or could not exec the wrapper, and both failed instantly. Here the
  wrapper runs, the signature is genuinely attempted, and the failure
  arrives only once the agent stops waiting for a touch that was never
  prompted for.

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

A second shape fails one step earlier, on the `bind(2)` call
itself, before any client connects:

```text
OSError: [Errno 1] Operation not permitted
```

…on every address (`127.0.0.1`, `localhost`, `0.0.0.0`, `::1`),
with no `allowedDomains` change making any difference. The doctor
skill's *localhost-bind* probe reports it as `✗ (bind: [Errno 1]
Operation not permitted)`.

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

The **`bind(2)` refusal** is a different gate. Newer Claude Code
sandbox profiles deny listening sockets outright unless
`sandbox.network.allowLocalBinding` is `true`; the framework
reference `.claude/settings.json` does not set it, so a listener
is refused before the egress proxy is ever involved. Adding
`localhost` / `127.0.0.1` to `allowedDomains` does not help this
shape, because no outbound connection is being attempted yet.

### Fix

For the `bind(2)` refusal, enable local binding. It is a boolean,
so the last settings file that sets it wins; the per-project
`.claude/settings.local.json` is the right place when only some
repos run fixture servers:

```jsonc
// <adopter-repo>/.claude/settings.local.json
{
  "sandbox": {
    "network": {
      "allowLocalBinding": true                         // let sandboxed processes listen on a port
    }
  }
}
```

`allowLocalBinding` permits `listen(2)` on the host's interfaces;
it does not add any outbound destination, so the egress allowlist
is unchanged. Once binding works, the loopback GET below may still
fail — apply both fixes when the probe reports both.

For the loopback-GET failure, add `localhost` and `127.0.0.1` to
the network allowlist:

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
Error: unable to connect to Podman socket: failed to read identity "/Users/<you>/.local/share/containers/podman/machine/machine": operation not permitted
dial unix ./.apache-magpie-local/run/podman.sock: connect: no such file or directory
dial unix ./.apache-magpie-local/run/podman.sock: connect: operation not permitted
```

…on any `docker` / `podman` / `nerdctl` invocation.
The first three lines are the CLI reaching straight for the real daemon socket or the podman machine's ssh identity, both denied by design.
The last two are the CLI reaching the container gateway's own socket instead.
`no such file or directory` means the gateway is not running for this project.
`operation not permitted` means its socket is not in `sandbox.network.allowUnixSockets`.

Inside the sandbox, `podman machine list` prints an empty table even when the machine is running, because the machine directory under `~/.local/share/containers/podman/machine/` is unreadable.
An empty list from inside the sandbox is therefore not evidence that no machine exists.
Check the machine's real state from **outside** the sandbox (a `!`-prefixed shell command, or your own terminal) before assuming it needs `podman machine init`.

### Root cause

The container daemon socket is root-equivalent over whatever the daemon mounts: a default Podman machine mounts `/Users`, `/private`, and `/var/folders` read-write, and Docker Desktop's daemon is no narrower.
Neither excluding `docker` / `podman` from the sandbox with `sandbox.excludedCommands`, which some upstream guidance suggests, nor listing the daemon socket itself in `sandbox.network.allowUnixSockets` is acceptable for that reason: both hand the agent unrestricted host access through the daemon.
The framework's `sandbox-lint` tool enforces the second half of that.
It rejects any `allowUnixSockets` entry whose basename is `docker.sock`, `podman.sock`, or ends in `-api.sock`, unless the entry's parent directory is `.apache-magpie-local/run`.

On macOS, the podman CLI's default connection to a Podman machine goes over `ssh://`, using an identity file under `~/.local/share/containers/podman/machine/`, a path the framework's blanket `~/` read denial already covers.
The machine's actual API socket lives elsewhere, under `$TMPDIR/podman/<machine>-api.sock` (`podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}'` prints the exact path), not under `~/.local/share` as the ssh identity path might suggest.

The supported route is the [container gateway](../../tools/container-gateway/README.md).
It runs outside the sandbox, holds the only connection to the real daemon socket, and exposes two policy-checked sockets of its own under `<project>/.apache-magpie-local/run/`.
`CONTAINER_HOST` and `DOCKER_HOST` point at `podman.sock` and `docker.sock` in that directory, only those two sockets are ever added to `allowUnixSockets`, and a `SessionStart` hook starts the gateway when a session begins.
See [Container gateway](secure-agent-setup.md#container-gateway) in the setup guide for the full install.

### Fix

| Error line | Cause | Action |
|---|---|---|
| `failed to read identity "…/machine/machine": operation not permitted` | `CONTAINER_HOST` / `DOCKER_HOST` are unset, so the CLI fell back to its default connection instead of the gateway | Add the reference `env` block below to `.claude/settings.local.json` |
| `dial unix /.//.apache-magpie-local/run/podman.sock` — note the leading `/.//` | `CONTAINER_HOST` / `DOCKER_HOST` use a project-relative `unix://./…` value, which the CLIs do **not** resolve against the cwd | Use the absolute `unix:///<project>/…` spelling in the `env` block below |
| `dial unix /<project>/.apache-magpie-local/run/podman.sock: connect: no such file or directory` | The gateway is not running for this project | Run `~/.claude/scripts/container-gateway-hook.sh start` from a terminal, or check `<project>/.apache-magpie-local/run/container-gateway.log` for why it did not start |
| `dial unix /<project>/.apache-magpie-local/run/podman.sock: connect: operation not permitted` | The gateway is running but its socket is missing from `sandbox.network.allowUnixSockets` | Add both gateway sockets as absolute paths, per [Container gateway](secure-agent-setup.md#container-gateway) |
| `no podman or docker backend found; nothing to serve` in the gateway log, while `podman` works by hand | On macOS the gateway asked `podman machine inspect` for the socket path, and that command renders it from the **caller's** `TMPDIR` | Update the framework: discovery now also probes `getconf DARWIN_USER_TEMP_DIR`/`podman/`, so a hook whose `TMPDIR` differs from the machine's still finds the socket |

```jsonc
// .claude/settings.local.json (gitignored, per machine — NOT committed)
{
  "env": {
    "CONTAINER_HOST": "unix:///<project>/.apache-magpie-local/run/podman.sock",
    "DOCKER_HOST": "unix:///<project>/.apache-magpie-local/run/docker.sock"
  }
}
```

A `unix://` URL's authority is parsed as a host component, so every relative spelling misses the socket — `unix://./x` dials `/.//x`, `unix://x` dials `/x/`, and `unix:x` dials `//`.
`unix:///absolute/path` is the only form that connects (verified against podman 6.1.0), which is why this block is per-machine rather than committed.

#### `403 container-gateway: …`

A request that reaches the gateway but fails its policy comes back as `403`, and the CLI prints the message verbatim, for example `container-gateway: bind-mount: /Users/you/.ssh is outside the allowed roots (…); see docs/setup/sandbox-troubleshooting.md#docker--podman-command-fails-with-a-socket-error`.
The message names the rule that refused the request, and it points back at this very catalog entry.
The full create-time refusal table lives in [`tools/container-gateway/README.md` → What the policy refuses](../../tools/container-gateway/README.md#what-the-policy-refuses).
Adjust the request rather than widening the sandbox: a `403` from the gateway is the policy working as intended, not a sandbox misconfiguration.

### Notes

- The gateway's `docker`-backend discovery on macOS reads the current `docker context`.
  Colima's socket lives under `~/.colima/<profile>/docker.sock`, and a Colima context already set as active is picked up the same way as Docker Desktop's, with no Colima-specific configuration.
- The gateway's `podman`-backend discovery on Linux reads `$XDG_RUNTIME_DIR/podman/podman.sock` directly, which is rootless Podman's default socket location, again with no separate configuration.
- Do **not** widen `allowRead` to `~/.docker/**`.
  The directory holds auth tokens and saved contexts, and the whole point of the framework's `Read(~/.docker/**)` denial is to keep those out of the agent's reach.
- Docker Desktop's CLI binary and plugins still need explicit read access, independently of which socket the CLI talks to.
  `docker` on `PATH` is `~/.docker/bin/docker`, a symlink into `/Applications/Docker.app`, and `docker compose` / `docker buildx` are separate binaries under `~/.docker/cli-plugins/`.
  Add `~/.docker/bin/` and `~/.docker/cli-plugins/` to `sandbox.filesystem.allowRead` as exact paths rather than the broader `~/.docker/**`, or install `docker` via Homebrew, whose CLI lives on a normal `PATH` directory outside `~/.docker` and needs no extra allow.
- If no Podman machine exists, or it is stopped, run `podman machine init` / `podman machine start` from your own terminal, outside the sandbox.
  Verify the result from outside the sandbox too: per the Symptom note above, `podman machine list` run inside the sandbox reports an empty table regardless of the machine's real state.
- When only Podman is installed, the gateway still serves the `docker` CLI.
  `DOCKER_HOST` points at the gateway's `docker.sock`, which relays to whichever backend it found, so `docker ps` and friends work through Podman's Docker-compatible API alone.
- For CI / image-build workflows that run inside an adopter repo and need a wider gateway configuration than the reference default (e.g. `--extra-bind-root` on `container-gateway serve`, or any other project-specific sandbox allowance), prefer project scope (`.claude/settings.local.json` in the adopter) over user scope.
  That keeps the framework's user-scope reference minimal and makes the widening visible to whoever audits the adopter's repo — a rule that holds for any workflow-specific sandbox widening, not just this one.

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

For the **unset / overwritten** and **outside `allowWrite`** cases
above, point `TMPDIR` back at a directory inside the writable tree
for whatever cleared it — the `env -i` wrapper, the Makefile, the
login shell — at that call site. `/tmp/claude-<uid>/` is already
inside the sandbox's writable set, so nothing needs widening.

For the **shared-session-root** case there is currently **no fix**.
Setting `env.TMPDIR` in the project's `.claude/settings.local.json`
— which this entry recommended until recently — does not work:

```jsonc
// <adopter-repo>/.claude/settings.local.json
{
  "env": {
    // Accepted, and silently without effect. Do not rely on it.
    "TMPDIR": "/tmp/claude-<uid>/<path-slug>/shared"
  }
}
```

Claude Code sets `TMPDIR` itself when it builds the sandbox, to the
shared session root `/tmp/claude-<uid>`, and that assignment wins
over the settings value. The override is specific to `TMPDIR`:
other `env` keys from the same file do take effect, so a session
can show a live `CONTAINER_HOST` from project settings and a
`TMPDIR` that ignores them. The symptom of having tried is a
directory that exists, is named exactly as configured, and stays
empty for the life of the setting.

In practice the collision risk this case describes is mostly
absorbed elsewhere: each session also gets its own scratchpad
under `/tmp/claude-<uid>/<path-slug>/<session-id>/`, which is
per-project and per-session by construction. Prefer that for
anything a skill or tool writes; treat a bare `$TMPDIR` as shared
with every other project on the machine, and make temp filenames
unique rather than assuming the directory is yours.

### Notes

- **`env` is applied at session start.** For the keys that are
  honored, a change does not take effect in the session that makes
  it; restart, then confirm with the doctor skill's
  *project-scratch* probe. `TMPDIR` is not one of those keys — see
  the Fix above.
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

## `gh` fails with TLS `OSStatus -26276` or `HTTP 401` inside the sandbox

### Symptom

Either of:

```text
Get "https://api.github.com/user": tls: failed to verify certificate: x509: OSStatus -26276
HTTP 401: Requires authentication (https://api.github.com/graphql)
```

…from a `gh` call made through the Bash tool, while `gh auth status`
reports a healthy login and the very same command succeeds in a
terminal. Which of the two appears depends on the call: on macOS the
TLS variant is the common one; the 401 is the keyring token read
failing silently, so `gh` sends the request unauthenticated.

### Root cause

`gh` is a Go binary. On macOS Go hands TLS certificate verification
to Security.framework, and `gh` reads its token from the keychain
through the same framework. Both go over mach services (`trustd`,
`securityd`) that the Seatbelt profile does not expose, so
verification fails with `errSecServiceNotAvailable` (`-26276`) and
the token read returns nothing. The CONNECT proxy and the certificates
are fine — Python's `urllib` through the same proxy returns 200 — and
nothing on the Go side can route around the framework: the Homebrew
`gh` does not embed Go's fallback root store, so
`GODEBUG=x509usefallbackroots=1` is inert, and Go ignores
`SSL_CERT_FILE` on darwin. Claude Code exposes no setting for mach
services (`enableWeakerNetworkIsolation` is about the proxy, not the
trust store).

That is why the framework reference runs `gh` **outside** the sandbox
with `sandbox.excludedCommands: ["gh *"]`
([`secure-agent-setup.md`](secure-agent-setup.md#the-frameworks-own-claudesettingsjson)).
The symptom above means *this particular* `gh` did not get excluded.
The exclusion is decided **per Bash invocation**, and it holds only
when **every segment** of the command is `cd …` or `gh …`. Measured on
macOS 26 with Claude Code 2.1.278:

| Command shape | Runs outside the sandbox? |
|---|---|
| `gh api user --jq .login` | yes |
| `cd /repo && gh pr view 12 --json title` | yes |
| `gh pr view 12 --json title && gh pr diff 12` | yes |
| `gh api … \| head -1` | no |
| `gh api … > "$TMPDIR/out.json"` (any redirection, even alone) | no |
| `x=$(gh api …)` | no |
| `for n in 1 2; do gh pr view "$n"; done` | no |
| `sh -c 'gh …'`, `uv run … vetted-op-read …` (`gh` as a child process) | no |

Claude Code's documentation says the exclusion list is matched
against each `&&` / `|` / `;` segment independently; in practice a
single non-`gh` segment, or any redirection, keeps the whole
invocation inside the sandbox.

### Fix

This one is not a settings widening — there is nothing to widen.
Two parts:

1. Keep `gh` on the exclusion list (already in the framework
   reference):

   ```jsonc
   // ~/.claude/settings.json (or the adopter's .claude/settings.json)
   {
     "sandbox": {
       "excludedCommands": ["gh *"]   // gh needs the keychain + Security.framework; run it outside
     }
   }
   ```

2. Shape every `gh` invocation so the exclusion applies:

   - make `gh` the only kind of command in the invocation — `cd … &&
     gh …`, or several `gh … && gh …`;
   - do the post-processing with `gh`'s own `--jq` / `--template`
     instead of a pipe into `jq`, `head`, or `python3`;
   - batch many reads into **one** GraphQL query with aliased fields
     (`a: pullRequest(number: 1){…} b: pullRequest(number: 2){…}`)
     rather than a loop;
   - for writes that need a JSON body, write the file in a separate
     non-`gh` call and pass it with `--input file.json` — *reading* a
     file is fine, only shell redirection breaks the match;
   - to capture a large payload to a file, move the redirection
     *inside* `gh` with a shell alias, so the Bash command stays a
     single `gh …` part. Import once from a YAML file
     (`gh alias import aliases.yml`):

     ```yaml
     tofile: |-
       !out="$1"; shift
       case "$out" in
         *..*) echo "gh tofile: refusing a path containing ..: $out" >&2; exit 2 ;;
         /private/tmp/claude*|/tmp/claude*|"$PWD"/*|[!/]*) ;;
         *) echo "gh tofile: refusing to write outside the working directory or the Claude scratch tree: $out" >&2; exit 2 ;;
       esac
       exec gh "$@" > "$out"
     ```

     then `gh tofile "$TMPDIR/pr.json" pr view 12 --json title,body`
     runs excluded and a separate non-`gh` call reads the file. The
     path guard matters: the alias runs *outside* the sandbox, so
     without it any `gh tofile` could overwrite any file the user can
     write. This is tracked upstream as
     [anthropics/claude-code#95532](https://github.com/anthropics/claude-code/issues/95532);
     drop the alias once a fixed release no longer treats a
     redirection as a non-matching part;
   - for a loop or pipeline that genuinely cannot be reshaped, run
     that one call with the per-call sandbox bypass and say so (the
     [bypass-visibility hook](secure-agent-setup.md#sandbox-bypass-visibility-hook)
     makes it loud).

### Notes

- The same `-26276` hits every other tool that verifies TLS through
  Security.framework; the framework runs `lychee` in offline mode for
  exactly this reason (see the annotated `.claude/settings.json` in
  [`secure-agent-setup.md`](secure-agent-setup.md#the-frameworks-own-claudesettingsjson)).
- Any wrapper that spawns `gh` as a child — `sh -c`, a Makefile
  target, the `vetted-ops` dispatcher — is matched on *its* command
  string, not on `gh`. Add the wrapper's invocation to
  `excludedCommands` too, alongside its `permissions.allow` rule; the
  two gates are independent and both key on the command string.
- The `Monitor` tool runs its command sandboxed and has no bypass
  flag, so a `gh`-based CI poll loop is blind. Use the Bash tool with
  `run_in_background` plus the per-call bypass instead.
- Do not work around this by dumping the token (`gh auth token`) into
  `GH_TOKEN`; the framework reference keeps that command in
  `permissions.deny` on purpose.
- A different symptom with a similar smell — the excluded `gh` *works*
  but *prompts* on every call, `gh pr view` included — is a
  permissions problem, not a sandbox one: a catch-all `Bash(gh *)` in
  `permissions.ask` (any scope; ask rules merge from every settings
  file). Claude Code evaluates deny, then ask, then allow, and a
  matching ask rule prompts even when a more specific allow rule also
  matches. Replace the catch-all with the explicit write-subcommand
  list from the reference `.claude/settings.json`; the verify skill's
  check 11b fails on it and the doctor's gh probe warns.
- Linux / bubblewrap is not measured here. Go uses its own root store
  on Linux, so the TLS half does not apply; the keyring half depends
  on which credential helper `gh` is configured with.

---

## `prek` or `uv` not found, or cannot write its cache, inside the sandbox

### Symptom

```console
$ prek run --all-files
(eval):1: command not found: prek

$ uv run pytest
(eval):1: command not found: uv
```

A binary reached by absolute path gets further and then fails
writing its cache or state under `~/.cache/` or
`~/.local/share/uv/`.
`git config --global --get <key>` printing nothing inside the
sandbox, while it prints the value in a terminal, is the same
failure on `~/.gitconfig`.

### Root cause

Claude Code filesystem allowlist. The framework's committed
`.claude/settings.json` lists `~/.local/bin/`, `~/.local/share/uv/`,
`~/.cache/`, `~/.gitconfig` and `~/.config/git/` under
`sandbox.filesystem.allowRead` (and the first three writable under
`allowWrite`), carving them out of `denyRead: ["~/"]`. The harness
does not apply those project-scope entries: the effective sandbox
denies every one of them, while the same kind of entry in
`.claude/settings.local.json` or `~/.claude/settings.json` takes
effect. It is the behaviour behind
[issue #197](https://github.com/apache/magpie/issues/197), where the
committed `"."` entry was dropped the same way. The Claude Code
documentation says `allowRead` merges across every scope, so treat
this as harness behaviour that may change, not as a contract.

### Fix

Re-run the project-root helper. It writes the dev-tool paths, as
absolute paths, into the gitignored project-local file, beside the
project root it already adds:

```bash
~/.claude/scripts/sandbox-add-project-root.sh --all-worktrees
```

```jsonc
// <adopter-repo>/.claude/settings.local.json (written by the helper)
{
  "sandbox": {
    "filesystem": {
      "allowRead": [
        "/home/<you>/code/<repo>",
        "/home/<you>/.gitconfig",          // git's user.name / user.email
        "/home/<you>/.config/git",         // git's per-host config
        "/home/<you>/.cache",              // uv / prek / ruff / mypy caches
        "/home/<you>/.local/share/uv",     // uv's tool venvs (prek)
        "/home/<you>/.local/bin"           // uv-installed entry points
      ],
      "allowWrite": [
        "/home/<you>/code/<repo>",
        "/home/<you>/.cache",
        "/home/<you>/.local/share/uv"
      ]
    }
  }
}
```

The helper writes that file only from outside the sandbox (it is in
the harness's write-deny set). The harness re-reads it without a
restart: the next sandboxed command already sees the new paths.
Confirm with `prek --version`, or with the doctor skill's
*dev-tools* probe.

### Notes

- The helper deliberately does **not** mirror the whole committed
  `allowRead`. That list also names credential paths
  (`~/.config/gh/`, `~/.config/apache-magpie/`, `~/.gnupg/`), which
  the same harness behaviour currently keeps out of sandboxed Bash.
  Re-open one of those only for the tool that needs it, per the
  entries above.
- `--no-tool-paths` keeps the old behaviour (project root only) for
  an operator who does not run `prek` or `uv` in agent sessions.
- Do not reach for `dangerouslyDisableSandbox: true` to run `prek`:
  its hooks execute code from the working tree, and the sandbox is
  what keeps a compromised hook away from the rest of `$HOME`.

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
