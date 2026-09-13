<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Local LLM runtime (Ollama, llama.cpp, vLLM)](#local-llm-runtime-ollama-llamacpp-vllm)
  - [Harness contract](#harness-contract)
  - [Serving engines and endpoints](#serving-engines-and-endpoints)
    - [Ollama](#ollama)
    - [llama.cpp server](#llamacpp-server)
    - [vLLM](#vllm)
    - [Desktop runners (LM Studio, Jan)](#desktop-runners-lm-studio-jan)
  - [Driving skills via agent frontends](#driving-skills-via-agent-frontends)
    - [OpenCode (reference harness)](#opencode-reference-harness)
    - [Aider CLI](#aider-cli)
    - [Goose (Block)](#goose-block)
    - [Continue.dev](#continuedev)
  - [Model capability floors and calibration](#model-capability-floors-and-calibration)
    - [Floor 1: 70B+ reasoning class](#floor-1-70b-reasoning-class)
    - [Floor 2: 8B–14B bounded class](#floor-2-8b14b-bounded-class)
  - [Sovereign and air-gapped operations](#sovereign-and-air-gapped-operations)
  - [Clean-environment wrapper and isolation](#clean-environment-wrapper-and-isolation)
  - [Verify](#verify)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Local LLM runtime (Ollama, llama.cpp, vLLM)

**Capability:** capability:platform

**Harness:** Local LLM (Ollama / llama.cpp / vLLM)

This guide documents how Apache Magpie operates against **local and on-premise open-weight LLMs** for [#315](https://github.com/apache/magpie/issues/315).
Grounding is established by [RFC-AI-0004 Principle 3 (Vendor Neutrality)](../rfcs/RFC-AI-0004.md), which explicitly commits the framework to open-weight models, self-hosted endpoints, and zero cloud-only skill requirements.

Local LLM runtimes serve three primary operational requirements:
1. **Sovereign deployments:** Projects and foundations bound by strict data-residency laws (such as EU GDPR, public sector, or defense-orbit OSS) that cannot transmit vulnerability or tracker content to external cloud APIs.
2. **Air-gapped triage:** Security teams operating within isolated networks that triage `<security-list>` traffic with zero external internet connectivity.
3. **Predictable cost ceilings:** Deployments running open-weight foundation models on shared local or cluster hardware without variable per-token cloud billing.

## Harness contract

| Magpie requirement | Local LLM implementation |
|---|---|
| Skill discovery | Agent frontends read the canonical `.agents/skills/magpie-*/SKILL.md` symlinks or `.claude/skills/` links directly without modification. |
| Model inference | Local engines expose standard OpenAI-compatible REST endpoints (`/v1/chat/completions` and `/v1/models`) over localhost or private network sockets. |
| Agent frontend | Model-agnostic harnesses (such as OpenCode or Aider) drive workflows by connecting to local inference endpoints. |
| Repository instructions | The agent ingests repository guidance from `AGENTS.md` and adopter instructions from `<project-config>/`. |
| Human-in-the-loop (HITL) | The agent frontend enforces strict proposal-then-confirm discipline before executing shell commands, file edits, or dispatch actions. |
| Tool bridges | Deterministic tool scripts under `tools/` execute as language-agnostic local CLI commands without sending tool code to the model. |
| Credential & network isolation | `agent-iso` strips ambient cloud credentials and network sockets, ensuring zero inadvertent outbound telemetry. |

## Serving engines and endpoints

Magpie works with any local inference server exposing an OpenAI-compatible HTTP API.
The primary supported serving backends are detailed below.

### Ollama

[Ollama](https://ollama.com) provides local model management and serving with built-in OpenAI API compatibility.

Start the Ollama daemon:

```bash
ollama serve
```

Pull the recommended model weights:

```bash
# Recommended 70B reasoning model for multi-step triage
ollama pull llama3.3:70b

# Alternative high-capability models
ollama pull qwen2.5:72b
ollama pull deepseek-r1:70b

# Lightweight model for mechanical and bounded tasks
ollama pull qwen2.5:14b
```

Ollama serves the OpenAI-compatible API at `http://localhost:11434/v1`.

### llama.cpp server

[`llama.cpp`](https://github.com/ggml-org/llama.cpp) provides lightweight, highly optimized C/C++ inference with GGUF quantization.

Launch the server with an extended context window:

```bash
llama-server \
  --model /path/to/models/Llama-3.3-70B-Instruct-Q4_K_M.gguf \
  --ctx-size 32768 \
  --port 8080 \
  --host 127.0.0.1
```

The server endpoint is available at `http://127.0.0.1:8080/v1`.

### vLLM

[vLLM](https://github.com/vllm-project/vllm) delivers high-throughput inference for multi-GPU workstations and dedicated on-premise clusters.

Start the vLLM OpenAI-compatible server:

```bash
vllm serve meta-llama/Llama-3.3-70B-Instruct \
  --port 8000 \
  --max-model-len 32768 \
  --tensor-parallel-size 2
```

The server endpoint is available at `http://localhost:8000/v1`.

### Desktop runners (LM Studio, Jan)

GUI-based local runners also provide local OpenAI-compatible endpoints:
- **LM Studio:** Start the local server under the Developer tab (default: `http://localhost:1234/v1`).
- **Jan:** Enable the local API server in Settings (default: `http://localhost:1337/v1`).

## Driving skills via agent frontends

Local models operate through model-agnostic agent frontends that handle skill discovery, tool execution, and the human interaction loop.

### OpenCode (reference harness)

[OpenCode](https://opencode.ai/) is the framework reference implementation and natively connects to any OpenAI-compatible local endpoint.

Configure OpenCode to use the local server in your project configuration or environment:

```bash
export OPENAI_BASE_URL="http://localhost:11434/v1"
export OPENAI_API_KEY="local-no-key-required"

# Launch OpenCode pointing to the local model
opencode --model llama3.3:70b
```

Inside OpenCode, discover and run Magpie skills directly:

```text
/skills list
Use the magpie-list-skills skill.
```

### Aider CLI

[Aider](https://github.com/paul-gauthier/aider) drives git-centric workflows against local endpoints:

```bash
# Connect Aider to Ollama
aider --openai-api-base http://localhost:11434/v1 \
      --model openai/llama3.3:70b \
      --no-git
```

### Goose (Block)

[Goose](https://github.com/block/goose) connects to local OpenAI-compatible endpoints:

```bash
# Configure Goose with the local endpoint
export OPENAI_BASE_URL="http://localhost:11434/v1"
export OPENAI_API_KEY="local-key"
goose run --model llama3.3:70b
```

### Continue.dev

[Continue](https://continue.dev/) discovers skills and drives local models inside VS Code and JetBrains IDEs via `~/.continue/config.json`:

```json
{
  "models": [
    {
      "title": "Local Llama 3.3 70B",
      "provider": "openai",
      "model": "llama3.3:70b",
      "apiBase": "http://localhost:11434/v1"
    }
  ]
}
```

## Model capability floors and calibration

Skills vary in their cognitive demands.
Based on calibration against the framework evaluation suite under [`tools/skill-evals/`](../../tools/skill-evals/), local deployments must respect model size floors to ensure reliable execution.

### Floor 1: 70B+ reasoning class

Multi-step security workflows require strong logical reasoning, instruction adherence across long contexts, and nuanced threat modeling.

**Recommended models:**
- `Llama-3.3-70B-Instruct`
- `Qwen2.5-72B-Instruct`
- `DeepSeek-R1-Distill-Llama-70B`

**Target skills requiring Floor 1:**
- `magpie-security-issue-triage` (inbound mail triage, attack vector identification, CVSS estimation)
- `magpie-pr-management-code-review` (security regression analysis, diff inspection)
- `magpie-cve-allocation-draft` (vulnerability narrative formulation, advisory drafting)
- `magpie-mentor-contributor` (multi-turn developer guidance and contextual code review)

### Floor 2: 8B–14B bounded class

Deterministic, mechanical, or single-turn tasks operate reliably on smaller, quantized models running on resource-constrained hardware.

**Recommended models:**
- `Qwen2.5-14B-Instruct`
- `Llama-3.1-8B-Instruct`
- `Mistral-Small-24B-Instruct`

**Target skills suitable for Floor 2:**
- `magpie-git-commit` (structured commit message generation with trailers)
- `magpie-review-doc` (formatting, spelling, and link consistency checks)
- `magpie-list-skills` (catalog presentation and inventorying)
- `magpie-scope-validation` (label taxonomy and milestone alignment)

## Sovereign and air-gapped operations

For deployments requiring absolute privacy or air-gapped isolation:

1. **Verify offline operation:** Ensure the inference server runs with telemetry disabled (`OLLAMA_NO_TELEMETRY=1`, `VLLM_NO_USAGE_STATS=1`).
2. **Model weight integrity:** Verify SHA-256 checksums of model weights prior to deployment in air-gapped enclaves.
3. **Zero cloud egress:** All parsing, triage analysis, and tool execution remain strictly local to the machine or local enclave.

## Clean-environment wrapper and isolation

To ensure local LLM execution does not inadvertently access ambient environment secrets:

```bash
source <framework>/tools/agent-isolation/agent-iso.sh
agent-iso opencode --model llama3.3:70b
```

The `agent-iso` launcher strips unapproved environment variables and enforces isolated execution baselines.

## Verify

Verify that the local LLM runtime setup satisfies framework constraints:

```bash
# 1. Verify skill discovery topology
$env:PYTHONUTF8=1; uv run --project tools/symlink-lint symlink-lint

# 2. Validate skill and tool metadata
$env:PYTHONUTF8=1; uv run --project tools/skill-and-tool-validator skill-and-tool-validate

# 3. Check vendor neutrality score
$env:PYTHONUTF8=1; uv run --project tools/vendor-neutrality-score vendor-neutrality-score

# 4. Check documentation table of contents and formatting
uv run prek run doctoc --all-files
```

## See also

- [`docs/rfcs/RFC-AI-0004.md`](../rfcs/RFC-AI-0004.md) — normative principles for vendor neutrality and open-weight models.
- [`docs/vendor-neutrality.md`](../vendor-neutrality.md) — framework vendor neutrality index across LLM backends.
- [`docs/adapters/add-a-harness.md`](add-a-harness.md) — step-by-step guide for integrating runtime harnesses.
- [`tools/agent-isolation/README.md`](../../tools/agent-isolation/README.md) — clean-environment launcher.
- [`tools/skill-evals/`](../../tools/skill-evals/) — empirical evaluation suite for model capability calibration.
