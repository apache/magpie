<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [container-gateway](#container-gateway)
  - [Prerequisites](#prerequisites)
  - [Run it](#run-it)
  - [Point the CLIs at it](#point-the-clis-at-it)
  - [What the policy refuses](#what-the-policy-refuses)
  - [Egress modes](#egress-modes)
  - [Socket paths](#socket-paths)
  - [Test](#test)
  - [Caveat — containers only, not a container security boundary](#caveat--containers-only-not-a-container-security-boundary)
  - [Limits and residual risks](#limits-and-residual-risks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# container-gateway

**Capability:** substrate:sandbox

**Harness:** agnostic

A per-project **policy proxy in front of the container daemon socket**.
Sandboxed shell commands talk to it through `CONTAINER_HOST` / `DOCKER_HOST`; it forwards the Docker-compatible API to podman or docker after labelling every resource with the project, filtering every call to that label, and refusing any request that would turn a container into host access.
Companion to [`tools/egress-gateway`](../egress-gateway/): that one bounds which hosts tools may reach, this one bounds what containers may touch.
The contract (what / why) is in [`tool.md`](tool.md); this file is the how-to.

## Prerequisites

- **Runtime:** Python 3.11+ stdlib only; run with `python3 -m container_gateway` from `src/`, or `uv run --directory tools/container-gateway container-gateway`.
- **CLIs:** `podman` and/or `docker` on the host (each optional); on macOS a running Podman machine or Docker Desktop.
- **Credentials / auth:** None. The gateway never reads the machine ssh identity, `~/.docker/config.json` or `~/.config/containers/auth.json`; pulls are anonymous.
- **Network:** None of its own. Connects only to the local daemon unix socket and, once at start, probes the egress gateway on loopback.
- **Optional:** the `dev` dependency group (pytest, ruff, mypy); a running egress gateway for the proxy-injection mode.

## Run it

One gateway process per project, keyed by the project root.
It must run **outside** the sandbox.
It connects to the real daemon socket, which the sandbox denies by design.

```bash
uv run --project tools/container-gateway container-gateway --project .
```

It listens on two unix sockets under `<project>/.apache-magpie-local/run/`: `podman.sock` (libpod + compat API, for the podman CLI) and `docker.sock` (compat API, for the docker CLI).
Configuration is CLI flags with environment-variable equivalents and no config file: `--project`, `--run-dir`, `--backend podman|docker|auto` (repeatable), `--egress inject-if-available|require|off`, `--egress-port`, `--extra-bind-root` (repeatable), `--idle-timeout`, `--log-level`, `--pid-file`.
A second start for the same project is a no-op when the pid file names a live process.
It exits on `SessionEnd`, on `SIGTERM`, or after an idle timeout (default 4h) as a backstop for sessions that end without the hook firing.

## Point the CLIs at it

```bash
export CONTAINER_HOST=unix://./.apache-magpie-local/run/podman.sock
export DOCKER_HOST=unix://./.apache-magpie-local/run/docker.sock
```

The podman CLI needs the libpod API and therefore only ever talks to a podman backend.
The docker CLI talks to a docker backend when one exists, otherwise to podman's compat API.
Persist these per-machine in `.claude/settings.local.json`'s `env` block, and allow the two sockets in `sandbox.network.allowUnixSockets`, never the real daemon socket.

## What the policy refuses

The policy is a pure function over the parsed request (method, normalised path, query, JSON body), applied identically to the compat and libpod path families.
Every container and pod is labelled with the project slug, and every list / act call is filtered to that label.

**The create body, the exec body, the update body and the build query are allow-lists.**
A create body may carry only the fields the gateway has learned — the ones it reasons about, plus the inert ones a real `docker run` / `podman run` sends — and any other key, at the top level or under `HostConfig`, comes back as `unknown-field`.
The fields that turn a container into host access on their own (`rootfs`, `overlay_volumes`, `env_host`, `log_configuration`, `secret_env` / `secrets`, `cni_networks`, compat `Links` / `Cgroup` / `ContainerIDFile` / `VolumeDriver`) are refused with a reason of their own, and only when they carry a value: both CLIs send the zero value of every field on every create.

The create-time rules below apply to containers and pods (the same fields under `HostConfig` in compat and at top level in libpod):

| Field | Rule |
|---|---|
| `Privileged` | deny |
| `CapAdd` | deny any; `CapDrop` allowed |
| `Devices`, `DeviceRequests`, `DeviceCgroupRules` | deny |
| `PidMode`, `IpcMode`, `UTSMode`, `UsernsMode`, `CgroupnsMode` | deny `host` and `container:<id>` unless `<id>` carries the label |
| `NetworkMode` | deny `host`; `container:<id>` only with the label; named networks must carry the label |
| `SecurityOpt` | deny `seccomp=unconfined`, `apparmor=unconfined`, `label=disable`, `no-new-privileges=false`, `systempaths=unconfined` |
| `Sysctls`, `CgroupParent`, `Runtime`, `Isolation` | deny |
| `MaskedPaths`, `ReadonlyPaths` | deny when set to an empty list |
| `Binds`, `Mounts[type=bind]`, libpod `mounts` | source must resolve (symlinks followed, on the host) under the project root or a `--extra-bind-root`; anything else denied. `tmpfs` allowed |
| `Mounts[type=volume]`, named volumes in `Binds`, `VolumesFrom` | the volume / container must carry the label; a volume driver configuration (compat `VolumeOptions.DriverConfig`, libpod `volume-opt=`) is refused whatever the driver, since `local` with `type=none,device=/,o=bind` is a host-root bind |
| `PortBindings` / `publish` | allowed; an empty `HostIp` is rewritten to `127.0.0.1` |
| `LogConfig` | deny any driver but `json-file`, `local`, `none` or unset; options (`--log-opt`, compose `logging.options`) only on `json-file` / `local`, and only rotation-shaped keys — `path` is refused |
| `Env` | proxy variables injected per the egress rule below; a client-supplied value for the same names is replaced |

`POST /build` gets the same treatment: `volume`, `remote`, `securityopt`, `cgroupparent`, `ulimits`, `devices`, `secrets`, `ssh`, `session`, podman's `addcaps` / `labelopts` / `extrahosts`, a `networkmode` outside the keyword set above, an `nsoptions` entry joining a host namespace other than `user`, and an `output` / `outputs` that names a filesystem destination — a path-shaped bare value, a `local` / `tar` / `oci` exporter, any `dest=` attribute, anything but `type=image` / `type=registry` in the JSON or comma form — are all refused, as is any parameter the gateway has not learned.
A build also gets the egress proxy merged into its `buildargs`, so `RUN` obeys the same allow-list a container does.
An exec body is allow-listed to the exec fields, with `Privileged: true` refused; an update body to resource limits and the restart policy.

A denial comes back as `403` with a one-line reason both CLIs print verbatim.
`auth` (registry login), image push, swarm, services, tasks, nodes, plugins, secrets, configs, distribution, session and `system/dial-stdio` are denied outright, along with any path not in the allowed families.
So are `checkpoint`, `restore`, `generate` and `play` (the first two write a host path daemon-side, the last two hand the daemon a Kubernetes manifest), and `export` / `import` as query parameters on any route.

## Egress modes

At start the gateway resolves the egress gateway address for each backend and probes it once.
`inject-if-available` (the default) injects `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` into every container it creates when the probe succeeded, and logs one warning per session otherwise.
`require` refuses container creation with `403` while the egress gateway is unreachable.
`off` never injects, for adopters who run their own filtering.
This is the extent of the network control.
`--network host` is denied above, but a raw socket or custom DNS from inside a container is not intercepted.

## Socket paths

Verification of project-relative socket paths is pending; see the implementation plan's Task 1.
Task 12 records the result here.

## Test

```bash
uv run --project tools/container-gateway --group dev pytest
```

Unit tests are table-driven over the policy families and need no backend.
Integration tests (`-m integration`) exercise whichever real backend is installed and auto-skip when none is.

## Caveat — containers only, not a container security boundary

The gateway keeps the agent off the daemon socket and off resources outside its own project's label; it does not harden the container runtime itself.
The runtime remains the real boundary between a container and the VM or host kernel.
A malicious image that escapes its container is not this gateway's problem to solve.
Network filtering is limited to the proxy-variable injection above; raw sockets and DNS from inside a container are not intercepted.

## Limits and residual risks

Known and accepted, in the order you are likely to meet them:

- **An unknown field is refused, so a new daemon feature is unavailable until the gateway learns it.**
  That is the allow-list working as designed; the `403` names the field, which is the signal to add it to `policy_shape.py` (create / exec / update) or to `decisions.py` (build query) with a test.
- **A bind source is checked on the host at decision time and re-resolved by the daemon at mount time.**
  A symlink swapped between those two moments is not caught — the check and the mount are two separate resolutions of the same path, and the gateway holds no lock on the filesystem in between.
- **Images are shared across projects by design.**
  Pull, list, inspect, history, save and build are allowed on any image on the host; only remove and tag are label-checked. A project can therefore see, and run, an image another project pulled.
- **`/info`, `/version` and `/_ping` return host-level daemon facts** — the daemon's version, its storage driver, the number of containers on the whole host — not a per-project view.
- **Container egress is a friction layer, not a wall.**
  The gateway injects proxy variables; a tool that ignores them, or a raw socket, or DNS, goes straight out. RFC-AI-0004 says the same of the permission layer.
- **Backend discovery happens at start.**
  A Podman machine or Docker Desktop started after the gateway is not picked up until the gateway restarts, which normally means the next session.
