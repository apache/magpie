<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [checker](#checker)
  - [Run](#run)
  - [Config file lookup](#config-file-lookup)
  - [Test](#test)
  - [Lint / type-check](#lint--type-check)
  - [Referenced by](#referenced-by)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- Licensed to the Apache Software Foundation (ASF) under one
     or more contributor license agreements.  See the NOTICE file
     distributed with this work for additional information
     regarding copyright ownership.  The ASF licenses this file
     to you under the Apache License, Version 2.0 (the
     "License"); you may not use this file except in compliance
     with the License.  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

     Unless required by applicable law or agreed to in writing,
     software distributed under the License is distributed on an
     "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
     KIND, either express or implied.  See the License for the
     specific language governing permissions and limitations
     under the License. -->

# checker

Stdlib-only Python project implementing the approved-LLM gate-check
for the Magpie privacy-llm tool. One console script:

| Console script | Purpose |
|---|---|
| `privacy-llm-check` | Parse `<project-config>/privacy-llm.md`, verify every entry in the *Currently configured LLM stack* section is approved per the rules in [`../models.md`](../models.md). Exit 0 if all approved, 1 with stderr explanation otherwise (2 if the config file cannot be located or parsed). |

The behavioural contract — which entries are default-approved, which
require an opt-in declaration with a data-residency contract + PMC
sign-off — lives in [`../models.md`](../models.md). The skill-side
wiring contract is in [`../wiring.md`](../wiring.md). This README
covers local invocation.

## Run

From the framework's root (this repository when running standalone;
the snapshot path inside an adopting tracker repo):

```bash
# Default lookup — reads <cwd>/.apache-magpie/privacy-llm.md or
# <cwd>/.apache-magpie-overrides/privacy-llm.md.
uv run --project tools/privacy-llm/checker privacy-llm-check

# Skill-style invocation: tells the user the check fires because
# the skill may read <private-list> content.
uv run --project tools/privacy-llm/checker privacy-llm-check --reads-private-list

# Explicit config path:
uv run --project tools/privacy-llm/checker privacy-llm-check \
  --config <project-config>/privacy-llm.md

# Quiet mode (no output on approval; non-zero exit + stderr on rejection):
uv run --project tools/privacy-llm/checker privacy-llm-check --quiet
```

Skill files reference the same invocation via the `<framework>`
placeholder so the path resolves in either context:

```bash
uv run --project <framework>/tools/privacy-llm/checker privacy-llm-check ...
```

`<framework>` substitutes to the snapshot path inside an adopting
project (typically `.apache-magpie/apache-magpie/`) and to `.`
when running standalone — see the placeholder convention in
[`AGENTS.md`](../../../AGENTS.md#placeholder-convention-used-in-skill-files).

## Config file lookup

In order of precedence:

| Source | Notes |
|---|---|
| `--config <path>` | Explicit override; absolute or relative to `<cwd>`. |
| `$PRIVACY_LLM_CONFIG` | Environment-variable override. |
| `<cwd>/.apache-magpie/privacy-llm.md` | Standard adopter location (the framework's `<project-config>` substitutes here). |
| `<cwd>/.apache-magpie-overrides/privacy-llm.md` | Alternative location used by adopters who keep overrides in a separate dir. |

If none of the candidates exist, the checker exits 2 with the list
of paths it tried.

## Test

```bash
uv run --project tools/privacy-llm/checker --group dev pytest
```

## Lint / type-check

```bash
uv run --project tools/privacy-llm/checker --group dev ruff check src tests
uv run --project tools/privacy-llm/checker --group dev ruff format --check src tests
uv run --project tools/privacy-llm/checker --group dev mypy
```

## Referenced by

- [`tools/privacy-llm/tool.md`](../tool.md) — tool overview.
- [`tools/privacy-llm/models.md`](../models.md) — approved-model registry contract that the checker implements.
- [`tools/privacy-llm/wiring.md`](../wiring.md) — skill-side wiring contract; the checker is called from Step 0 pre-flight.
- [`projects/_template/privacy-llm.md`](../../../projects/_template/privacy-llm.md) — adopter template; this is the file the checker parses.
