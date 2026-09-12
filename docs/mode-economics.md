<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Mode economics — what does each mode cost to run?](#mode-economics--what-does-each-mode-cost-to-run)
  - [How to read this page](#how-to-read-this-page)
    - [What "tokens" means here](#what-tokens-means-here)
    - [Measured skill-file tokens](#measured-skill-file-tokens)
    - [Measured runtime replay sample](#measured-runtime-replay-sample)
    - [Model classes](#model-classes)
  - [Per-mode token shape](#per-mode-token-shape)
    - [Triage](#triage)
    - [Mentoring](#mentoring)
    - [Drafting](#drafting)
    - [Pairing](#pairing)
    - [Meta](#meta)
    - [Modes not yet covered](#modes-not-yet-covered)
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
> measured file sizes, bounded replay samples, and unvalidated planning estimates.
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
structured code or JSON. Token counts on this page use **K** for a
thousand tokens and **M** for a million (so `30K` = 30,000 and
`1.5M` = 1,500,000). Practical anchors:

| Content | Approximate token count |
|---|---|
| Typical bug-report body (400 words) | ~530 tokens |
| Small PR diff (50 lines changed) | ~800 tokens |
| Medium PR diff (300 lines changed) | ~5K tokens |
| Large PR diff (1,500 lines changed) | ~25K tokens |
| Mail thread, 10 messages | ~3K–8K tokens |

Full skill-file sizes are measured separately in the generated table below.
They describe the file loaded when that skill is invoked, not the full session
or the always-on plugin description cost. Referenced documents and tool output
add further context. Other token ranges on this page are planning estimates;
they are not measured runtime percentiles. The separately labeled replay
benchmark below provides sample percentiles for its own bounded workloads.
Different model tokenizers can produce different counts; no universal conversion
percentage is assumed.

### Measured skill-file tokens

Regenerate with `uv run --project tools/skill-token-count skill-token-count --write`.
The [measurement tool](../tools/skill-token-count/README.md) documents the scope,
normalization, and content-based provenance. A content fingerprint identifies
exact inputs without changing on every commit or run. The recorded UTC date
is preserved until changed inputs require regeneration; the document's Git
history separately provides its publication revision and date.

<!-- BEGIN GENERATED SKILL TOKEN COUNTS -->

Measured on (UTC): 2026-09-11.

Tokenizer: **tiktoken 0.12.0, `cl100k_base`**. Method: full UTF-8 file,
including frontmatter and comments; line endings normalized to LF;
special-token spellings counted as ordinary text.
Coverage: **74 of 74 local `skills/**/SKILL.md` files**.
External `source.md` redirects and harness symlinks are excluded.

Measurement manifest SHA-256: `e764e9d7bfbecb87146a48e1bc47dd467cbe027fc76be21c8553634dcbe5f8c2`.

| Skill file | Measured tokens | Source SHA-256 (first 16 characters) |
|---|---:|---|
| [audit-finding-fix](../skills/audit-finding-fix/SKILL.md) | 4,856 | `ec0ec27a9bbefdbd` |
| [ci-runner-audit](../skills/ci-runner-audit/SKILL.md) | 2,161 | `e955adb1505e9479` |
| [committer-onboarding](../skills/committer-onboarding/SKILL.md) | 7,250 | `027ea03fd0f440bd` |
| [contributor-activity-sweep](../skills/contributor-activity-sweep/SKILL.md) | 3,273 | `a12075cbff14340e` |
| [contributor-nomination](../skills/contributor-nomination/SKILL.md) | 4,699 | `9314dc6f3521e414` |
| [contributor-sentiment](../skills/contributor-sentiment/SKILL.md) | 4,668 | `c61377d495bc9c6e` |
| [contributor-to-committer](../skills/contributor-to-committer/SKILL.md) | 4,639 | `c7b06d51a3823780` |
| [dependency-audit](../skills/dependency-audit/SKILL.md) | 3,062 | `aa2894fffe1b96b1` |
| [dependency-license-audit](../skills/dependency-license-audit/SKILL.md) | 5,206 | `1538ed69a3a56965` |
| [flaky-test-triage](../skills/flaky-test-triage/SKILL.md) | 3,018 | `bb31ef1ab791295e` |
| [good-first-issue-author](../skills/good-first-issue-author/SKILL.md) | 3,536 | `fa2fa9c100099e85` |
| [good-first-issue-sweep](../skills/good-first-issue-sweep/SKILL.md) | 4,060 | `74dc908e6e48fbc6` |
| [issue-backlog-stats](../skills/issue-backlog-stats/SKILL.md) | 6,091 | `127256ebf660e008` |
| [issue-deduplicate](../skills/issue-deduplicate/SKILL.md) | 4,484 | `a9314de110f8a7d2` |
| [issue-fix-workflow](../skills/issue-fix-workflow/SKILL.md) | 5,967 | `bc8a00d030cc4a36` |
| [issue-reassess](../skills/issue-reassess/SKILL.md) | 5,611 | `e5b7e4633bed292c` |
| [issue-reassess-stats](../skills/issue-reassess-stats/SKILL.md) | 2,937 | `28b6c692475a0a64` |
| [issue-reproducer](../skills/issue-reproducer/SKILL.md) | 6,476 | `8d069819de820538` |
| [issue-stale-sweep](../skills/issue-stale-sweep/SKILL.md) | 6,355 | `d0a6c188e475669d` |
| [issue-triage](../skills/issue-triage/SKILL.md) | 8,445 | `5b48347045deff86` |
| [license-compliance-audit](../skills/license-compliance-audit/SKILL.md) | 4,580 | `43cd5aa4f96fbf68` |
| [list-skills](../skills/list-skills/SKILL.md) | 2,224 | `022b516276b62e2a` |
| [mentoring-welcome](../skills/mentoring-welcome/SKILL.md) | 3,163 | `a245871e572b8087` |
| [newcomer-issue-explainer](../skills/newcomer-issue-explainer/SKILL.md) | 3,441 | `5c29eb31eb3c0391` |
| [onboarding-concierge](../skills/onboarding-concierge/SKILL.md) | 3,297 | `cacfba7e70981c52` |
| [optimize-skill](../skills/optimize-skill/SKILL.md) | 3,753 | `d455dfef901f0a2d` |
| [pairing-multi-agent-review](../skills/pairing-multi-agent-review/SKILL.md) | 3,720 | `be66e6488625a9b9` |
| [pairing-self-review](../skills/pairing-self-review/SKILL.md) | 3,470 | `b4e805d4e09a53f5` |
| [pr-management-code-review](../skills/pr-management-code-review/SKILL.md) | 8,808 | `b336469b3f5d59b2` |
| [pr-management-mentor](../skills/pr-management-mentor/SKILL.md) | 2,931 | `fa887219033e6b9b` |
| [pr-management-quick-merge](../skills/pr-management-quick-merge/SKILL.md) | 7,315 | `1a17f3f5322641bb` |
| [pr-management-stats](../skills/pr-management-stats/SKILL.md) | 7,155 | `0abdbccc25d53dbe` |
| [pr-management-triage](../skills/pr-management-triage/SKILL.md) | 11,444 | `b8da22f0d957cc1e` |
| [pr-stale-sweep](../skills/pr-stale-sweep/SKILL.md) | 6,665 | `679b23344ae1815c` |
| [pre-first-pr-check](../skills/pre-first-pr-check/SKILL.md) | 3,400 | `50d9198d7859c86f` |
| [release-announce-draft](../skills/release-announce-draft/SKILL.md) | 5,856 | `ac0b800323339e00` |
| [release-archive-sweep](../skills/release-archive-sweep/SKILL.md) | 4,080 | `9c5bd915a65dc619` |
| [release-audit-report](../skills/release-audit-report/SKILL.md) | 5,639 | `dd931d4a61a49325` |
| [release-keys-sync](../skills/release-keys-sync/SKILL.md) | 4,578 | `61c24efcb06f1dd2` |
| [release-prepare](../skills/release-prepare/SKILL.md) | 6,818 | `a357dda14857620f` |
| [release-promote](../skills/release-promote/SKILL.md) | 6,031 | `77ae6c7a6a8ee6dd` |
| [release-rc-cut](../skills/release-rc-cut/SKILL.md) | 6,473 | `ddb6c6c25aacf132` |
| [release-verify-rc](../skills/release-verify-rc/SKILL.md) | 7,636 | `c2feccf82acc4d86` |
| [release-vote-draft](../skills/release-vote-draft/SKILL.md) | 5,192 | `12518835b2f23c85` |
| [release-vote-tally](../skills/release-vote-tally/SKILL.md) | 5,553 | `e00605ffdc9cc310` |
| [report-framework-issue](../skills/report-framework-issue/SKILL.md) | 4,574 | `d0f76de0d33269bd` |
| [reviewer-routing](../skills/reviewer-routing/SKILL.md) | 5,127 | `8a3a31403e0af0ef` |
| [security-cve-allocate](../skills/security-cve-allocate/SKILL.md) | 11,041 | `bfc7430502855d90` |
| [security-issue-deduplicate](../skills/security-issue-deduplicate/SKILL.md) | 7,985 | `00905921821904c5` |
| [security-issue-fix](../skills/security-issue-fix/SKILL.md) | 11,846 | `7814e7d35744865b` |
| [security-issue-import](../skills/security-issue-import/SKILL.md) | 28,801 | `251beef876192cdc` |
| [security-issue-import-from-md](../skills/security-issue-import-from-md/SKILL.md) | 9,112 | `e0beea2ce188338a` |
| [security-issue-import-from-pr](../skills/security-issue-import-from-pr/SKILL.md) | 9,987 | `006579946d0591db` |
| [security-issue-import-from-scan](../skills/security-issue-import-from-scan/SKILL.md) | 4,461 | `91a818360f376ddd` |
| [security-issue-import-via-forwarder](../skills/security-issue-import-via-forwarder/SKILL.md) | 7,900 | `0dd48183e6598491` |
| [security-issue-invalidate](../skills/security-issue-invalidate/SKILL.md) | 12,258 | `07a937811564c7d0` |
| [security-issue-sync](../skills/security-issue-sync/SKILL.md) | 9,567 | `9c770f20c9e606fd` |
| [security-issue-triage](../skills/security-issue-triage/SKILL.md) | 13,075 | `c26acc8adee19bc2` |
| [security-model-prepare](../skills/security-model-prepare/SKILL.md) | 3,609 | `410f819d6fceafa1` |
| [security-model-update](../skills/security-model-update/SKILL.md) | 4,809 | `55dc0a32ecf6887e` |
| [security-model-verify](../skills/security-model-verify/SKILL.md) | 5,494 | `3fe1223783defe4f` |
| [security-tracker-stats-dashboard](../skills/security-tracker-stats-dashboard/SKILL.md) | 3,745 | `e7d2f223b63ad132` |
| [setup](../skills/setup/SKILL.md) | 7,682 | `ea48f4ad09b1e857` |
| [setup-isolated-setup-doctor](../skills/setup-isolated-setup-doctor/SKILL.md) | 3,232 | `b0a72212990efd54` |
| [setup-isolated-setup-install](../skills/setup-isolated-setup-install/SKILL.md) | 7,616 | `89c3729756eb2fb3` |
| [setup-isolated-setup-update](../skills/setup-isolated-setup-update/SKILL.md) | 4,476 | `83c62ad1d32eedaf` |
| [setup-isolated-setup-verify](../skills/setup-isolated-setup-verify/SKILL.md) | 4,406 | `a7a0a76796a7f00e` |
| [setup-override-upstream](../skills/setup-override-upstream/SKILL.md) | 4,008 | `9694cc73e1ecb2a0` |
| [setup-shared-config-sync](../skills/setup-shared-config-sync/SKILL.md) | 4,270 | `1f4d5373af095b3c` |
| [setup-status](../skills/setup-status/SKILL.md) | 2,401 | `2f86d2fc612e3492` |
| [setup-upstream-fix](../skills/setup-upstream-fix/SKILL.md) | 4,603 | `1ef9b63d182ffa6e` |
| [skill-reconciler](../skills/skill-reconciler/SKILL.md) | 4,391 | `2aa89dcafe326342` |
| [workflow-security-audit](../skills/workflow-security-audit/SKILL.md) | 3,126 | `d9cc6c8e56c2b3c0` |
| [write-skill](../skills/write-skill/SKILL.md) | 5,458 | `954ec0d57946c346` |

<!-- END GENERATED SKILL TOKEN COUNTS -->

### Measured runtime replay sample

On 2026-09-11, 30 actual Claude Code invocations ran synthetic tasks through
five skills across four modes to their final draft/report boundary: three scenarios per skill,
two repetitions each, using `claude-haiku-4-5-20251001` and Claude Code 2.1.268.
Full entrypoints and sibling Markdown references were supplied, along with
captured configuration and tool observations. Live tools and posting were disabled.

| Mode and measured skill | Runs | p50 total tokens | p90 total tokens |
|---|---:|---:|---:|
| Triage: `issue-triage` | 6 | 34,825 | 35,055 |
| Mentoring: `pr-management-mentor` | 6 | 28,907 | 29,592.5 |
| Mentoring: `good-first-issue-author` | 6 | 26,567 | 26,653 |
| Drafting: `issue-fix-workflow` | 6 | 28,714 | 29,406.5 |
| Pairing: `pairing-self-review` | 6 | 22,975 | 24,475 |

Totals use CLI-reported per-model usage, including uncached input, cache creation,
cache reads, output, and auxiliary CLI calls. Thinking is included in output,
not added twice. These are token-traffic counts, not equivalent billing units.
p50/p90 use inclusive linear interpolation. Six runs across three synthetic
scenarios are an exploratory sample, not typical costs for an entire mode.

Concrete first-attempt examples:

- **Triage:** classify an empty-input bug and draft a proposal: **34,962 tokens**.
- **Mentoring:** draft regression-test guidance for a newcomer: **29,207 tokens**.
- **Mentoring, issue authoring:** draft an issue for a missing test: **26,131 tokens**.
- **Drafting:** draft a one-file empty-input fix and regression test: **28,600 tokens**.
- **Pairing:** review one file whose empty-input guard was removed: **22,406 tokens**.

The [measurement report](../tools/skill-token-count/benchmarks/2026-09-11.md)
provides input/cache/output breakdowns and methodology. The
[records and final responses](../tools/skill-token-count/benchmarks/2026-09-11.json)
and [synthetic corpus](../tools/skill-token-count/benchmarks/replay-v1.json)
provide the first 24 calls. The [Drafting report](../tools/skill-token-count/benchmarks/2026-09-11-drafting.md),
[records](../tools/skill-token-count/benchmarks/2026-09-11-drafting.json), and
[corpus](../tools/skill-token-count/benchmarks/drafting-v1.json) cover six further
calls on an empty-input fix, a weighted-mean denominator fix, and a two-module
summary fix. All 30 CLI calls produced artifacts; completion is not a correctness
grade. One two-file review miscounted deleted lines. One Drafting response
asserted that tests were green inside its proposed PR text although no tests ran.
These outputs need human review and are not verified fixes.

The initial sample mislabeled `good-first-issue-author` as Drafting. It is
Mentoring; metadata has been corrected without changing prompts, usage, or
responses. Legacy `drafting-*` case IDs in that sample refer to issue authoring.
The collector now checks each case against the skill's declared mode before
launching calls. Percentiles are grouped by skill, not pooled across a mode.

These observations do not measure live GitHub/tool calls, follow-up discussions,
patch application and test execution, or multi-agent pipelines. They must not be substituted
for the broader planning ranges below or generalized to other models.

Security draft pre-flight also loads the shared CC-resolution rule from
`tools/mail-source/contract.md`: approximately 600 additional tokens once
per run, estimated from the rule's prose and configuration identifiers.
It reuses already-loaded project/organization configuration and adds no
mail or tracker calls, so the per-mode ranges below remain unchanged.

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

**Planning estimates are unvalidated hypotheses, not observed bounds or averages.**
The replay p50 column refers only to the exact skill and synthetic workload
above, using Claude Code's total token traffic including cache and auxiliary
calls. `Not measured` means there is no corresponding session evidence here.
It does not mean zero, and another skill's p50 must not be substituted.

For example, `issue-triage` has replay p50 **34,825**, above the old **4K-15K**
planning estimate; `pr-management-mentor` also exceeds its estimate. Loading
full entrypoints and sibling references plus CLI overhead differs from the
unspecified protocol behind those estimates. We cannot attribute the discrepancy
to one cause or validate the old bounds from this sample. Use a workload-matched
pilot for budgeting; the old estimates are retained for context, not as a cap.

### Triage

Most Agentic Triage skills are read-bounded: the
expensive part is loading context (PR diff, report body, existing
issue sample), not generating output. Every output is a short
proposal — a label suggestion, a routing recommendation, a
classification with rationale — so output tokens are low relative
to input.

| Skill | Typical invocation | Planning estimate | Primary cost driver | Replay p50 tokens |
|---|---|---|---|---|
| `pr-management-triage` | Single PR triage pass | 5K–30K | PR diff size and comment count | Not measured |
| `pr-management-stats` | Weekly queue report | 10K–50K | Number of open PRs read | Not measured |
| `pr-management-code-review` | Single PR deep review | 15K–80K | Diff size; code-heavy PRs are expensive | Not measured |
| `issue-triage` | Single issue classification | 4K–15K | Issue body length + similar-issue cross-check sample | 34,825 |
| `issue-reassess` | Pool-level sweep (10 issues) | 30K–120K | Pool size; batch cost scales linearly | Not measured |
| `security-issue-import` | Single inbound report | 8K–25K | Report length + known-dup cross-check | Not measured |
| `security-issue-import-from-pr` | Single security PR import | 10K–30K | PR diff + associated discussion | Not measured |
| `security-issue-import-from-md` | Batch import (5 findings) | 15K–60K | Number of findings × finding length | Not measured |
| `security-issue-deduplicate` | Two-tracker merge | 10K–30K | Tracker age and mail-thread depth | Not measured |
| `security-issue-invalidate` | Single invalid close | 8K–20K | Report length + reply draft | Not measured |
| `security-issue-sync` | Full tracker reconciliation | 20K–100K | Tracker age, mail-thread depth, linked PRs | Not measured |
| `security-cve-allocate` | CVE allocation workflow | 5K–12K | Mostly procedural; low variance | Not measured |
| `security-model-verify` | One repository, both checks | 10K–40K | Reads the chain plus the whole model document; a shared model is read once for the repository set | Not measured |
| `contributor-activity-sweep` | Single-contributor activity card | 10K–40K | Activity volume in the configured window | Not measured |
| `contributor-sentiment` | Full sentiment gate report | 20K–80K | Number of threads and signals sampled | Not measured |
| `contributor-nomination` | Nomination-readiness brief | 15K–50K | Contributor activity breadth read | Not measured |

**Illustrative planning assumption, not a measured average:** assuming 10K-30K
tokens per item and 50 items per week gives 500K-1.5M tokens/week. The measured
replay above exceeds that per-item assumption; validate it for your workload.

### Mentoring

Agentic Mentoring is conversational and per-reply: the agent reads thread
context, project conventions, and contributor history, then produces
a single targeted response. Cost per reply is moderate; total weekly
cost depends on contributor volume.

| Skill | Typical invocation | Planning estimate | Notes | Replay p50 tokens |
|---|---|---|---|---|
| `pr-management-mentor` | Single threaded reply | 6K–20K | Estimated; skill experimental | 28,907 |
| `good-first-issue-author` | One candidate → one issue draft | 6K–18K | Estimated; reads one candidate + named source files, no full-thread history; skill experimental | 26,567 |
| `newcomer-issue-explainer` | One issue → one beginner explanation draft | 4K–12K | Estimated; reads one issue body + a small set of named source files; read-only; skill experimental | Not measured |
| `mentoring-welcome` | One first-time contributor → one welcome draft | 4K–12K | Estimated; reads the triggering thread + contributing-guide pointers, no full-thread history; skill experimental | Not measured |
| `onboarding-concierge` | One newcomer question → one grounded answer draft | 4K–12K | Estimated; reads `CONTRIBUTING.md` + the relevant doc excerpt; read-only; skill experimental | Not measured |
| `contributor-to-committer` | Single contributor readiness brief | 15K–50K | Estimated; reads the contributor's activity history against the adopter's thresholds; read-only; skill experimental | Not measured |
| `good-first-issue-sweep` | Backlog sweep (10 issues) | 20K–80K | Estimated; scales linearly with the number of issues scored; skill experimental | Not measured |

**Unvalidated planning assumption for Agentic Mentoring:** budget 10K–20K tokens per
contributor interaction. A project with 20 active contributors each
receiving 3 agent replies per week: roughly 600K–1.2M
tokens/week.

### Drafting

The most variable mode. Short reporter replies are inexpensive;
agent-drafted code fixes are expensive because the agent reads relevant
source files in addition to the issue or report.

| Skill | Typical invocation | Planning estimate | Notes | Replay p50 tokens |
|---|---|---|---|---|
| `security-issue-fix` — reporter reply | Single reply draft | 10K–35K | Reads report + canned responses + prior thread | Not measured |
| `security-issue-fix` — code fix | Agent-drafted fix + PR | 30K–150K | Adds source files; wide variance | Not measured |
| `issue-fix-workflow` | Issue fix + PR | 25K–120K | Bounded by what the skill reads from the codebase | 28,714 (patch draft only) |
| `security-model-update` | One update cycle | 40K–200K | Dominated by the corpus: closed trackers with discussion, the reporter threads, and the model itself. Scales with the window, not the diff | Not measured |
| `security-model-prepare` | First model for one project | 150K–600K+ | The deep surface pass over in-scope entry points is the cost, and it is meant to be — a model written from the README alone is a summary of marketing copy. Budget it as a project, not an invocation | Not measured |

**Unvalidated planning assumptions for Agentic Drafting:** 15K-25K tokens
for reporter replies and 50K-100K tokens for code-producing invocations
depending on codebase scope. Limiting the skill to the relevant source
files is the single biggest lever on Agentic Drafting cost.

`security-model-prepare` is the outlier in this table and is best
budgeted separately: it is a one-off per project, its cost is
front-loaded into a code-reading pass whose whole purpose is to be
thorough, and what it produces is amortised across every later triage
decision the model routes. The recurring cost is
`security-model-update`, which is bounded by the window it is given.

### Pairing

Agentic Pairing runs in the developer's own development cycle, not on project
infrastructure — cost is per-developer-session. Multi-agent pipelines
multiply the per-pass cost by the number of review agents.
Whether a project reimburses contributors is a project policy decision.
The following ranges are estimates, not measured session costs.

| Skill | Typical invocation | Planning estimate | Notes | Replay p50 tokens |
|---|---|---|---|---|
| `pairing-self-review` | Pre-flight review of a local diff | 10K–60K | Estimated; skill experimental. Scales with diff size plus conventions, dependency, and release-policy doc length. | 22,975 |
| `pairing-multi-agent-review` | Full three-pass review | 30K–200K | Estimated; skill experimental. 3–4 × single-pass cost. Parallelism reduces latency, not billing. | Not measured |
| `pre-first-pr-check` | Newcomer pre-flight checklist on a local branch | 5K–20K | Estimated; skill experimental. Read-only; scales with diff size and convention docs read. | Not measured |

**Unvalidated planning assumptions for Agentic Pairing:** 15K-35K tokens
for a medium-PR self-review and 45K-90K for a three-agent review. The replay
measures only small self-reviews; the pipeline remains unmeasured.

### Meta

The **Meta** mode is mostly framework machinery — setup, utilities,
dashboards — whose cost is per machine or per repo rather than per
maintainership item, so it is not budgeted per invocation here (see
[`docs/modes.md` § Meta](modes.md#meta)). The exception with a
recurring per-item shape is `committer-onboarding`, which runs once
per new committer or PMC member:

| Skill | Typical invocation | Planning estimate | Primary cost driver | Replay p50 tokens |
|---|---|---|---|---|
| `committer-onboarding` | One post-vote onboarding walkthrough | 10K–30K | Mostly procedural; podling vs TLP path length | Not measured |

---

<a id="auto-merge"></a>
<a id="agentic-autonomous"></a>

### Modes not yet covered

[Agentic Autonomous](modes.md#agentic-autonomous), formerly Auto-merge: off, not implemented; no measured token cost.

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

**Price comparison:** this page does not maintain a dated comparison of named
models, so it does not claim a current price multiplier between classes.
For a concrete budget, apply the selected provider's current input, output,
and cached-input rates to the corresponding measured token quantities.
The class labels alone do not establish an invocation's price.

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

The file counts and bounded replays on this page are initial evidence for
the capacity planning and cost models that endpoint will need. The planning
estimates are not validated capacity requirements. As pilot adopters accumulate real usage data, this
page will be updated with observed ranges rather than theoretical
estimates, so the endpoint sizing argument rests on evidence.

---

## Cross-references

- [`MISSION.md` § Affordability](../MISSION.md#affordability-and-vendor-neutrality--the-public-good-commitment) — the policy commitment behind this page.
- [`docs/modes.md`](modes.md) — per-mode skill catalogue and maturity status.
- [`docs/prerequisites.md`](prerequisites.md) — what you need to run the framework, including model-backend setup.
