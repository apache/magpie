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
  - [Test cannot bind to a localhost port](#test-cannot-bind-to-a-localhost-port)
    - [Symptom](#symptom-1)
    - [Root cause](#root-cause-1)
    - [Fix](#fix-1)
    - [Notes](#notes-1)
  - [Docker / Podman command fails with a socket error](#docker--podman-command-fails-with-a-socket-error)
    - [Symptom](#symptom-2)
    - [Root cause](#root-cause-2)
    - [Fix](#fix-2)
    - [Notes](#notes-2)
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

### Fix

Add the SSH agent socket directories to `sandbox.filesystem.allowRead`:

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
  `~/.gnupg/gpg-agent.conf`), no extra entry is needed — the
  framework reference already includes `~/.gnupg/` and
  `/run/user/*/gnupg/`, which cover the gpg-agent SSH socket
  (`S.gpg-agent.ssh`) on both platforms.
- If you use **Secretive** (an alternative macOS Yubikey
  agent), the socket lives under
  `~/Library/Group Containers/<bundle>/socket.ssh`; add that
  specific path to `allowRead` instead of the launchd glob.
- Do **not** widen `allowRead` to `/private/tmp/**` — that opens
  the entire system temp directory, which other processes use for
  arbitrary files including credentials. Stay specific.

---

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

### Root cause

The runtime CLI talks to its daemon via a unix-domain socket. The
framework's reference `~/.claude/settings.json` has
`Read(~/.docker/**)` in `permissions.deny` (to keep the agent
from reading Docker credentials stored under `~/.docker/config.json`)
and lists `~/.docker` in the broader filesystem `denyRead` set.
Both block the socket file under `~/.docker/run/docker.sock`,
which is where Docker.app for Mac drops its socket.

For Colima the socket lives under `~/.colima/...` (not currently
covered by any allow / deny in the framework reference, so it
works by default), and for rootless Podman it lives under
`$XDG_RUNTIME_DIR/podman/...` (also not covered → works). The
case that fails is specifically Docker.app on macOS plus the
generic `~/.docker` denial.

### Fix

Allow Bash subprocesses to read the *socket file* without opening
the `~/.docker/` directory generally:

```jsonc
// ~/.claude/settings.json
{
  "sandbox": {
    "filesystem": {
      "allowRead": [
        // ...existing entries...
        "~/.docker/run/docker.sock",                    // Docker.app for Mac socket
        "~/.colima/default/docker.sock",                // Colima default socket (defensive; usually not blocked)
        "/var/run/docker.sock"                          // Linux daemon socket (root-managed install)
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
