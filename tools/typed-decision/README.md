<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/typed-decision/`](#toolstyped-decision)
  - [Prerequisites](#prerequisites)
  - [Operations](#operations)
  - [Configuration](#configuration)
  - [Fail-Open Contract](#fail-open-contract)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/typed-decision/`

**Capability:** contract:typed-decision

**Kind:** implementation

**Vendor:** TypeSafe

**Harness:** agnostic

Provider-agnostic typed decision adapter contract (`choice`, `score`, `noul`) with TypeSafe's Jev API
(`api.typesafe.ai/v1/systemone`) as the initial reference backend. See [`tool.md`](tool.md) for full contract
specifications and Python API usage.

## Prerequisites

- **Runtime:** Python 3.11+ via `uv`. The implementation is stdlib-only (`urllib.request`), introducing zero third-party dependencies.
- **CLIs:** None.
- **Credentials / auth:** `TYPESAFE_API_KEY` (or `JEV_API_KEY`) environment variable or home-directory key at `~/.config/apache-magpie/typesafe.key`. Outbound prompts are strictly gated through [`tools/privacy-llm/`](../privacy-llm/).
- **Network:** `api.typesafe.ai` over HTTPS.

## Operations

The contract defines three operations (see [`tool.md`](tool.md) for parameter details):

1. **`choice(prompt, options: list[str]) -> {label, confidence}`** — Discrete option selection.
2. **`score(prompt, scale) -> {value, confidence}`** — Bounded numeric scoring along a range.
3. **`noul(prompt) -> {probability}`** — Semantic null/binary decision probability.

## Configuration

Adopters configure the provider and credentials via environment variables:

| Variable | Description | Default |
|---|---|---|
| `MAGPIE_TYPED_DECISION_PROVIDER` | Selected decision backend (`jev`) | `jev` if credentials configured, else reports unavailable |
| `TYPESAFE_API_KEY` | API key for TypeSafe Jev provider | Unset (can also use `JEV_API_KEY` or `~/.config/apache-magpie/typesafe.key`) |
| `MAGPIE_PRIVACY_GATE_STRICT` | Require explicit opt-in in `privacy-llm.md` for third-party endpoints | `false` |

## Fail-Open Contract

In adherence with RFC-AI-0004:
- On missing credentials, timeout, network failure, or provider error, every operation raises
  `TypedDecisionUnavailable`.
- The tool **never fabricates an answer** or returns synthetic defaults.
- Callers must catch `TypedDecisionUnavailable` and fall back to maintainer confirmation or primary LLM reasoning.
