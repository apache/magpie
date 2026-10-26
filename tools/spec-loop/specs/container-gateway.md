<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Container gateway (podman / docker inside the sandbox)
status: experimental
kind: feature
mode: infra
source: >
  MISSION.md § Privacy, security and supply-chain integrity ("Layered
  sandbox by default"); RFC-AI-0004 Principle 2 (secure sandbox by
  default) and RFC-AI-0003 § 4.4 (egress-allowlist gateway).
  Implemented in tools/container-gateway/, a SessionStart/SessionEnd/
  PreToolUse hook in tools/agent-isolation/, the reference .claude/settings.json,
  tools/sandbox-lint/expected.json, the setup-isolated-setup-doctor /
  -verify / -install skills, docs/setup/secure-agent-setup.md and
  docs/setup/sandbox-troubleshooting.md.
acceptance:
  - A sandboxed `podman` or `docker` command works with the OS sandbox
    fully on, with no daemon socket, machine identity file or CLI in
    `sandbox.filesystem.allowRead` / `allowUnixSockets` beyond the
    gateway's own sockets.
  - Every container, pod, volume and network created through the
    gateway carries the project label, and every list / inspect /
    exec / logs / stop / remove / prune / connect call is restricted
    to resources carrying that label.
  - A create request that asks for privileged mode, extra
    capabilities, devices, a host or foreign namespace, an
    unconfined security option, or a bind mount outside the project
    root and any `--extra-bind-root` is refused with HTTP 403 and a
    one-line reason.
  - A create, exec, update or build request carrying a field or query
    parameter the gateway has not learned is refused with HTTP 403;
    the create body, the exec body, the update body and the build
    query are all allow-lists.
  - Containers created through the gateway receive `HTTP_PROXY` /
    `HTTPS_PROXY` / `NO_PROXY` pointing at the egress gateway when it
    is reachable; the `require` mode refuses creation when it is not.
  - Each backend (Podman machine, Docker Desktop, Linux docker.sock,
    Linux rootless podman) is optional; the gateway serves whichever
    exist and exits quietly when none does. The doctor reports ⊘, not
    ✗, in that case.
---

# Container gateway (podman / docker inside the sandbox)

## What it does

Lets sandboxed shell commands drive `podman` and `docker` without
weakening the sandbox. Today the only ways to use a container runtime
from the sandbox are to exclude the CLI from the sandbox (upstream
Claude Code guidance for `docker`) or to allow the daemon socket in
`sandbox.network.allowUnixSockets`. Both hand the agent the daemon,
and the daemon is root-equivalent over everything it can mount: the
default Podman machine on macOS mounts `/Users`, `/private` and
`/var/folders` read-write, so its API socket is a bind-mount away from
`~/.ssh`. Upstream's own sandbox documentation names the docker socket
as the canonical example of an `allowUnixSockets` entry that grants
host access.

The container gateway is a per-project policy proxy in front of the
daemon socket, in the same family as the egress gateway: it runs
outside the sandbox, listens on unix sockets the sandbox may reach, and
enforces a default-deny policy on the Docker-compatible API that both
CLIs speak. Three properties fall out of the policy:

1. **Containers only.** The agent reaches the daemon exclusively through
   the API surface the gateway forwards, and the gateway strips every
   request shape that would turn a container into host access.
2. **This project's containers only.** Every resource the gateway
   creates is labelled with the project; every read or act call is
   filtered to that label. Two projects on one machine share a daemon
   and see disjoint worlds.
3. **Same egress policy as the shell.** Containers get the egress
   gateway as their HTTP proxy, so tools that honour proxy variables
   are bound by the same host allow-list as sandboxed commands. This is
   a friction layer, not a wall: a raw socket from inside a container
   bypasses it, exactly as RFC-AI-0004 says of the permission layer.

## Where it lives

- `tools/container-gateway/` — the tool: `pyproject.toml` (stdlib-only
  runtime, `dev` group for pytest / ruff / mypy), `src/container_gateway/`
  (`__main__.py` CLI — serve / stop / status, `daemon.py` run directory,
  pid file, sockets, process lifetime and the git-common-dir anchor check,
  `layers.py` personal-layer resolution, `relay.py` and `http.py`
  unix-socket HTTP relay, `routes.py` API path mapping, `decisions.py` /
  `policy.py` / `policy_shape.py` pure request/response policy,
  `backends.py` discovery, `labels.py` project identity), `tests/`, `README.md` (how-to) and `tool.md`
  (contract). Capability: `substrate:sandbox`. Harness: agnostic.
