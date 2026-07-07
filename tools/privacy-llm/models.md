<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Approved-LLM registry](#approved-llm-registry)
  - [The default-approved entries](#the-default-approved-entries)
  - [The opt-in entries — adopter declares explicitly](#the-opt-in-entries--adopter-declares-explicitly)
  - [The pre-flight check](#the-pre-flight-check)
  - [Adopter config — `<project-config>/privacy-llm.md`](#adopter-config--project-configprivacy-llmmd)
  - [How skills call the gate](#how-skills-call-the-gate)
  - [Why this list is provisional](#why-this-list-is-provisional)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Approved-LLM registry

The registry answers a single question every skill that touches
`<private-list>` content asks at Step 0: **"is the active LLM
stack approved to receive this data?"** If yes, the skill
proceeds. If no, it stops with a pointer at this doc and the
adopter's `<project-config>/privacy-llm.md`.

The registry has two tiers: **default-approved** entries that
require no adopter action, and **opt-in** entries the adopter
declares explicitly per the rationale in
[*Why this list is provisional*](#why-this-list-is-provisional)
below.

## The default-approved entries

These four classes are pre-approved by the framework. An adopter
running with only these does **not** need to write
`<project-config>/privacy-llm.md` (the gate auto-detects the
default-approved Claude Code instance and passes).

| Class | Rationale | Examples |
|---|---|---|
| **Claude Code itself** | The Claude-Code instance running framework skills is treated as an approved privacy model for the data it directly processes. See [`docs/setup/privacy-llm.md` — Claude Code trust boundary](../../docs/setup/privacy-llm.md#claude-code-trust-boundary) for the rationale and the limits of this default. | The agent invoking the skill |
| **`*.apache.org`-hosted endpoints** | Anything served from an Apache Software Foundation domain runs on infra under ASF governance — data residency, retention, and access are bounded by the ASF infra agreement. | A future ASF-hosted inference endpoint at e.g. `inference.apache.org`; an in-tracker endpoint at `<project>.apache.org/llm/` |
| **Local-only inference** | The data never leaves the user's machine. No external party (cloud LLM operator, network operator, log aggregator) can observe it. | Ollama serving a local model, vLLM on the user's workstation, llama.cpp embedded in a CLI helper |
| **Air-gapped on-prem** | Same rationale as local inference, scaled to a contributor's organisation. The model server runs on infra the adopter operationally controls and which has no path to a third-party LLM operator. | A PMC-hosted inference appliance on a private VLAN |

Detection lives in
[`checker/src/checker/check.py`](checker/src/checker/check.py)
(the `_approve_by_default_rules` function); the markdown contract
here is the source-of-truth for what those rules implement, and
the
[`<project-config>/privacy-llm.md`](#adopter-config--project-configprivacy-llmmd)
declaration shape is what the checker parses.

## The opt-in entries — adopter declares explicitly

Every other LLM endpoint requires the adopter to declare it
explicitly in `<project-config>/privacy-llm.md`, naming:

- the endpoint URL (or provider product name);
- the data-residency / retention contract that backs the choice
  (a link to a contract clause, vendor doc, or BAA-equivalent);
- the security-team member who approved the addition (initials +
  date), so the audit trail is local and visible.

The framework does not ship a curated allow-list of third-party
endpoints. The opt-in mechanism puts the choice — and the
responsibility — on the adopting project's security team, where
ASF policy expects it to live.

Recipes for the most common opt-in cases (AWS Bedrock with a
data-residency-bounded region, direct Anthropic API with a
no-training agreement, Vertex AI with VPC-SC) are in
[`docs/setup/privacy-llm.md`](../../docs/setup/privacy-llm.md).
The recipes spell out the data-residency contract each one
implies.

## The pre-flight check

Skills that may read `<private-list>` content (or any private
content beyond `<security-list>` — recall the redactor handles
*third-party* PII inside `<security-list>` mail, leaving the
reporter's own identity intact) run this check at Step 0:

```text
1. Read <project-config>/privacy-llm.md, if present.
2. Build the active-LLM-stack set:
     - Claude Code (always present — this is what's running)
     - any model named in <project-config>/privacy-llm.md as
       "currently configured"
3. For every entry in the stack, decide approved? per:
     - Claude Code → ✓ default-approved
     - URL ending in .apache.org → ✓ default-approved
     - Hostname ∈ {localhost, 127.0.0.1, ::1} → ✓ default-approved
     - Listed under "approved third-party" with a complete
       data-residency note → ✓ adopter-approved
     - Anything else → ✗
4. If every entry is approved, proceed.
   If any entry is not approved, stop with:
     "Skill <name> reads <private-list> content. The active LLM
      stack contains <unapproved entry>, which is not in the
      framework's default-approved list and is not declared in
      <project-config>/privacy-llm.md. See
      tools/privacy-llm/models.md and docs/setup/privacy-llm.md."
```

The check is deliberately conservative: any single unapproved
entry in the stack stops the skill. The intent is to make adding
a new LLM hop a *deliberate* act, not something a skill can
silently grow into.

## Adopter config — `<project-config>/privacy-llm.md`

Adopters declare their privacy-LLM posture in a single markdown
file at `<project-config>/privacy-llm.md`. The framework's
[`projects/_template/privacy-llm.md`](../../projects/_template/privacy-llm.md)
ships a starting point pre-filled with the Claude-Code default;
adopters customise from there.

The file has three sections:

```markdown
## Currently configured LLM stack

- Claude Code (the agent running framework skills)
<!-- list every additional LLM the adopter has wired into any
     skill or tool here, one per line, with the endpoint URL or
     provider name. -->

## Approved third-party endpoints (opt-in)

<!-- adopter populates this section per the recipes in
     docs/setup/privacy-llm.md. Each entry includes:
     - endpoint URL / provider name
     - data-residency contract (link)
     - approved-by: <initials> <YYYY-MM-DD>
     For empty (Claude-Code-only) deployments this section
     stays empty. -->

## Private mailing lists for this project

- `<private-list>`           # PMC private list
- (any additional PMC-private foundation lists this project's
   security team reads, e.g. cross-project security relay lists)
```

The "Private mailing lists" section is what
[`tools/ponymail/`](../ponymail/) reads for the
`tools.ponymail.private_lists` config knob; the privacy-llm tool
re-uses the same source-of-truth so the two stay in sync.

## How skills call the gate

Skills call the gate via the `privacy-llm-check` console script
in [`checker/`](checker/). Run it at Step 0 (pre-flight); a
non-zero exit is a hard stop.

```bash
# Returns exit code 0 if the active stack is fully approved,
# non-zero with a stderr explanation if not.
uv run --project <framework>/tools/privacy-llm/checker privacy-llm-check \
  --reads-private-list                 # set when the skill may read <private-list>
```

The checker auto-locates `<project-config>/privacy-llm.md`:
explicit `--config` → `$PRIVACY_LLM_CONFIG` env var → standard
adopter paths (`<cwd>/.apache-magpie/privacy-llm.md`,
`<cwd>/.apache-magpie-overrides/privacy-llm.md`). On approval
it prints a one-line banner per stack entry; on rejection it
prints the failing entries to stderr and exits 1. Exit 2 means
the config file could not be located or parsed.

For `<security-list>`-only skills the gate-call is **also
required** as a defence-in-depth measure: even though the body
classification permits Claude-Code-default LLMs, running the
check ensures the adopter's config is in a valid state (no
unconfigured opt-in entries lurking in the active stack) before
any private content flows. The redactor (`pii-redact`) is
required for every `<security-list>` body read regardless; see
[`pii.md`](pii.md) for the redaction contract and
[`wiring.md`](wiring.md) for how the two mechanisms compose at
the skill level.

## Why this list is provisional

There is no ratified ASF Legal Affairs / Privacy policy yet that
enumerates approved LLM endpoints for handling foundation private
data. The default-approved list above is the **working position**
the framework adopts until such a policy lands. Specifically:

- The "Claude Code itself" default reflects the framework
  maintainer's current trust posture (per
  [`docs/setup/privacy-llm.md` — Claude Code trust boundary](../../docs/setup/privacy-llm.md#claude-code-trust-boundary)).
  If ASF Legal subsequently rules that Anthropic-hosted endpoints
  require a data-processing agreement for foundation private
  data, the framework will narrow the default and bump the
  registry version.
- The `*.apache.org` blanket approval assumes infra-level
  governance; if a future ASF endpoint runs at `*.apache.org` but
  proxies to a third-party LLM, that endpoint may need
  re-classification.

When ASF Legal does ratify a list, this file becomes the
*pointer* to that list rather than the list itself, and the
default-approved entries get re-checked against it. Until then,
this file is the framework's source-of-truth for adopters and
the rationale-of-record for the choices it encodes.
