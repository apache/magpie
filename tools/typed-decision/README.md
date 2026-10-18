<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/typed-decision/`](#toolstyped-decision)
  - [Prerequisites](#prerequisites)
  - [Operations](#operations)
  - [Configuration](#configuration)
  - [Local OpenAI-Compatible Provider](#local-openai-compatible-provider)
  - [Fail-Open Contract](#fail-open-contract)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# `tools/typed-decision/`

**Capability:** contract:typed-decision

**Kind:** implementation

**Vendor:** TypeSafe + self-hosted OpenAI-compatible

**Harness:** agnostic

Provider-agnostic typed decision adapter contract (`choice`, `score`, `noul`) with TypeSafe's Jev API (`api.typesafe.ai/v1/systemone`) as the initial reference backend and an in-tree local OpenAI-compatible provider (Ollama / llama.cpp / vLLM) as the offline, zero-egress backend.
See [`tool.md`](tool.md) for full contract specifications and Python API usage.

## Prerequisites

- **Runtime:** Python 3.11+ via `uv`.
  The implementation is stdlib-only (`urllib.request`), introducing zero third-party dependencies.
- **CLIs:** None.
- **Credentials / auth:** `TYPESAFE_API_KEY` (or `JEV_API_KEY`) environment variable or home-directory key at `~/.config/apache-magpie/typesafe.key`.
  Outbound prompts are strictly gated through [`tools/privacy-llm/`](../privacy-llm/) and deny unapproved destinations by default.
- **Network:** `api.typesafe.ai` over HTTPS (Jev), or a loopback OpenAI-compatible endpoint (local provider).
- **Secure agent setup:** under [`docs/setup/secure-agent-setup.md`](../../docs/setup/secure-agent-setup.md) the sandbox cannot read `~/`, so the key file is not found and every call resolves to `TypedDecisionUnavailable`.
  After the privacy-llm opt-in is signed off, an adopter enables the provider by passing the key through an environment variable the clean-env wrapper forwards, and by adding `api.typesafe.ai` to their own `sandbox.network.allowedDomains`.
  The framework's default allowlist does not include it, by design.
  The local provider needs no credentials and no egress allowlist entry for its default loopback endpoint, but the runtime must still be able to reach the chosen local port.

## Operations

The contract defines three operations (see [`tool.md`](tool.md) for parameter details):

1. **`choice(prompt, options: list[str]) -> {label, confidence}`** — Discrete option selection.
2. **`score(prompt, scale) -> {value, confidence}`** — Bounded numeric scoring along a range.
3. **`noul(prompt) -> {probability}`** — Semantic null/binary decision probability.

## Configuration

Adopters configure the provider and credentials via environment variables:

| Variable | Description | Default |
|---|---|---|
| `MAGPIE_TYPED_DECISION_PROVIDER` | Selected decision backend (`jev` or `local`) | `jev` if credentials configured, else reports unavailable |
| `TYPESAFE_API_KEY` | API key for TypeSafe Jev provider | Unset (can also use `JEV_API_KEY` or `~/.config/apache-magpie/typesafe.key`) |
| `MAGPIE_TYPED_DECISION_LOCAL_MODEL` | Model name for the `local` provider (e.g. `qwen3.5:9b`) | Unset — required when `MAGPIE_TYPED_DECISION_PROVIDER=local` |
| `MAGPIE_TYPED_DECISION_LOCAL_ENDPOINT` | OpenAI-compatible chat-completions URL for the `local` provider | `http://localhost:11434/v1/chat/completions` (Ollama) |
| `MAGPIE_TYPED_DECISION_LOCAL_API_KEY` | Optional Bearer key for the `local` provider (e.g. a vLLM `--api-key`) | Unset — local endpoints are typically unauthenticated |

Third-party destinations such as `api.typesafe.ai` deny by default per [`tools/privacy-llm/models.md`](../privacy-llm/models.md).
They require an explicit opt-in entry in `<project-config>/privacy-llm.md` with filled `Data-residency contract` and `Approved-by` sign-offs.
Loopback endpoints (`localhost`, `127.0.0.1`, `::1`) are default-approved for the `local` provider; any other host needs HTTPS and, unless it is a default-approved `*.apache.org` endpoint, an explicit opt-in entry.

## Local OpenAI-Compatible Provider

The in-tree `local` provider (`MAGPIE_TYPED_DECISION_PROVIDER=local`) sends every operation to a self-hosted
OpenAI-compatible chat-completions endpoint — [Ollama](https://ollama.com) (`:11434/v1`),
[llama.cpp server](https://github.com/ggml-org/llama.cpp) (`:8080/v1`), or
[vLLM](https://docs.vllm.ai) (`:8000/v1`) — so structured decisions run offline with zero third-party egress.

- **Structured outputs:** each request carries a strict `response_format: json_schema` whose schema
  pins the operation's shape (`label` constrained to the candidate `options`); scale and probability
  bounds are re-validated client-side after parsing. Every returned field is re-validated against the contract
  (label ∈ options, scale bounds, `[0.0, 1.0]` ranges, booleans and non-finite numbers rejected)
  and anything malformed raises `TypedDecisionUnavailable` — fail-open, never a fabricated answer.
- **Privacy posture:** the endpoint must be a loopback host (plain HTTP is only allowed there) or an
  explicitly opted-in HTTPS host; environment proxies (`HTTP_PROXY` / `HTTPS_PROXY`) are disabled for
  every request and redirects are rejected, so a loopback URL stays loopback for the whole round trip.
- **Retry policy:** same as Jev — a 30-second socket timeout with exactly one retry on timeout.

## Fail-Open Contract

In adherence with RFC-AI-0004:
- On missing credentials, timeout, network failure, or provider error, every operation raises `TypedDecisionUnavailable`.
- The tool **never fabricates an answer** or returns synthetic defaults.
- Callers must catch `TypedDecisionUnavailable` and fall back to maintainer confirmation or primary LLM reasoning.
