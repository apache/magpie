<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gemini runtime integration tests](#gemini-runtime-integration-tests)
  - [Prerequisites](#prerequisites)
  - [Run](#run)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Gemini runtime integration tests

The ordinary [sandbox-lint tests](../test_gemini.py) validate Magpie's committed profile with Python.
These optional tests check how Gemini actually loads and enforces that profile.
They catch failures that static matching cannot establish: upstream TOML validation, policy precedence, approval-mode behavior, headless refusal, and native versus shell filesystem access.

Pytest owns discovery, skips, timeouts, and failure reporting in [`test_gemini_runtime.py`](test_gemini_runtime.py).
The adjacent [`gemini_runtime.mjs`](gemini_runtime.mjs) helper calls Gemini's JavaScript APIs and asserts their results.
It is executable test support, not fixture data or a replacement policy engine.
The tests use a temporary workspace and synthetic home files without authenticating or calling a model.

## Prerequisites

- An existing npm installation of Gemini CLI **0.59.0** and its supported Node.js runtime.
- For the Linux sandbox test: bubblewrap, usable user namespaces, Python 3, and ordinary shell utilities.
- A normal terminal where namespace creation is permitted for the sandbox test.

The helper imports private bundle APIs and checks the package version before using them.
Revalidate those imports and expected behavior on upgrades; do not downgrade an installed runtime to satisfy this test.
It resolves modules through the installed CLI entry point so leftover bundle files cannot select a different runtime.

## Run

From the framework checkout root, point at the bundle for the installation being checked:

```bash
export MAGPIE_GEMINI_BUNDLE="$(npm root -g)/@google/gemini-cli/bundle"
uv run --directory tools/sandbox-lint --group dev pytest tests/integration/test_gemini_runtime.py -k native_policy -s
```

This checks the settings loader, policy parser, and actual allow/ask/deny decisions across approval modes and interactive/headless execution.
To also exercise the Linux filesystem and network boundaries:

```bash
MAGPIE_GEMINI_SANDBOX_TEST=1 \
  uv run --directory tools/sandbox-lint --group dev pytest tests/integration/test_gemini_runtime.py -s
```

The Linux test verifies workspace writes, refusal of outside writes and network connections, and the difference between a native read and an approved shell read of a synthetic file outside the workspace.
The temporary workspace lives under the checkout because Gemini replaces `/tmp` inside the sandbox; the helper removes it afterward.
A namespace failure fails the test and does not count as successful isolation.

Without these opt-ins, pytest skips the integration tests.
Normal CI requires neither Gemini nor Node for the sandbox-lint suite and does not certify live enforcement.
Authenticated UI, skill activation, and hook checks remain in the [harness guide](../../../../docs/adapters/gemini.md#verify).
