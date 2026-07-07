<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Tool: egress-gateway](#tool-egress-gateway)
  - [What this tool provides](#what-this-tool-provides)
  - [Why this is its own tool](#why-this-is-its-own-tool)
  - [Relationship to RFC-AI-0003](#relationship-to-rfc-ai-0003)
  - [How adopters consume this tool](#how-adopters-consume-this-tool)
  - [What this tool is NOT for](#what-this-tool-is-not-for)
  - [Failure modes](#failure-modes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Tool: egress-gateway

This directory documents the **egress-gateway** tool — a local
host-allowlisting HTTP(S) forward proxy that constrains *where* framework
tools may send data. It is the network-layer egress-control chokepoint that
backstops the LLM-routing controls in
[RFC-AI-0003](../../docs/rfcs/RFC-AI-0003.md).

How-to (run it, point tools at it, extend the allowlist) lives in
[`README.md`](README.md). This file is the **what** and **why**.

## What this tool provides

A `proxy.py`-based forward proxy bound to loopback. The only first-party
code is a `proxy.py` plugin (`egress_gateway.allowlist.EgressAllowlistPlugin`)
that enforces a **default-deny host allowlist** in the
`before_upstream_connection` hook: a CONNECT / request to any host not on the
allowlist is rejected with `403` before an upstream socket is opened.

The default allowlist mirrors the curated host set the secure sandbox already
trusts (`sandbox.network.allowedDomains`): ASF infra (`*.apache.org`), GitHub,
Google APIs, PyPI — suffix-matched. Loopback is always allowed. Adopters
extend it via the `EGRESS_ALLOW_EXTRA` environment variable without editing
code.

## Why this is its own tool

Egress control is cross-cutting — it is not specific to one fetch backend or
one skill, so it does not belong under `tools/gmail/` or inside any single
skill (which would create N drifting copies). It is also **not** LLM-specific:
it governs *all* tool egress (mail fetch, roster lookups, issue-tracker
writes), which is a different concern from the PII redactor and approved-LLM
gate that RFC-AI-0003's `tools/privacy-llm/` already owns. A dedicated tool
keeps the egress policy in one auditable place.

It depends on `proxy.py` (a third-party forward proxy), so it cannot live
inside the stdlib-only `tools/privacy-llm/` sub-tools without polluting their
dependency-free contract.

## Relationship to RFC-AI-0003

RFC-AI-0003 protects foundation-private data flowing *into LLMs* with two
mechanisms (PII redactor + approved-LLM gate). Both operate at the
application layer. They do not, by themselves, stop a skill — or a
prompt-injection payload riding in an inbound report — from exfiltrating
private data over an **arbitrary HTTP call** (the gap noted in
[`docs/setup/secure-agent-setup.md`](../../docs/setup/secure-agent-setup.md):
`Bash(curl *)` egress bypasses the sandbox proxy).

The egress-gateway closes that gap at the network layer: by funnelling tool
egress through a default-deny allowlist, private data physically cannot reach
a non-sanctioned host even if a higher layer is tricked into trying. It is
**defence-in-depth**, layered under — not a replacement for — the redactor and
the gate. See RFC-AI-0003 §4.4.

## How adopters consume this tool

1. Run the gateway (outside the sandbox — it needs to bind a port and make
   unrestricted outbound; that is the point). See [`README.md`](README.md).
2. Point tool egress at it with `HTTPS_PROXY`/`HTTP_PROXY`, persisted
   per-machine in `.claude/settings.local.json`'s `env` block.
3. Allow loopback in `sandbox.network.allowedDomains` so sandboxed tools can
   reach it (loopback-only; does not widen the internet egress surface).

The gateway's allowlist should be kept in sync with the adopter's
`sandbox.network.allowedDomains` — they encode the same egress policy at two
layers.

## What this tool is NOT for

- **Not** an LLM router or a replacement for `tools/privacy-llm/`. It does not
  redact content and does not gate which LLM may receive data — it gates which
  *host* any tool may reach.
- **Not** a payload/content firewall. It tunnels HTTPS via `CONNECT` and
  allow/denies by host only — no TLS interception, no URL-path or body
  inspection.
- **Not** a sandbox replacement. The sandbox still owns filesystem isolation,
  credential denial, and bind restrictions; the gateway only adds an
  egress-allowlist chokepoint for outbound HTTP(S).

## Failure modes

| Symptom | Likely cause | Remediation |
|---|---|---|
| Gateway exits with `Operation not permitted` on bind | Started inside the sandbox | Run it from a non-sandboxed context — binding a listener is blocked under the sandbox |
| Gateway exits with `PermissionError: '.../.proxy'` | `$HOME` not writable for the process | `HOME=/tmp/egress-home … egress-gateway` |
| Sandboxed tool gets `Operation not permitted` reaching `127.0.0.1:PORT` | Loopback not in `sandbox.network.allowedDomains` | Add `localhost` + `127.0.0.1` (see `docs/setup/sandbox-troubleshooting.md`) |
| A legitimate host returns `403 CONNECT rejected` | Host not on the allowlist | Add it via `EGRESS_ALLOW_EXTRA`, or extend `ALLOW_EXACT`/`ALLOW_SUFFIXES` and keep it in sync with `sandbox.network.allowedDomains` |