- `tools/agent-isolation/container-gateway-hook.sh` — Claude Code
  `SessionStart` (`start`) / `SessionEnd` (`stop`) / `PreToolUse` on
  `Bash` (`ensure`, before a `docker` / `podman` command) hook, installed to
  `~/.claude/scripts/` by `setup-isolated-setup-install` like the other
  hook scripts. Other harnesses start the gateway by hand or from their
  wrapper; the hook is a convenience, not the mechanism.
- `.claude/settings.json` (reference, and the copy in
  `docs/setup/secure-agent-setup.md`): `env.CONTAINER_HOST`,
  `env.DOCKER_HOST`, `sandbox.network.allowUnixSockets` entries for the
  two gateway sockets. `tools/sandbox-lint/expected.json` mirrors them.
- `docs/setup/sandbox-troubleshooting.md` → *Docker / Podman command
  fails with a socket error*: rewritten to route through the gateway;
  `plugins/magpie-setup/skills/isolated-setup-doctor/SKILL.md` probe 3
  and `isolated-setup-verify` gain gateway checks;
  `tools/skill-evals/evals/setup-isolated-setup-doctor/` fixtures.
- `docs/rfcs/RFC-AI-0004.md` Principle 2 architecture table: a
  *socket gateways* row naming the egress gateway and the container
  gateway, cross-referencing RFC-AI-0003 § 4.4.

## Behaviour & contract

### Process model

