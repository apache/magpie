<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Tool: Typed Decision](#tool-typed-decision)
  - [What this tool provides](#what-this-tool-provides)
  - [The Contract](#the-contract)
    - [`choice(prompt, options) -> {label, confidence}`](#choiceprompt-options---label-confidence)
    - [`score(prompt, scale) -> {value, confidence}`](#scoreprompt-scale---value-confidence)
    - [`noul(prompt) -> {probability}`](#noulprompt---probability)
  - [Fail-Open Contract](#fail-open-contract)
  - [Architecture and Providers](#architecture-and-providers)
    - [Provider Interface](#provider-interface)
    - [TypeSafe Jev API Provider](#typesafe-jev-api-provider)
    - [Provider Registry and Configuration](#provider-registry-and-configuration)
  - [Privacy-LLM Gate Routing](#privacy-llm-gate-routing)
  - [Retry Policy](#retry-policy)
  - [Python Usage](#python-usage)
    - [Functional API](#functional-api)
    - [Client API](#client-api)
    - [Handling Failure](#handling-failure)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tool: Typed Decision

This directory documents the **typed-decision** capability contract (`contract:typed-decision`) —
the provider-agnostic interface that framework skills use when requesting structured, low-latency,
typed decisions (discrete categorization, bounded scoring, and binary/null hypothesis evaluation)
from specialized System 1 decision backends.

Adopting projects configure their chosen backend via `MAGPIE_TYPED_DECISION_PROVIDER` (or credential
variables such as `TYPESAFE_API_KEY`). TypeSafe's Jev API (`api.typesafe.ai/v1/systemone`) serves as
the initial reference provider backend.

## What this tool provides

Three core decision operations:

| Operation | Inputs | Output | Use Case |
|---|---|---|---|
| `choice` | `prompt: str`, `options: list[str]` | `{"label": str, "confidence": float}` | Categorical classification (e.g. bug vs feature, reviewer routing, area dispatch). |
| `score` | `prompt: str`, `scale: tuple | list | num` | `{"value": num, "confidence": float}` | Numeric evaluation along a scale (e.g. severity rating 1-5, priority scoring 0-10). |
| `noul` | `prompt: str` | `{"probability": float}` | Null hypothesis / binary probability estimation (e.g. is this report actionable?). |

## The Contract

### `choice(prompt, options) -> {label, confidence}`

Selects exactly one label from a non-empty list of candidate strings based on the prompt context.

- **Inputs:**
  - `prompt`: Natural language question, triage snippet, or context.
  - `options`: Non-empty list of string labels (e.g. `["bug", "feature-request", "needs-info"]`).
- **Output:**
  - A dictionary containing:
    - `"label"`: The chosen option (must be an element of `options`).
    - `"confidence"`: Floating-point certainty estimate in `[0.0, 1.0]`.
- **Preconditions:** `options` must contain at least one string.

### `score(prompt, scale) -> {value, confidence}`

Evaluates a score along a specified numeric interval or scale.

- **Inputs:**
  - `prompt`: Text to evaluate.
  - `scale`: Numeric range or ceiling (e.g. `(1, 5)`, `(0, 10)`, or upper-bound `10`).
- **Output:**
  - A dictionary containing:
    - `"value"`: Assigned score (integer or float within scale bounds).
    - `"confidence"`: Floating-point certainty estimate in `[0.0, 1.0]`.

### `noul(prompt) -> {probability}`

Computes the semantic probability of a proposition or binary/null decision.

- **Inputs:**
  - `prompt`: Proposition to evaluate (e.g. "Does this issue describe a reproducible defect?").
- **Output:**
  - A dictionary containing:
    - `"probability"`: Float in `[0.0, 1.0]` representing the probability of the proposition.

## Fail-Open Contract

The typed decision contract is strictly **fail-open**:

> On missing configuration, timeout, network error, or provider error, every operation
> raises `TypedDecisionUnavailable` — **never a fabricated answer**.

This guarantees that:
1. Skills never make decisions based on hallucinated defaults, fallacious random picks, or mock data.
2. Callers can catch `TypedDecisionUnavailable` cleanly and fall back to their primary LLM reasoning,
   heuristic classifiers, or interactive maintainer confirmation (in line with RFC-AI-0004
   Principle 1: Human-in-the-loop and Principle 4: Conversational/correctable skills).

## Architecture and Providers

### Provider Interface

All backends implement the `DecisionProvider` abstract base class defined in
[`interface.py`](src/typed_decision/interface.py):

```python
class DecisionProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...
    @abstractmethod
    def choice(self, prompt: str, options: list[str]) -> dict[str, Any]: ...
    @abstractmethod
    def score(self, prompt: str, scale: Any) -> dict[str, Any]: ...
    @abstractmethod
    def noul(self, prompt: str) -> dict[str, Any]: ...
```

### TypeSafe Jev API Provider

The reference backend [`providers/jev.py`](src/typed_decision/providers/jev.py) connects to TypeSafe's Jev API:

- **Endpoint:** `https://api.typesafe.ai/v1/systemone`
- **Pinned Model:** The model version is pinned to an explicit constant (`systemone-2026-06-01`), **never "latest"**,
  ensuring behavioral stability and reproducible benchmark evaluations (RFC-AI-0004 § Principle 3).
- **Zero Third-Party Dependencies:** Implemented using Python's standard `urllib.request` library.
- **Credential Storage:** Follows framework credential isolation (`AGENTS.md`): reads `TYPESAFE_API_KEY` (or `JEV_API_KEY`)
  from environment or from home directory storage (`~/.config/apache-magpie/typesafe.key`).
- **Construction Gate:** If credentials are missing at construction time, `JevProvider` raises `TypedDecisionUnavailable`
  immediately, signaling unavailability to the registry.

### Provider Registry and Configuration

Providers are resolved dynamically through [`registry.py`](src/typed_decision/registry.py):

1. **`MAGPIE_TYPED_DECISION_PROVIDER`** (env var): Explicitly select provider name (e.g. `jev`).
   If set to an unknown provider, raises `TypedDecisionUnavailable`.
2. **Default Behavior:** If `MAGPIE_TYPED_DECISION_PROVIDER` is unset:
   - Defaults to `"jev"` **if configured** (credentials present).
   - If unconfigured, reports unavailable and raises `TypedDecisionUnavailable`.

## Privacy-LLM Gate Routing

Per RFC-AI-0004 Principle 6 (Privacy by design) and [`tools/privacy-llm/`](../privacy-llm/),
**every outbound prompt must pass through the privacy-llm gate before leaving the process**:

1. Before an HTTP request is assembled, the prompt is routed through `enforce_privacy_gate(prompt, endpoint)`.
2. The gate validates that the destination host is approved per [`tools/privacy-llm/models.md`](../privacy-llm/models.md):
   - Local endpoints (`localhost`, `127.0.0.1`) are default-approved.
   - Foundation endpoints (`*.apache.org`, excluding carve-outs) are default-approved.
   - Third-party endpoints (`api.typesafe.ai`) require an explicit opt-in entry in `<project-config>/privacy-llm.md`
     with non-empty `Data-residency contract` and `Approved-by` sign-offs.
3. If the gate rejects the destination or content, `TypedDecisionUnavailable` is raised and no network request occurs.

## Retry Policy

To guard against transient network fluctuations without unbounded stalls:
- The HTTP client executes with a 30-second socket timeout (`DEFAULT_TIMEOUT_SECONDS = 30.0`).
- On timeout (`socket.timeout`, `TimeoutError`, or timeout-related `URLError`), the client executes **exactly one retry**
  following a backoff delay (`DEFAULT_BACKOFF_SECONDS = 0.5`).
- If the retry also times out (or on non-timeout network errors / HTTP 4xx/5xx responses), the client raises
  `TypedDecisionUnavailable`.

## Python Usage

### Functional API

```python
from typed_decision import choice, score, noul, TypedDecisionUnavailable

try:
    decision = choice("Classify issue #412", ["bug", "feature", "question"])
    print(decision["label"], decision["confidence"])
except TypedDecisionUnavailable:
    # Fall back to agentic reasoning or interactive maintainer confirmation
    ...
```

### Client API

```python
from typed_decision import TypedDecisionClient, TypedDecisionUnavailable

client = TypedDecisionClient()
result = client.score("Rate security impact of report", scale=(1, 5))
print(result["value"], result["confidence"])
```

### Handling Failure

```python
try:
    prob = noul("Is this report actionable?")
except TypedDecisionUnavailable as e:
    # Fail-open: do not assume a answer; proceed with maintainer review
    logger.info("Typed decision unavailable (%s); falling back to HITL", e)
```
