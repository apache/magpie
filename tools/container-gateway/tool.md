<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Tool: container-gateway](#tool-container-gateway)
  - [What this tool provides](#what-this-tool-provides)
  - [Why this is its own tool](#why-this-is-its-own-tool)
  - [Relationship to RFC-AI-0004 and RFC-AI-0003](#relationship-to-rfc-ai-0004-and-rfc-ai-0003)
  - [How adopters consume this tool](#how-adopters-consume-this-tool)
  - [What this tool is NOT for](#what-this-tool-is-not-for)
  - [Limits and residual risks](#limits-and-residual-risks)
  - [Declared egress surfaces](#declared-egress-surfaces)
  - [Failure modes](#failure-modes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Tool: container-gateway

This directory documents the **container-gateway** tool: a per-project policy
proxy in front of the podman / docker daemon socket, so sandboxed shell
commands can drive containers without reaching the daemon, the machine
identity, or the host filesystem.

How-to (run it, point the CLIs at it, the create-time refusal table) lives in
[`README.md`](README.md). This file is the **what** and **why**.

## What this tool provides

A Docker-compatible API relay that forwards to whichever backend is
available (Podman machine, Docker Desktop, rootless podman, dockerd) and
enforces a default-deny policy on that API. Three properties fall out of the
policy:

1. **Containers only.** The agent reaches the daemon exclusively through the
   API surface the gateway forwards, and every request shape that would turn
   a container into host access is stripped or refused. The create body, the
   exec body, the update body and the build query are **allow-lists**: a
   field or parameter the gateway has not learned is refused, rather than
   forwarded because no rule happened to name it.
2. **This project's containers only.** Every resource the gateway creates is
   labelled with the project slug; every read or act call is filtered to
   that label. Two projects on one machine share a daemon and see disjoint
   worlds.
3. **Same egress policy as the shell.** Containers get the egress gateway as
   their HTTP proxy, so tools that honour proxy variables are bound by the
   same host allow-list as sandboxed commands.

## Why this is its own tool

Container access is cross-cutting.
It is not specific to one skill, so it
does not belong under any single skill's directory (which would create N
drifting copies of the same policy). It is also not an adapter for an
external system in the `contract:*` sense: it has no upstream API of its own
to speak on a skill's behalf, it is framework substrate that makes an
*existing* local daemon safe to reach from inside the sandbox, in the same
family as [`tools/egress-gateway`](../egress-gateway/).

It depends on nothing beyond the Python standard library, so it stays a
policy proxy rather than growing a container-orchestration dependency.
`podman` and `docker` remain external CLIs the gateway forwards to, never a
library it imports.

## Relationship to RFC-AI-0004 and RFC-AI-0003

[RFC-AI-0004](../../docs/rfcs/RFC-AI-0004.md) Principle 2 (secure sandbox by
default) treats the daemon socket for a container runtime the same way it
treats the raw internet: a capability the agent needs occasionally, gated
behind a chokepoint the agent cannot bypass from inside the sandbox. Today
the only ways to reach `podman` / `docker` from the sandbox are to exclude
the CLI from sandboxing entirely, or to allow the daemon socket directly in
`sandbox.network.allowUnixSockets`. Both hand the agent a root-equivalent
socket, since the daemon can mount arbitrary host paths.

The container gateway closes that gap the same way
[RFC-AI-0003](../../docs/rfcs/RFC-AI-0003.md) §4.4's egress gateway closes
the network-egress gap: a policy proxy the sandbox is allowed to reach sits
between the agent and the thing that actually has host-level power.
`docs/rfcs/RFC-AI-0004.md`'s Principle 2 architecture table names both
gateways together as the *socket gateways* row.

## How adopters consume this tool

1. Run the gateway (outside the sandbox: it needs the real daemon socket,
   which the sandbox denies by design). See [`README.md`](README.md).
2. Point `CONTAINER_HOST` / `DOCKER_HOST` at its two sockets, and allow
   those two sockets (never the real daemon socket) in
   `sandbox.network.allowUnixSockets`.
3. Optionally wire `tools/agent-isolation/container-gateway-hook.sh` as a
   Claude Code `SessionStart` / `SessionEnd` hook so the gateway starts and
   stops with the session; other harnesses start it by hand or from their
   own wrapper.

## What this tool is NOT for

- **Not** a container security boundary. The runtime remains the real
  boundary between a container and the VM or host kernel; a malicious image
  that escapes its container is outside this gateway's scope.
- **Not** a network content filter. It injects proxy variables into
  containers it creates; it does not intercept raw sockets or DNS from
  inside a container.
- **Not** a replacement for `tools/egress-gateway`. The two are
  complementary: the egress gateway bounds which hosts *any* tool may reach
  over HTTP(S); this tool bounds what a *container* may touch on the host
  (mounts, namespaces, privileges) and hands it the same egress policy as a
  proxy.
- **Not** per-project daemon isolation. Isolation is by label on a daemon
  shared across every project on the machine, not by running a separate
  daemon per project.

## Limits and residual risks

The gateway is a policy boundary, not a sandbox for the daemon. What it
does not cover, and what the design accepts:

- **An unknown field is refused.** The allow-list posture means a daemon
  feature the gateway has not learned is unavailable through it until the
  table learns it. The refusal names the field, so the fix is a table entry
  plus a test, not a debugging session.
- **Bind sources are checked on the host at decision time and re-resolved by
  the daemon at mount time.** A symlink swapped between those two moments is
  not caught: they are two independent resolutions of the same path, and the
  gateway holds no lock on the filesystem in between.
- **Images are shared across projects by design.** Pull, list, inspect,
  history, save and build are allowed on any image the host holds; only
  remove and tag are label-checked. One project can see and run an image
  another pulled.
- **`/info`, `/version` and `/_ping` return host-level daemon facts** — the
  daemon's version and storage driver, the host's container counts — not a
  per-project view.
- **Container egress is a friction layer, not a wall.** Proxy variables bind
  the tools that honour them; a raw socket, a tool that ignores the
  variables, and DNS all go straight out, exactly as RFC-AI-0004 says of the
  permission layer.
- **Backend discovery happens at start.** A Podman machine or Docker Desktop
  started later is not picked up until the gateway restarts, which normally
  means the next session.

## Declared egress surfaces

None. The gateway's only connections are local unix sockets: the two it
listens on for the sandboxed CLIs, and the backend's own daemon socket it
forwards to. It makes no outbound network call of its own, which is why the
`no-telemetry-import` check in
[`tools/skill-and-tool-validator/`](../skill-and-tool-validator/) exempts it
the same way it exempts `egress-gateway`.
Both tools' network-shaped
imports (`socket`) are the mechanism, not an egress surface, per
[`tools/egress-gateway/tool.md`](../egress-gateway/tool.md#declared-egress-surfaces).

## Failure modes

| Symptom | Likely cause | Remediation |
|---|---|---|
| CLI reports `502` from the gateway | Backend (Podman machine / Docker Desktop / dockerd) is down | Start the backend, then retry; see [`docs/setup/sandbox-troubleshooting.md`](../../docs/setup/sandbox-troubleshooting.md#docker--podman-command-fails-with-a-socket-error) |
| CLI gets a connect error, no `502` | Gateway is not running for this project | Run the `SessionStart` hook or start the gateway by hand (see [`README.md`](README.md)) |
| CLI gets `Operation not permitted` reaching the socket | The gateway's socket is not in `sandbox.network.allowUnixSockets` | Add the two gateway sockets (never the real daemon socket) per [`docs/setup/sandbox-troubleshooting.md`](../../docs/setup/sandbox-troubleshooting.md#docker--podman-command-fails-with-a-socket-error) |
| Container create returns `403` | A create-time request violated the policy (see `README.md` § What the policy refuses) | Read the one-line reason in the response and adjust the request; it names the rule and what to change |
