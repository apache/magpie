<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [egress-gateway](#egress-gateway)
  - [Prerequisites](#prerequisites)
  - [Run it](#run-it)
  - [Point tools at it](#point-tools-at-it)
  - [The allowlist](#the-allowlist)
  - [Test](#test)
  - [Caveat — host-level, not payload-level](#caveat--host-level-not-payload-level)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# egress-gateway

**Capability:** substrate:sandbox

**Harness:** agnostic

A local **host-allowlisting HTTP(S) forward proxy** for the
Magpie framework. It is the egress-control chokepoint: framework
tools point `HTTPS_PROXY`/`HTTP_PROXY` at it, and the gateway rejects any
connection to a host that is not on its allowlist — before a socket is
opened. This is defence-in-depth for
[RFC-AI-0003](../../docs/rfcs/RFC-AI-0003.md): even if a skill or a
prompt-injection tries to send private data to an arbitrary endpoint, the
destination is blocked.

The contract (what/why) lives in [`tool.md`](tool.md); this file is the
how-to.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv` (no system install needed).
- **Dependencies:** `proxy.py` (`>=2.4,<3`) — the forward-proxy runtime,
  resolved by `uv` from PyPI; the allowlist policy is the only first-party code.
- **CLIs:** None beyond the runtime.
- **Credentials / auth:** None.
- **Network:** Binds a loopback listen socket (default `127.0.0.1:8899`) and
  makes unrestricted outbound by design — must run in a **non-sandboxed**
  context. Needs a writable `$HOME` (or a `HOME` override) for runtime state
  under `~/.proxy`. Default allowlist mirrors the sandbox's curated domains
  (ASF infra, GitHub, Google APIs, PyPI).
- **Optional:** the `dev` dependency group (`pytest`, `ruff`, `mypy`) to run the test suite.

## Run it

```bash
# From a context that is NOT sandboxed — binding a listen socket and
# making unrestricted outbound is exactly this process's job.
uv run --project tools/egress-gateway egress-gateway          # 127.0.0.1:8899
uv run --project tools/egress-gateway egress-gateway --port 9000
```

proxy.py keeps runtime state under `$HOME/.proxy`; if HOME is not writable
in your environment, point it somewhere writable for this process:

```bash
HOME=/tmp/egress-home uv run --project tools/egress-gateway egress-gateway
```

## Point tools at it

```bash
export HTTPS_PROXY=http://127.0.0.1:8899
export HTTP_PROXY=http://127.0.0.1:8899
export NO_PROXY=localhost,127.0.0.1
```

Every framework tool that uses Python `urllib` (ponymail, whimsy, jira, …)
honours these automatically — no code change. Persist them per-machine in
`.claude/settings.local.json`'s `env` block (never committed — the gateway
is a local process).

**Sandbox interaction:** a *sandboxed* process can only reach the loopback
proxy if `localhost`/`127.0.0.1` are in `sandbox.network.allowedDomains`
(see [`docs/setup/sandbox-troubleshooting.md`](../../docs/setup/sandbox-troubleshooting.md)
→ *cannot bind to a localhost port*). Adding them is loopback-only and does
not widen the internet egress surface — that is now the gateway's job.

## The allowlist

Defaults mirror the sandbox's curated `sandbox.network.allowedDomains`
(ASF infra, GitHub, Google APIs, PyPI), suffix-matched so every
`*.apache.org` project site is covered. Extend without editing code:

```bash
EGRESS_ALLOW_EXTRA="bedrock.example.com,.internal.corp" \
  uv run --project tools/egress-gateway egress-gateway
```

Entries starting with `.` are treated as suffixes; everything else is an
exact host. Loopback (`localhost`, `127.0.0.1`, `::1`) is always allowed.

## Test

```bash
uv run --project tools/egress-gateway --group dev pytest
```

The allowlist policy (`host_allowed`) is a pure function and is unit-tested
directly; the proxy.py integration is intentionally not exercised in CI
(it needs to bind a port).

## Caveat — host-level, not payload-level

The gateway tunnels HTTPS via `CONNECT`; it allow/denies by **host**, not by
URL path or body. There is no TLS interception, so it cannot inspect request
payloads. That is the right model for egress *control* without MITM. If you
need per-path or content-level filtering, that is a different (heavier) tool.
