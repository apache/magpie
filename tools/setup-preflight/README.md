<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [setup-preflight](#setup-preflight)
  - [Prerequisites](#prerequisites)
  - [Why it is installed into the project](#why-it-is-installed-into-the-project)
  - [Invocation](#invocation)
  - [Output](#output)
    - [The two scopes](#the-two-scopes)
  - [Two rules that are the reason this is code](#two-rules-that-are-the-reason-this-is-code)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# setup-preflight

**Capability:** substrate:setup

**Harness:** agnostic

Resolve a project's Magpie setup state, and one skill's fingerprint,
into a machine-readable verdict.

Every framework skill has to answer the same question before it runs:
*is this project set up for the framework version now installed?* That
question used to be answered by prose the agent re-read on every
invocation of every skill. Most of it was not judgement at all — read a
lock, compare two hashes, order two versions, subtract two dates — so it
is answered here instead, once, deterministically, and testably.

What stays prose is what a model is actually for: which proposal to make,
how to word it, and the prohibitions. Those live in each skill's
`preflight-detail.md`, and a finding names the section that applies.

## Prerequisites

- **Runtime** — Python 3.11+. Standard library only, deliberately: the
  module is copied into an adopter's gitignored `.apache-magpie-local/`
  and run with bare `python3`, where nothing else is available.
- **CLIs** — none required. The harness CLI (`claude plugin list --json`)
  is consulted when present and its absence is a supported state, not an
  error.
- **Credentials / auth** — none.
- **Network** — none. Every input is a file in the project.
- **Optional** — `--plugin-list` accepts a listing the caller already
  read, so the tool never has to shell out.

## Why it is installed into the project

The obvious home is the plugin, and it does not work. Under the sandbox
the framework itself recommends, `~/.claude/plugins/cache/` is
read-denied, so a script shipped in the plugin can be read by the agent's
file tool but never *executed* by a shell — and a sandboxed marketplace
install is exactly the environment the reconciliation check was written
for. So `/magpie-setup config` copies this module into
`.apache-magpie-local/`, beside the configuration it already writes, and
`/magpie-setup upgrade` refreshes that copy against the framework version
now installed. It is removed when that directory is — `uninstall`
deliberately preserves `.apache-magpie-local/`, personal configuration
included, so it does not delete the checker either.

That has a consequence worth stating plainly: pre-flight may run `config`
unattended, so an unattended run can place an executable in the
checkout. It is framework code of the same provenance as the plugin the
adopter installed, it is gitignored, and it goes away with the directory
— but it is a step beyond writing configuration files.

## Invocation

```bash
python3 .apache-magpie-local/setup_preflight/cli.py \
    --skill magpie-pr-management-triage \
    --hash sha256:9f1c4e… \
    --requires pr-management-config.md
```

In the framework checkout, the same thing through the workspace:

```bash
uv run --directory tools/setup-preflight --project . setup-preflight --skill … --hash …
```

## Output

```json
{ "verdict": "ok" }
```

…or a list of findings, each naming its scope and the
`preflight-detail.md` section whose rules apply:

```json
{
  "verdict": "action",
  "findings": [
    { "scope": "project", "code": "below-floor",       "section": "step-3", "facts": {…} },
    { "scope": "skill",   "code": "fingerprint-moved", "section": "step-4", "facts": {…} }
  ]
}
```

**Exit status is 0 whenever a verdict was reached**, findings included. A
finding is the answer, not a failure. A non-zero exit means the check
could not run, and the caller falls back to the detail file rather than
assuming the project is fine.

### The two scopes

**`project`** findings are true of the checkout and identical for every
skill invoked in it — the lock, snapshot drift, the marketplace floor.
They are memoised in `.apache-magpie-local/.preflight-cache.json`, keyed
on the lock files' identity and the plugin listing and expiring after 15
minutes, so the second and later skills in a session pay only for their
own fingerprint comparison.

**`skill`** findings differ per skill: its fingerprint against the
reconciliation stamp, and whether its `requires_config:` entries resolve.

**`end-of-run`** is the periodic `/magpie-setup verify` suggestion, which
is settled when the run finishes rather than before it starts.

## Two rules that are the reason this is code

**Unknown is never absent.** A plugin listing that could not be read is
`None`, not `{}`. Inside a sandboxed session the plugin cache is
read-denied and `claude plugin list --json` prints `[]`, which reads
exactly like "nothing installed"; acting on it would propose installing a
project's entire floor on every sandboxed run. An empty *parsed* listing
is treated as unknown for the same reason — it is indistinguishable from
the denied case.

**A dev build is a version like any other.** Nothing strips or rounds a
`.devN` segment. `0.2.0.dev202609110041` is below `0.2.0`, and `0.10.0`
is above `0.9.0` — the two orderings a string comparison gets wrong in
opposite directions.

## Tests

```bash
uv run --directory tools/setup-preflight --project . python -m pytest
```

Each test is named for the rule it pins. A failure is a change to what
every skill does before it runs, not merely a refactor.
