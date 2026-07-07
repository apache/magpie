<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Mode economics — what does each mode cost to run?](#mode-economics--what-does-each-mode-cost-to-run)
  - [How to read this page](#how-to-read-this-page)
    - [What "tokens" means here](#what-tokens-means-here)
    - [Model classes](#model-classes)
  - [Per-mode token shape](#per-mode-token-shape)
    - [Triage](#triage)
    - [Mentoring](#mentoring)
    - [Drafting](#drafting)
    - [Pairing](#pairing)
    - [Agentic Autonomous](#agentic-autonomous)
  - [Model class and mode cost shape](#model-class-and-mode-cost-shape)
  - [Local and self-hosted inference](#local-and-self-hosted-inference)
  - [Reducing costs](#reducing-costs)
  - [Long-term: the ASF inference endpoint](#long-term-the-asf-inference-endpoint)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Mode economics — what does each mode cost to run?

> **Indicative, not a quote.** The numbers on this page describe the
> token-count shape of a typical invocation, not a billing prediction.
> Token prices vary by provider, model, date, and discount tier. Always
> multiply by your own provider's current rate — or by zero if you are
> running local inference.

This page exists because [MISSION.md § Affordability](../MISSION.md#affordability-and-vendor-neutrality--the-public-good-commitment)
commits to documenting mode economics honestly: a maintainer evaluating
adoption should be able to make an informed decision, not discover the
cost after the fact. The same data informs the long-term capacity
planning for an ASF-hosted inference endpoint
(see [Long-term: the ASF inference endpoint](#long-term-the-asf-inference-endpoint)).

---

## How to read this page

### What "tokens" means here

One token ≈ 0.75 words in English prose, or roughly one character in
structured code or JSON. Practical anchors:

| Content | Approximate token count |
|---|---|
| Typical bug-report body (400 words) | ~530 tokens |
| Small PR diff (50 lines changed) | ~800 tokens |
| Medium PR diff (300 lines changed) | ~5 000 tokens |
| Large PR diff (1 500 lines changed) | ~25 000 tokens |
| Mail thread, 10 messages | ~3 000–8 000 tokens |
| One skill file (SKILL.md), small setup/utility skill | ~1 000–3 000 tokens |
| One skill file (SKILL.md), typical workflow skill | ~3 500–9 000 tokens (median ~5 300) |
| One skill file (SKILL.md), large multi-step security skill | ~11 000–36 000 tokens |

Every invocation loads the relevant skill file as part of its context,
and that overhead varies widely by skill (measured with `cl100k_base`
across the current catalogue). Small setup/utility skills run
~1 000–3 000 tokens; most workflow skills ~3 500–9 000 (median ~5 300);
and the large multi-step security skills go much higher —
`security-issue-triage` ~11 000, `security-issue-import` ~22 000,
`security-issue-sync` ~36 000. This overhead applies before any
project-specific content is read.

### Model classes

Skills are written against a capability contract, not a vendor.
Three capability classes cover the realistic range for these workflows:

| Class | Parameter scale | Characteristics |
|---|---|---|
| **Small** | ~7B–13B equivalent | Fast and cheap. Good at extraction, classification, and short structured drafts. Struggles on long-chain reasoning, large contexts, and novel patterns. |
| **Mid-tier** | ~70B equivalent | Balanced quality and cost. Handles the full skill catalogue well. Recommended starting point for new adopters. |
| **Large** | Frontier reasoning | Highest capability and highest cost. Use where mid-tier recall or reasoning falls short — complex security analysis, multi-step code fix drafting, detecting novel vulnerability patterns. |

Local models (Ollama, vLLM, llama.cpp) map onto Small or Mid-tier by
capability; they incur hardware cost rather than per-token billing. See
[Local and self-hosted inference](#local-and-self-hosted-inference).

---

## Per-mode token shape

### Triage

The lowest-cost mode. Most Agentic Triage skills are read-bounded: the
expensive part is loading context (PR diff, report body, existing
issue sample), not generating output. Every output is a short
proposal — a label suggestion, a routing recommendation, a
classification with rationale — so output tokens are low relative
to input.

| Skill | Typical invocation | Token range | Primary cost driver |
|---|---|---|---|
| `pr-management-triage` | Single PR triage pass | 5 000–30 000 | PR diff size and comment count |
| `pr-management-stats` | Weekly queue report | 10 000–50 000 | Number of open PRs read |
| `pr-management-code-review` | Single PR deep review | 15 000–80 000 | Diff size; code-heavy PRs are expensive |
| `issue-triage` | Single issue classification | 4 000–15 000 | Issue body length + similar-issue cross-check sample |
| `issue-reassess` | Pool-level sweep (10 issues) | 30 000–120 000 | Pool size; batch cost scales linearly |
| `security-issue-import` | Single inbound report | 8 000–25 000 | Report length + known-dup cross-check |
| `security-issue-import-from-pr` | Single security PR import | 10 000–30 000 | PR diff + associated discussion |
| `security-issue-import-from-md` | Batch import (5 findings) | 15 000–60 000 | Number of findings × finding length |
| `security-issue-deduplicate` | Two-tracker merge | 10 000–30 000 | Tracker age and mail-thread depth |
| `security-issue-invalidate` | Single invalid close | 8 000–20 000 | Report length + reply draft |
| `security-issue-sync` | Full tracker reconciliation | 20 000–100 000 | Tracker age, mail-thread depth, linked PRs |
| `security-cve-allocate` | CVE allocation workflow | 5 000–12 000 | Mostly procedural; low variance |

**Rule of thumb for Agentic Triage:** budget 10 000–30 000 tokens per
PR / issue / report on average. A project processing 50 inbound items
per week uses roughly 500 000–1 500 000 tokens/week across Agentic Triage work.

### Mentoring

Agentic Mentoring is conversational and per-reply: the agent reads thread
context, project conventions, and contributor history, then produces
a single targeted response. Cost per reply is moderate; total weekly
cost depends on contributor volume.

| Skill | Typical invocation | Token range | Notes |
|---|---|---|---|
| `pr-management-mentor` | Single threaded reply | 6 000–20 000 | Estimated; skill experimental |
| `good-first-issue-author` | One candidate → one issue draft | 6 000–18 000 | Estimated; reads one candidate + named source files, no full-thread history; skill experimental |
| `newcomer-issue-explainer` | One issue → one beginner explanation draft | 4 000–12 000 | Estimated; reads one issue body + a small set of named source files; read-only; skill experimental |

**Rule of thumb for Agentic Mentoring:** budget 10 000–20 000 tokens per
contributor interaction. A project with 20 active contributors each
receiving 3 agent replies per week: roughly 600 000–1 200 000
tokens/week.

### Drafting

The most variable mode. Short reporter replies are inexpensive;
agent-drafted code fixes are expensive because the agent reads relevant
source files in addition to the issue or report.

| Skill | Typical invocation | Token range | Notes |
|---|---|---|---|
| `security-issue-fix` — reporter reply | Single reply draft | 10 000–35 000 | Reads report + canned responses + prior thread |
| `security-issue-fix` — code fix | Agent-drafted fix + PR | 30 000–150 000 | Adds source files; wide variance |
| `issue-fix-workflow` | Issue fix + PR | 25 000–120 000 | Bounded by what the skill reads from the codebase |

**Rule of thumb for Agentic Drafting:** reporter replies average 15 000–25 000
tokens; code-producing invocations average 50 000–100 000 tokens
depending on codebase scope. Limiting the skill to the relevant source
files is the single biggest lever on Agentic Drafting cost.

### Pairing

Agentic Pairing runs in the developer's own development cycle, not on project
infrastructure — cost is per-developer-session. Multi-agent pipelines
multiply the per-pass cost by the number of review agents.

| Skill | Typical invocation | Token range | Notes |
|---|---|---|---|
| `pairing-self-review` | Pre-flight review of a local diff | 10 000–50 000 | Estimated; skill experimental. Scales with diff size and conventions doc length. |
| Multi-agent review pipeline | Full three-pass review | 30 000–200 000 | Estimated; future skill. 3–4 × single-pass cost. Parallelism reduces latency, not billing. |

**Rule of thumb for Agentic Pairing:** a typical pre-flight self-review of a
medium PR uses 15 000–30 000 tokens. A three-agent review pipeline on
the same PR: 45 000–90 000 tokens.

### Agentic Autonomous

**Status: off.** Agentic Autonomous is not implemented; it has no token cost.
See [`docs/modes.md` § Agentic Autonomous](modes.md#agentic-autonomous).

---

## Model class and mode cost shape

The table below describes the quality/cost trade-off per mode, not a
hard recommendation. "Viable" means acceptable recall on typical cases;
"Recommended" means the sweet spot between quality and cost; "Large
class" means quality requirements that mid-tier models often miss.

| Mode | Small class | Mid-tier class | Large class |
|---|---|---|---|
| Agentic Triage — classification / routing | Viable for most cases | Recommended default | Rarely needed |
| Agentic Triage — security import (novel patterns) | Miss rate is higher | Recommended default | For subtle or novel reports |
| Agentic Mentoring | Acceptable on simple threads | Recommended default | Not typical |
| Agentic Drafting — reporter reply | Acceptable | Recommended default | Rarely needed |
| Agentic Drafting — code fix | Often insufficient | Recommended default | Complex bugs or large refactors |
| Agentic Pairing — self-review | Limited recall on conventions | Recommended default | Anchor pass in multi-agent pipelines |

**Cost differential across classes (indicative ratio, not a price):**
Small-class models are typically 10–50× cheaper per token than
Large-class models at hosted-API rates. Mid-tier sits at roughly 3–10×
cheaper than Large. The total invocation cost is `token_count × per_token_rate`;
the rate varies by vendor and changes over time — check your provider's
current pricing page.

---

## Local and self-hosted inference

Running a model locally (Ollama, vLLM, llama.cpp) shifts cost from
per-token billing to hardware:

| Inference path | Per-token cost | Typical hardware cost | Notes |
|---|---|---|---|
| Consumer GPU, Small-class quantised model | $0 | ~$0.10–0.50/hr (capex amortised over ~3 yr lifespan × moderate utilisation) | Viable for Agentic Triage and short Agentic Mentoring/Agentic Drafting |
| Cloud spot GPU, Mid-tier model | $0 | ~$1–4/hr depending on GPU class | Viable for all modes; latency is higher than hosted APIs |
| CPU-only, quantised Small model | $0 | Near-zero | Very slow; not recommended for interactive Agentic Pairing |

Local inference is also the simplest privacy answer for most skills:
data never leaves the machine, and no third-party data-processing
agreement is needed. The framework's vendor neutrality means local
paths use identical skill code to hosted paths.

---

## Reducing costs

1. **Match model class to task.** Agentic Triage classification and short
   Agentic Mentoring replies do not need a frontier model. Reserve Large-class
   for novel-pattern security analysis and complex multi-file code fixes.

2. **Scope code reads.** The biggest driver of Agentic Drafting cost is how
   many source files the agent loads. Small, well-named files help the
   skill read only what is relevant.

3. **Cache skill context.** Most agent CLIs support prompt-level
   caching. The skill file (size varies by skill class; see
   [What "tokens" means here](#what-tokens-means-here)) and stable
   project configuration files are ideal cache candidates — the first
   invocation pays; subsequent invocations are cheap on the cached
   portion. Note: most provider caches have a short TTL (Anthropic
   prompt cache: 5 min default, 1 h extended at higher write cost),
   so bursty same-session workloads benefit most; periodic triage runs
   spaced hours apart will typically miss the cache.

4. **Batch triage.** `issue-reassess` and `pr-management-stats`
   amortise context load across a pool. Running them weekly rather than
   per-event reduces overall token volume compared with individual calls.

5. **Run locally for development.** When authoring or testing a new
   skill override, use a local model. Save the hosted model for
   production invocations.

---

## Long-term: the ASF inference endpoint

[MISSION.md § Affordability](../MISSION.md#affordability-and-vendor-neutrality--the-public-good-commitment)
names an ASF-hosted inference endpoint (`inference.apache.org`, name
TBD) as a long-term roadmap item: a community-affordable,
foundation-governed, audit-logged inference layer any open-source
maintainer — ASF or otherwise — can use without paying a vendor or
accepting a vendor's gift.

This page's data — token counts per mode, per typical workload — is the
quantitative input for the capacity planning and cost models that
endpoint will need. As pilot adopters accumulate real usage data, this
page will be updated with observed ranges rather than theoretical
estimates, so the endpoint sizing argument rests on evidence.

---

## Cross-references

- [`MISSION.md` § Affordability](../MISSION.md#affordability-and-vendor-neutrality--the-public-good-commitment) — the policy commitment behind this page.
- [`docs/modes.md`](modes.md) — per-mode skill catalogue and maturity status.
- [`docs/prerequisites.md`](prerequisites.md) — what you need to run the framework, including model-backend setup.
