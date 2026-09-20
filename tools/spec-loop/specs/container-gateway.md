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
  Implemented in tools/container-gateway/, a SessionStart/SessionEnd
  hook in tools/agent-isolation/, the reference .claude/settings.json,
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
    root and the project scratch tree is refused with HTTP 403 and a
    one-line reason.
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
  (`__main__.py` CLI, `proxy.py` unix-socket HTTP relay, `policy.py`
  pure request/response policy, `backends.py` discovery, `labels.py`
  project identity), `tests/`, `README.md` (how-to) and `tool.md`
  (contract). Capability: `substrate:sandbox`. Harness: agnostic.
- `tools/agent-isolation/container-gateway-hook.sh` — Claude Code
  `SessionStart` (`start`) / `SessionEnd` (`stop`) hook, installed to
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
on `<project>/.apache-magpie-local/run/podman.sock` (libpod + compat
API, for the podman CLI) and `<project>/.apache-magpie-local/run/docker.sock`
(compat API, for the docker CLI). Both files sit inside the project tree.
What shipped: `CONTAINER_HOST` / `DOCKER_HOST` do honour a
project-relative `unix://./…` value, so the committed reference
`env` block (below) names both sockets that way and needs no
per-project edit. `sandbox.network.allowUnixSockets` is a separate
setting with no such relative form in practice; the committed
baseline carries no gateway-socket entry in it at all, and
`/magpie-setup config` writes the two sockets' **absolute** paths into
the gitignored, per-project `.claude/settings.local.json` instead —
see [Container gateway](../../../docs/setup/secure-agent-setup.md#container-gateway)
in the setup guide. The macOS limit of 104 bytes on a socket path is
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
start / inspect / resize, attach, archive get / put, commit, export,
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
| `Binds`, `Mounts[type=bind]`, libpod `mounts` | source must resolve (symlinks followed, on the host) under the project root or the project scratch tree; anything else denied. `tmpfs` allowed |
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
`<root>/.apache-magpie-local/run`), `--backend podman|docker|auto`
(repeatable; default auto), `--egress inject-if-available|require|off`,
`--egress-port` (default: the egress gateway's), `--extra-bind-root
<path>` (repeatable; for adopters whose tests need a data directory
outside the tree — each one is logged at start so it shows up in a
`setup verify` run), `--idle-timeout`, `--log-level`, `--pid-file`.

Reference settings (committed, project-agnostic):

```jsonc
{
  "env": {
    "CONTAINER_HOST": "unix://./.apache-magpie-local/run/podman.sock",
    "DOCKER_HOST":    "unix://./.apache-magpie-local/run/docker.sock"
  },
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command",
      "command": "~/.claude/scripts/container-gateway-hook.sh start" }] }],
    "SessionEnd":   [{ "hooks": [{ "type": "command",
      "command": "~/.claude/scripts/container-gateway-hook.sh stop" }] }]
  }
}
```

Both open questions this section used to flag are resolved, and this is
what shipped: `podman` and `docker` both resolve a project-relative
`unix://./…` value in `CONTAINER_HOST` / `DOCKER_HOST` against the cwd,
so the committed `env` block above works unedited in every adopting
project and carries no `allowUnixSockets` entry at all.
`sandbox.network.allowUnixSockets` has no equivalent relative-path
support, so the two gateway sockets are added there as **absolute**
per-project paths — written into the gitignored
`.claude/settings.local.json` by `/magpie-setup config`, never into the
committed baseline:

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
`~/.docker` read denial; the catalog entry keeps the exact-path
`allowRead` for those two locations and recommends the Homebrew `docker`
CLI, which needs no widening. On Linux both CLIs are under `/usr/bin`.

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
  `test_policy_paths.py`, `test_policy_images.py`) over request dicts,
  covering compat and libpod shapes for every row in the tables above.
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

- The egress alias for Linux depends on the backend's bridge
  configuration and on the egress gateway listening on a non-loopback
  address; until the egress gateway grows a `--bind` option, Linux
  adopters run it with an explicit address.
- Docker Desktop's file-sharing settings, not the gateway, decide
  which host paths the VM can see; a project root outside the shared
  set fails at mount time with Docker's own error.
- `podman compose` shells out to an external compose provider whose
  own socket handling (e.g. `docker-compose` reading `DOCKER_HOST`) is
  outside the gateway's control; the labels the gateway injects
  coexist with compose's own.
