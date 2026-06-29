<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/privacy-llm/`](#toolsprivacy-llm)
  - [Prerequisites](#prerequisites)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/privacy-llm/`

**Capability:** capability:setup

Privacy-LLM PII-scrubbing gate. Standalone redactor / checker pair that screens content for PII before it reaches an external LLM. See [`tool.md`](tool.md) and [`wiring.md`](wiring.md) for integration details, [`models.md`](models.md) for the model catalogue, and [`pii.md`](pii.md) for the PII taxonomy.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv` (stdlib only) — the `redactor/` and `checker/` sub-tools.
- **CLIs:** None beyond the runtime.
- **Credentials / auth:** None.
- **Network:** Runs fully offline/local; the LLM endpoints it gates (Claude Code, `*.apache.org`, local Ollama / vLLM, opt-in third-party) are configured, not prerequisites of the tool itself.