One gateway process per project, keyed by the project root. It listens
on `<run-dir>/podman.sock` (libpod + compat API, for the podman CLI) and
`<run-dir>/docker.sock` (compat API, for the docker CLI), where
`<run-dir>` is the `run/` directory of the personal config layer:
`<project>/.apache-magpie-local/run` for a project that has adopted
Magpie, `<git-common-dir>/apache-magpie/run/<worktree-id>` for one that has not (inside
the git directory, never the working tree; for a linked worktree the
common directory is the main checkout's `.git`, which is then the trust
anchor the run-directory guards walk from). `<worktree-id>` is `main`
for the main working tree and the linked worktree's `.git/worktrees/<name>`
name, validated against `[A-Za-z0-9._-]+` (anything else is refused), so
every worktree has its own gateway. `serve` refuses a socket path over
the 103-byte macOS `sun_path` limit before creating anything. Outside a git repository an
unadopted project has no default and `serve` requires `--run-dir`. The
run directory and the personal layer are never accepted as bind-mount
sources. In a linked worktree of an adopted project, which reads its main
checkout's `.apache-magpie-local/` when it has none of its own, both
that directory and the worktree's own are excluded; the run directory
itself stays per worktree and never falls back to the main checkout.
Every setting that names a gateway socket needs its **absolute**
path. `CONTAINER_HOST` / `DOCKER_HOST` do **not** honour a
project-relative `unix://./…` value: a `unix://` URL's authority is
parsed as a host component, so `unix://./x` dials `/.//x`,
`unix://x` dials `/x/`, and `unix:x` dials `//` (verified against
podman 6.1.0). `sandbox.network.allowUnixSockets` has no relative
form either. The committed baseline therefore carries **neither** —
no gateway `env` block and no gateway-socket entry. The operator
adds both, with absolute paths, to the gitignored, per-project
`.claude/settings.local.json` by hand (the block is in
[Container gateway](../../../docs/setup/secure-agent-setup.md#container-gateway)
in the setup guide, and `setup-isolated-setup-install` Step L proposes
it as a settings diff); `/magpie-setup:setup config` does not write it. The macOS limit of 104 bytes on a socket path is
checked at start and reported.

The gateway must run **outside** the sandbox: it connects to the real
daemon socket, which the sandbox denies by design, and it also has to
`bind()` its own two gateway sockets, an operation the sandbox refuses
unconditionally regardless of the destination path — there is no sandbox
configuration under which the gateway process itself could run inside the
sandbox it exists to let other processes reach through. Start-up order:
discover backends, refuse to start when the run directory is
world-writable, bind the gateway sockets with mode `0600`, write a pid
file, serve. It exits on `SessionEnd`, on `SIGTERM`, or after an idle
timeout (default 4 h) as a backstop for sessions that end without the
hook firing. A second start for the same project is a no-op when the
pid file names a live process.

The gateway can also exit while a session still needs it — the idle timeout, another
session on the same project ending (its `SessionEnd` stops the one
gateway both share), a crash — so the hook's `ensure` action, wired as a
`PreToolUse` hook on `Bash`, starts it again before a `docker` /
`podman` command finds it gone. `ensure` leaves at once for a command
naming neither CLI, and judges the directory the session started in —
`CLAUDE_PROJECT_DIR`, which Claude Code sets on every hook and a
settings `env` entry cannot override — never the payload's `cwd`, which
follows the agent's `cd` and, judged from elsewhere, would leave the
session project's write grants uncounted; without the variable it does
nothing. It runs every check `start`
runs before it executes anything (so on-demand start reaches nothing
`start` would refuse),
asks the gateway's `status` whether it already serves, and otherwise
starts it and waits up to five seconds for it to serve, so the command
does not race the start. It never blocks the command.
"Serve" means `status` reports a serving backend, not merely a live pid:
the gateway takes its pid lock before it discovers backends and binds
its sockets, so waiting on the pid let the command race the bind. The
wait ends early once the gateway has come up and exited again (no
backend) or never came up (#1826). The `PreToolUse` wiring carries no
`if` filter, which missed `docker-compose`, `podman-compose` and
path-qualified CLIs; the script's own check leaves in about 10 ms.

### Hook trust model

The hook runs outside the sandbox, so everything it executes — the
interpreter, the standard library under it and the gateway source — must
live where neither the repository being opened nor a sandboxed command,
which runs without a prompt, can write; otherwise sandboxed code planted
there would run unsandboxed at the next session start (#1784).

- **Writable roots.** A path is refused when it resolves, through every
  symlink hop, under the project root, `~/.cache`, `~/.local`,
  `/tmp/claude*`, `/private/tmp/claude*`, `$CLAUDE_CODE_TMPDIR`, or any
  `sandbox.filesystem.allowWrite`, `permissions.additionalDirectories` or
  `Edit` / `Write` allow-rule path in the user, project, local or managed
  settings (relative entries resolved against their own settings root;
  an entry with `..` refuses everything). In a linked worktree the main
  checkout and its settings count too. A write grant over a system or
  package-manager location (`/usr`, `/opt`, `/Library`, …) refuses the
  gateway outright. A settings path that is not a regular file refuses
  the start without being opened, so a planted FIFO cannot stall the
  hook (#1826).
- **Interpreter.** Never looked up on `PATH`. Candidates, in order: an
  operator pin in `~/.claude/scripts/container-gateway/python`, fixed
  Homebrew and system locations, then uv-managed CPython under
  `~/.local/share/uv/python` (newest first), the one exemption from the
  `~/.local` refusal, holding only for a real, unlinked directory and only
  while no settings scope grants writes over it; the first 3.11+
  interpreter outside every writable root wins. A virtualenv or launcher
  stub is never run, `<prefix>/lib/python3.X` must be a real directory,
  and every symlink in the standard library and the libpython beside it
  must stay inside the prefix or pass only through system locations at
  each step. It runs by its canonical path with `-I -S` and a one-line
  bootstrap that puts the source on `sys.path`, so no `PYTHON*`
  variable, site-packages or the opened project reaches it (#1769, #1784).
  `container_gateway stop` recognises that bootstrap command line
  (`HOOK_BOOTSTRAP`, kept identical to the hook by a test) as well as the
  `-m` form.
- **Source.** `$MAGPIE_CONTAINER_GATEWAY_SRC` (absolute, resolved once)
  or `~/.claude/scripts/container-gateway/src`, judged file by file and
  refused if it holds a symlink; a copy inside the repository, an
  `.apache-magpie/` snapshot included, is never used.
  `$MAGPIE_CONTAINER_GATEWAY_ARGS` is allow-listed token by token;
  anything else, notably `--extra-bind-root`, makes the hook ignore the
  whole variable.
- **Environment.** Helpers (`jq`, `git`, `readlink`, `dirname`, `find`)
  come from a fixed root-owned `PATH`; every inherited `GIT_*` variable is
  dropped; the physical cwd and the account database's home (its
  `.cache`, `.local` and user settings, whatever `$HOME` says) count as
  writable (#1789). The checkout root is also derived from the nearest
  directory holding a `.git`, and the hook refuses when git's toplevel
  differs from it or `core.worktree` is set (#1804). The shebang is
  `#!/bin/bash -p`, which ignores `BASH_ENV`, exported functions and
  `SHELLOPTS`, so the hook must be executed directly by its absolute
  path, never as `bash <path>` or through a `~` the launching shell
  expands from `$HOME`; it refuses to start when the account home cannot
  be determined (#1793). The script avoids here-strings, which bash 3.2
  backs with a temporary file and which failed open when that file could
  not be created (#1790).
- **Worktree records.** The first main checkout the hook confirms for a
  linked worktree (its `worktrees/<name>/gitdir` must point back) is
  recorded under `~/.claude/magpie-gateway/worktrees`, keyed by the
  SHA-256 of the path, and a later run deriving a different one refuses
  until the operator deletes the record, so a session cannot hide the
  main checkout's grants by rewriting `.git` metadata. The record
  directory is refused for every checkout when it is sandbox-writable or
  a symlink (#1790).
- **Known gap.** Write grants given only on the command line
  (`--add-dir`, a `--settings` file) or mid-session without saving them
  (`/add-dir`) are invisible to a hook (#1789).

### Backends

Discovery runs once, at start, not on a timer or per-request: a backend
that appears (a Podman machine started, Docker Desktop launched) after the
gateway is already serving is not picked up until the next restart. The
hook's `SessionStart` / `SessionEnd` lifecycle means this is normally a new
session away, not a standalone daemon adopters manage by hand.

Discovery, in order, all optional:

| Backend | Where the socket comes from | Serves |
|---|---|---|
| Podman machine (macOS) | `podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}'` of the default machine, run by the gateway outside the sandbox | podman.sock (libpod + compat) and docker.sock (compat) when no docker backend exists |
| Rootless podman (Linux) | `$XDG_RUNTIME_DIR/podman/podman.sock`; when absent and `podman` is installed, `podman system service --time=0` is started as a child | same as above |
| Docker Desktop (macOS) | `docker context inspect --format '{{(index .Endpoints "docker").Host}}'`, else `~/.docker/run/docker.sock` | docker.sock (compat) |
| dockerd (Linux) | `/var/run/docker.sock` | docker.sock (compat) |

The podman CLI needs the libpod API and therefore only ever talks to a
podman backend. The docker CLI talks to a docker backend when one
exists, otherwise to podman's compat API. When no backend exists the
gateway logs one line and exits 0; nothing else in the setup depends on
it running.

The gateway never reads the Podman machine's ssh identity, never uses
the `ssh://` connection, and never reads `~/.docker/config.json` or
`~/.config/containers/auth.json`: registry credentials stay outside the
sandbox and pulls are anonymous.

### Request policy

The policy is a pure function `decide(request) -> Allow | Rewrite |
Deny(reason)` over the parsed request (method, normalised path with the
`/v1.NN` or `/v5.x.y/libpod` prefix stripped, query, JSON body). It is
applied identically to the compat and libpod path families.

`Request`, `Allow`, and `decide` live in `decisions.py`, the single entry
point the relay calls per request; `decisions.py` imports from `policy.py`
(the create-time and label rules), which in turn imports from
`policy_shape.py` (the compat/libpod field tables and malformed-shape
detection). Imports are one-way only — `policy.py` never imports back from
`decisions.py`, and `policy_shape.py` never imports from either of the
other two — so the three modules form a strict layering rather than a
cycle.

**Allowed endpoint families** (each with the label rule below):
containers and pods (create, start, stop, kill, restart, pause,
unpause, wait, remove, inspect, list, logs, top, stats, exec create /
start / inspect / resize / remove, attach, archive get / put, commit, export,
rename, update, prune); images (list, inspect, history, pull / create,
build, tag, remove, prune, load, save, search); volumes and networks
(list, inspect, create, remove, connect, disconnect, prune); system
(ping, version, info, events, df); `_ping`, `/version`, `/info`.

**Denied outright**: `auth` (registry login), image push, swarm,
services, tasks, nodes, plugins, secrets, configs, distribution, session,
`system/dial-stdio`, and any path not in the allowed families. Unknown
API versions are forwarded as-is after policy; unknown paths are denied,
not forwarded.

**Label rule.** The gateway derives the project slug from the resolved
project root (the same `/`→`-` slug Claude Code uses for its scratch
tree) and:

- injects `org.apache.magpie.project=<slug>` into every container,
  pod, volume, network and build request (`Labels`, `labels`, and the
  build `labels` query parameter);
- injects `label=org.apache.magpie.project=<slug>` into the `filters`
  of every list, prune and events call, merging with filters the client
  sent;
- for every by-name or by-id call, inspects the resource first through
  the backend, checks the label, and re-issues the call by ID, so a name
  that is re-bound between the check and the act cannot escape;
- treats images differently: pull, list, inspect, history, save and
  build are allowed on any image; remove and tag are allowed only on
  images that carry the label (i.e. built or tagged through the
  gateway); image prune is restricted to dangling images carrying the
  label; load is allowed and the loaded image is not labelled.

**The create body is an allow-list.** A container or pod create body
may carry only the fields the gateway has learned — the ones it reasons
about, plus the inert ones real `docker run` / `podman run` bodies send —
and any other key, at the top level or under `HostConfig`, is refused
with `unknown-field`. A deny-list over an unbounded JSON body cannot be
right by construction: libpod's `rootfs`, `overlay_volumes`, `env_host`,
`log_configuration` and `secret_env` each turn a container into host
access on their own, and each was an `Allow` while the policy enumerated
what was forbidden. Those fields keep reasons of their own, and are
refused on a *set* value rather than on mere presence, because both CLIs
serialise the zero value of every member of their create struct on every
request. The exec body and the update body are allow-lists in the same
way. The cost of the posture — a field the gateway has not learned is
unavailable through it — is recorded under *Limits and residual risks*
in [`tools/container-gateway/tool.md`](../../container-gateway/tool.md).

**The build query is an allow-list too.** `POST /build` is a create in
disguise: its `RUN` steps execute with whatever the query asks for.
Parameters that reach the host — `volume`, `remote`, `securityopt`,
`cgroupparent`, `ulimits`, `devices`, `secrets`, `ssh`, `session`,
podman's `addcaps` / `labelopts` / `extrahosts`, a `networkmode` outside
the create path's keyword set, an `nsoptions` entry joining a host
namespace other than `user`, an `output` naming a filesystem
destination — are refused, and anything not enumerated is refused as
`denied-build-parameter`. When the egress mode is not `off` and a proxy
is resolved, `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` are merged into
`buildargs` (client-supplied values for those names dropped first) and
podman's own `httpproxy` is turned off, so property 3 covers builds.

**Denied outright by action**: `checkpoint`, `restore`, `generate` and
`play` on containers and pods — the first two name a host path for the
daemon to write, the last two hand the daemon a Kubernetes YAML it acts
on wholesale. `export` and `import` are refused as query parameters on
every route, as a backstop for a verb this policy has not enumerated.

**Create-time rules** (containers and pods; the same fields under
`HostConfig` in compat and at top level in libpod):

| Field | Rule |
|---|---|
| `Privileged` | deny |
| `CapAdd` | deny any; `CapDrop` allowed |
| `Devices`, `DeviceRequests`, `DeviceCgroupRules` | deny |
| `PidMode`, `IpcMode`, `UTSMode`, `UsernsMode`, `CgroupnsMode` | allow-list of safe values (`private`, `pod`, `auto`, `keep-id`, `nomap`, `shareable`, or unset) plus `container:<id>` when `<id>` carries the label; every other value, including `host` and any value the allow-list does not recognise, is denied |
| `NetworkMode` | allow-list of safe keywords (`default`, `bridge`, `none`, `private`, `slirp4netns`, `pasta`, `pod`, or unset) plus a named network that looks like a real network name and carries the label, checked by the relay; `host`, `container:<id>` without the label, and anything else are denied |
| `SecurityOpt` | allow-list per key: `seccomp` only `""` / `default`; `apparmor` denies only `unconfined` (any other value, including a custom profile, is allowed); `label` denies only `disable`; `no-new-privileges` allows only `""` / `true` (any other value, including `false`, is denied); `systempaths` allows only `""` (any non-empty value is denied); an unrecognised key (including `unmask`, `proc-opts`) is denied outright |
| `Sysctls`, `CgroupParent`, `Runtime`, `Isolation` | deny |
| `MaskedPaths`, `ReadonlyPaths` | deny when set to an empty list |
| `Binds`, `Mounts[type=bind]`, libpod `mounts` | source must resolve (symlinks followed, on the host) under the project root or a `--extra-bind-root`; anything else denied. `tmpfs` allowed |
| `Mounts[type=volume]`, named volumes in `Binds` | the named volume must carry the label, checked (and, for an unknown name, pre-created labelled) by the relay before the backend ever sees the create call |
| `VolumesFrom` | refused outright — sharing another container's mounts would need the same by-id label check the relay does for named volumes/networks, and the common case is already covered by a named volume |
| `PortBindings` / `publish` | allowed; an empty `HostIp` is rewritten to `127.0.0.1` |
| `Env` | proxy variables injected per the egress rule below; a client-supplied value for the same names is replaced |

Named volumes and named networks are the two by-name references the pure
`decide()` function cannot fully resolve on its own — it can validate shape
and queue the label check, but only the relay has a live connection to the
backend to actually perform it. The relay therefore inspects (and, for an
unrecognised **volume** name only, pre-creates labelled) every named volume
and network a create request references before forwarding the request, and
refuses with the same `label-check` reason a by-name act call uses when the
resource exists but does not carry the label. A named **network** that does
not already exist is refused outright — the relay never creates a network on
the caller's behalf, unlike volumes.

Because the relay trusts any volume that carries the label, a volume created
through the gateway (`POST /volumes/create`, compat or libpod) must not be
able to name a host resource: the create is refused when it names a driver
other than `local` or carries any driver options (compat `DriverOpts`, libpod
`options`), since `local` with `type=none,device=/,o=bind` is a host-root
bind. Empty options and the `local` driver, which both CLIs send on every
plain create, pass.

Rewrites are logged at debug level; denials are returned as
`403 {"message": "container-gateway: <rule> — <what to change>; see
docs/setup/sandbox-troubleshooting.md#…"}` so both CLIs print the
reason verbatim.

### Egress rule

At start the gateway resolves the egress gateway address for each
backend: the egress gateway's listen port plus the host alias the
backend gives containers (`host.containers.internal` for Podman
machine, `host.docker.internal` for Docker Desktop, the bridge or
`host-gateway` address on Linux, where the egress gateway must be
listening on that address rather than loopback). It probes the address
from the host once. Modes:

- `inject-if-available` (default): inject `HTTP_PROXY`, `HTTPS_PROXY`,
  `NO_PROXY=localhost,127.0.0.1,<host alias>` when the probe
  succeeded; otherwise create without them and log one warning per
  session. The doctor surfaces the warning.
- `require`: refuse container creation with 403 while the egress
  gateway is unreachable.
- `off`: never inject. For adopters who run their own filtering.

The proxy variables are the extent of the network control. `--network
host` is denied above; custom DNS and extra hosts are forwarded
unchanged.

### Streaming and hijacking

Logs, events, stats, pull / build progress and `wait` are streamed
response bodies (chunked or `application/vnd.docker.raw-stream`); the
relay forwards them incrementally. `exec start` and `attach` upgrade
the connection to a raw bidirectional stream after the policy check;
the relay switches to byte pass-through for that connection and holds
the label decision made at upgrade time. Request bodies for `archive
put`, `load` and `build` are streamed to the backend without
buffering the whole tarball, after the path / label checks that need
only the URL.

### Configuration surface

CLI flags with environment-variable equivalents, no config file:
`--project <root>` (default: cwd), `--run-dir` (default
`<root>/.apache-magpie-local/run` when adopted, else
`<git-common-dir>/apache-magpie/run/<worktree-id>`), `--backend podman|docker|auto`
(repeatable; default auto), `--egress inject-if-available|require|off`,
`--egress-port` (default: the egress gateway's), `--extra-bind-root
<path>` (repeatable; for adopters whose tests need a data directory
outside the tree — each one is logged at start so it shows up in a
`setup verify` run), `--idle-timeout`, `--log-level`, `--pid-file`.

Reference settings. The `hooks` half goes in the user settings by the
script's absolute path (per machine, so `~/.claude/settings.local.json`
when `~/.claude/settings.json` is synced; a `~` there is expanded from
`$HOME`, which the session environment can redirect); the `env` half is
per-project and belongs in the gitignored `.claude/settings.local.json`,
because it needs absolute socket paths:

```jsonc
// .claude/settings.local.json — per machine
{
  "env": {
    "CONTAINER_HOST": "unix:///<project>/.apache-magpie-local/run/podman.sock",
    "DOCKER_HOST":    "unix:///<project>/.apache-magpie-local/run/docker.sock"
  }
}

// ~/.claude/settings.local.json — per machine, absolute path
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command",
      "command": "/Users/<you>/.claude/scripts/container-gateway-hook.sh start" }] }],
    "SessionEnd":   [{ "hooks": [{ "type": "command",
      "command": "/Users/<you>/.claude/scripts/container-gateway-hook.sh stop" }] }],
    "PreToolUse":   [{ "matcher": "Bash", "hooks": [{ "type": "command", "timeout": 30,
      "command": "/Users/<you>/.claude/scripts/container-gateway-hook.sh ensure" }] }]
  }
}
```

This section once recorded both open questions as resolved in favour
of a project-relative `unix://./…` value, on the strength of the URL
*parsing* rather than a connection. That was wrong, and the committed
`env` block it justified could never have worked: the CLIs read the
authority as a host component and dial a path that does not exist.
Neither `CONTAINER_HOST` / `DOCKER_HOST` nor
`sandbox.network.allowUnixSockets` has a usable relative form, so all
four values are **absolute** per-project paths in the gitignored
`.claude/settings.local.json`, never in the committed baseline, added
by the operator (see *Known gaps*):

```jsonc
// <project>/.claude/settings.local.json
{
  "sandbox": {
    "network": {
      "allowUnixSockets": [
        "/absolute/path/to/<project>/.apache-magpie-local/run/podman.sock",
        "/absolute/path/to/<project>/.apache-magpie-local/run/docker.sock"
      ]
    }
  }
}
```

### Binaries inside the sandbox

The CLIs must be executable from inside the sandbox on both Seatbelt
and bubblewrap; the gateway does nothing for a CLI the sandbox cannot
run. `podman` from Homebrew or a distro package lives outside every
denied path. Docker Desktop installs `docker` under `~/.docker/bin/`
and its plugins under `~/.docker/cli-plugins/`, both inside the
`~/.docker` read denial.
The reference `sandbox.filesystem.allowRead` grants exactly those two paths by default (#1404), so `docker`, `docker compose` and `docker buildx` start inside the sandbox out of the box.
The rest of `~/.docker` (auth tokens, saved contexts) stays denied to the sandbox, and `Read(~/.docker/**)` still denies it to the agent's file tools; sandbox-lint asserts both the grant and that no broader `~/.docker` entry appears.
A settings file that predates the default adds the two exact paths itself, as the catalog entry says.
A Homebrew `docker` CLI needs neither, and the two entries are harmless no-ops for it.
On Linux both CLIs are under `/usr/bin`.

## Out of scope

- Hardening against a malicious image: the container runtime remains
  the boundary between a container and the VM or host kernel.
- Network filtering beyond proxy-variable injection; raw sockets and
  DNS from inside a container are not intercepted.
- Running rootless podman natively inside bubblewrap (nested user
  namespaces, fuse-overlayfs); the Linux path is always a remote client
  against a service the gateway proxies.
- Multiple Podman machines, machine lifecycle (`podman machine init` /
  `start`), and Kubernetes / compose orchestration beyond what
  `podman compose` and `docker compose` already do through the API.
- Per-project *daemons*; isolation is by label on a shared daemon.

## Acceptance criteria

See the frontmatter `acceptance:` list. Additionally:

- `uv run --project tools/container-gateway --group dev pytest` passes
  with no backend installed; the integration module is skipped, not
  failed, when no backend socket exists.
- `tools/sandbox-lint` accepts the reference settings with the new
  entries and rejects a project that lists a daemon socket directly in
  `allowUnixSockets`.
- The doctor's probe 3 reports ✓ when the gateway answers `_ping` on
  its sockets, ✗ with the catalog anchor when a backend exists but the
  gateway is not running or its socket is not allowed, and ⊘ when no
  backend is installed.

## Validation

```bash
# Unit + relay tests (no backend needed; integration auto-skips)
(cd tools/container-gateway && uv run --group dev pytest)
# Session hook: trust model, ensure, worktree records
uv run --project tools/agent-isolation --group dev pytest \
    tools/agent-isolation/tests/test_container_gateway_hook.py
# Integration against whichever backend is installed
(cd tools/container-gateway && uv run --group dev pytest -m integration)
# Reference settings still lint clean with the gateway entries
uv run --project tools/sandbox-lint --group dev sandbox-lint
# Doctor fixtures for the new probe-3 shapes
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/setup-isolated-setup-doctor/
```

- Unit tests: one table-driven test module per policy family
  (`test_policy_create.py`, `test_policy_labels.py`,
  `test_policy_build.py`, `test_policy_images.py`) over request dicts,
  covering compat and libpod shapes for every row in the tables above,
  plus the bodies a real `docker run`, `podman run`, `podman pod
  create`, `podman exec` and `podman build` actually send.
- Relay tests against an in-process fake backend on a unix socket:
  plain JSON round trip, chunked streaming, raw-stream upgrade for exec
  and attach, streamed request bodies, backend-down → 502, unknown path
  → 403.
- Integration (`-m integration`, auto-skipped): against whichever real
  backend is present, `podman run --rm` of a small image with a
  project bind mount succeeds; a bind mount of `$HOME` is refused; a
  container created in a second project directory is invisible from
  the first.
- Skill evals: `setup-isolated-setup-doctor/interpret-probes` gains
  fixtures for the three new probe-3 shapes.

## Known gaps

- `/magpie-setup:setup config` does not write the two gateway sockets into
  `.claude/settings.local.json`'s `sandbox.network.allowUnixSockets`,
  although the setup guide used to say it did. The operator adds the
  block by hand, or takes the settings diff
  `setup-isolated-setup-install` Step L proposes. Automating it in
  `/magpie-setup:setup config` is the follow-up.
- **Residual risk — a forged worktree layout.** In a linked worktree
  of a project that has not adopted Magpie, the run directory's anchor
  (the git common directory) is located from the worktree's `.git`
  file. The gateway verifies ownership and mode, `HEAD` and `objects/`,
  and a back-link to the checkout: the `worktrees/<name>/gitdir` file for
  a linked worktree, or, when the `.git` file names the common directory
  itself (the submodule layout), a `core.worktree` in `<common>/config`
  that resolves to the checkout (#1537).
  A `.git` file naming another repository's git directory outright is
  refused and points at `--run-dir`.
  The ownership check does not tell the agent from the operator (both
  run as the same user); the back-link is what ties the anchor to the
  checkout. But an agent able to
  write files can forge a complete layout inside directories it can
  already write, so the check cannot distinguish it from a real
  worktree. The consequences are bounded: sockets only land where the
  agent could already create files, are reachable only if that exact
  path is allowlisted in settings the agent cannot edit, and container
  binds remain limited to the worktree's bind roots. Mitigation: pass
  `--run-dir` explicitly, or adopt (per-worktree in-tree run dir).
- A create, exec or build field the gateway has not learned is refused,
  so a daemon feature that arrives after this table is unavailable
  through the gateway until the allow-list learns it. The refusal names
  the field, which is the signal to add it.
- The egress alias for Linux depends on the backend's bridge
  configuration and on the egress gateway listening on a non-loopback
  address; it binds loopback by default, so Linux adopters start it
  with `--host <bridge address>`.
- Docker Desktop's file-sharing settings, not the gateway, decide
  which host paths the VM can see; a project root outside the shared
  set fails at mount time with Docker's own error.
- `podman compose` shells out to an external compose provider whose
  own socket handling (e.g. `docker-compose` reading `DOCKER_HOST`) is
  outside the gateway's control; the labels the gateway injects
  coexist with compose's own.
