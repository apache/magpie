---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-setup-isolated-setup-doctor
description: |
  Probe the secure-agent setup for in-session functional
  restrictions that block legitimate workflows. Three live
  probes — SSH agent / Yubikey reachability, localhost port
  binding, docker / podman runtime socket — each pointing the
  user at the matching numbered troubleshooting entry and its
  settings.json remediation (see body). Read-only — never
  modifies settings.json, never invokes the sandbox bypass.
when_to_use: |
  Invoke when the user says "doctor my sandbox", "diagnose
  sandbox friction", "why is the sandbox blocking X", "check
  whether ssh / docker / port-bind works inside the sandbox",
  or after the user reports a workflow failure that smells
  sandbox-shaped (agent unreachable, socket errors, port
  permission errors). Also a good periodic check after every
  Claude Code upgrade — the sandbox profile evolves and a
  previously-working call may have moved into deny.
capability:
  - capability:platform
  - capability:reassess
license: Apache-2.0
---

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> → adopting project's `.apache-magpie/` directory -->

# setup-isolated-setup-doctor

The **diagnostic** layer over the secure agent setup. Complements
the existing setup skills:

- [`setup-isolated-setup-install`](../setup-isolated-setup-install/SKILL.md)
  installs the secure setup.
- [`setup-isolated-setup-verify`](../setup-isolated-setup-verify/SKILL.md)
  answers *"is the secure setup **installed** correctly?"* —
  static checks on settings.json shape, hook wiring, pinned tool
  versions. Catches drift and missing pieces.
- [`setup-isolated-setup-update`](../setup-isolated-setup-update/SKILL.md)
  surfaces drift against the framework's latest.
- **`setup-isolated-setup-doctor` (this skill)** answers *"are
  common workflows **functionally** blocked by the current
  sandbox?"* — live probes of SSH agent, port binding, docker /
  podman socket. Catches over-restrictive allowlists.

Run `verify` first when the install is in question (fresh
machine, recent framework upgrade, sandbox-state surprise). Run
`doctor` when the install is known good but a workflow fails in
a sandbox-shaped way — agent unreachable, socket error, port
permission error.

Every probe maps to a numbered entry in
[`docs/setup/sandbox-troubleshooting.md`](../../docs/setup/sandbox-troubleshooting.md);
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
  user may have one of three independent restrictions, or all
  three, and discovering them one re-run at a time is annoying.
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
  [`docs/setup/sandbox-troubleshooting.md`](../../docs/setup/sandbox-troubleshooting.md).
  Do not paraphrase the remediation — the catalog is the single
  source of truth.

## The 3 probes

The current set covers the three failure modes the catalog
documents. New probes are added when new entries land in the
catalog; the two stay in lock-step.

### Probe 1 — SSH agent / Yubikey reachable

Tests whether `ssh-agent` is reachable from inside the sandbox.
Failure mode: `SSH_AUTH_SOCK` is passed through `claude-iso`'s
env whitelist but the socket file is not in
`sandbox.filesystem.allowRead`, so the agent's `ssh` /
`git push` subprocesses cannot `connect(2)` to the socket.

**Command:**

```bash
if [ -z "$SSH_AUTH_SOCK" ]; then
  echo "PROBE: ssh-agent → ⊘ (SSH_AUTH_SOCK not set in env)"
elif [ ! -S "$SSH_AUTH_SOCK" ]; then
  echo "PROBE: ssh-agent → ✗ (socket file at SSH_AUTH_SOCK not stat-able from inside sandbox)"
  echo "       SSH_AUTH_SOCK=$SSH_AUTH_SOCK"
else
  ssh-add -l > /tmp/ssh-add.out 2>&1; rc=$?
  case "$rc" in
    0) echo "PROBE: ssh-agent → ✓ ($(wc -l < /tmp/ssh-add.out | tr -d ' ') identities listed)" ;;
    1) echo "PROBE: ssh-agent → ✓ (agent reachable, no identities configured)" ;;
    2) echo "PROBE: ssh-agent → ✗ (agent unreachable: $(head -1 /tmp/ssh-add.out))" ;;
    *) echo "PROBE: ssh-agent → ⚠ (unexpected rc=$rc: $(head -1 /tmp/ssh-add.out))" ;;
  esac
fi
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
[`docs/setup/sandbox-troubleshooting.md` — SSH agent / Yubikey appears unreachable from inside the sandbox](../../docs/setup/sandbox-troubleshooting.md#ssh-agent--yubikey-appears-unreachable-from-inside-the-sandbox).

### Probe 2 — Localhost port bind

Tests whether a process inside the sandbox can bind to a
loopback port AND then talk to itself over loopback. The
failure mode the catalog documents is the second half (egress
proxy blocks `127.0.0.1`).

**Command:**

```bash
python3 - <<'PY' 2>&1 || true
import socket, urllib.request, threading, http.server, sys

# 1. Can we bind?
try:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.listen(1)
except OSError as e:
    print(f"PROBE: localhost-bind → ✗ (bind: {e})")
    sys.exit(0)

# 2. Can we GET from our own server over loopback?
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *_): pass

server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=5) as r:
        body = r.read()
    print(f"PROBE: localhost-bind → ✓ (bound + loopback GET → HTTP {r.status}, body={body!r})")
except Exception as e:
    print(f"PROBE: localhost-bind → ✗ (bind ok, loopback GET: {type(e).__name__}: {e})")
finally:
    server.shutdown()
    s.close()
PY
```

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ bound + loopback GET → HTTP 200` | Pass | Both bind and loopback HTTP work. |
| `✗ bind: ...` | Fail | The sandbox blocks `bind(2)` on `127.0.0.1`. Rare. |
| `✗ bind ok, loopback GET: ...` | Fail | Bind works but the sandbox egress proxy refuses `127.0.0.1` as a destination. Common shape. |

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — Test cannot bind to a localhost port](../../docs/setup/sandbox-troubleshooting.md#test-cannot-bind-to-a-localhost-port).

### Probe 3 — Docker / Podman runtime socket

Tests whether the runtime CLI can talk to its daemon. Run for
each of `docker` / `podman` that is on `PATH`; ⊘ each that is
not installed (this is not a sandbox failure, just an absent
prerequisite).

**Command:**

```bash
for rt in docker podman; do
  if ! command -v "$rt" > /dev/null 2>&1; then
    echo "PROBE: ${rt}-runtime → ⊘ ($rt not on PATH)"
    continue
  fi
  out=$("$rt" info > /dev/null 2>&1 && echo ok || echo "fail:$?")
  case "$out" in
    ok)
      echo "PROBE: ${rt}-runtime → ✓ (${rt} info returned)" ;;
    fail:*)
      err=$("$rt" info 2>&1 >/dev/null | head -2 | tr '\n' ' ')
      echo "PROBE: ${rt}-runtime → ✗ ($out: $err)"
      ;;
  esac
done
```

**Interpretation:**

| Result | Status | Meaning |
|---|---|---|
| `✓ <rt> info returned` | Pass | The CLI reached the daemon successfully. |
| `✗ fail:1: Cannot connect to the Docker daemon …` | Fail | Daemon socket not readable from inside the sandbox. |
| `✗ fail:1: connect: permission denied` | Fail | Same root cause, different stderr (Linux variant). |
| `⊘ <rt> not on PATH` | Skip | Runtime not installed; not a sandbox restriction. |

**On ✗ → remediation:**
[`docs/setup/sandbox-troubleshooting.md` — Docker / Podman command fails with a socket error](../../docs/setup/sandbox-troubleshooting.md#docker--podman-command-fails-with-a-socket-error).

## After the report

If every probe is ✓ or ⊘:

> All three probes pass (or are not applicable). The sandbox is
> not currently blocking the known failure modes catalogued in
> `docs/setup/sandbox-troubleshooting.md`. If you hit a different
> sandbox-shaped failure, follow the catalog's *Adding a new
> entry* section and (optionally) extend this skill with a fourth
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
[`docs/setup/sandbox-troubleshooting.md`](../../docs/setup/sandbox-troubleshooting.md):

1. Report the fail with the literal probe command + exit code +
   stderr.
2. Suggest the user add a new entry to the catalog per its
   *Adding a new entry* section (symptom verbatim, root cause,
   fix, notes).
3. Once the catalog has the new entry, extend this skill with a
   matching probe in the same shape so the next doctor run
   catches it automatically.

## Extending the skill with a new probe

When the catalog grows a new entry, add a matching probe section
following the shape above:

1. **Command** — a short, deterministic, side-effect-free
   one-liner (or short Python heredoc) that triggers the failure
   mode reliably.
2. **Interpretation** — a 3–5-row table mapping result strings
   to ✓ / ✗ / ⊘ / ⚠.
3. **On ✗ → remediation** — a direct link to the matching
   section of `docs/setup/sandbox-troubleshooting.md`.

Keep probes narrowly scoped: each probe tests **one** failure
mode, not a bundle. A probe that conflates two restrictions
makes the report ambiguous when the result is ✗.
