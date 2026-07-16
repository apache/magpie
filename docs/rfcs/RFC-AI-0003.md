<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [RFC-AI-0003: Privacy-aware LLM routing for foundation private information](#rfc-ai-0003-privacy-aware-llm-routing-for-foundation-private-information)
- [RFC: privacy-aware LLM routing for foundation private mail](#rfc-privacy-aware-llm-routing-for-foundation-private-mail)
  - [1. Abstract](#1-abstract)
  - [2. Background and motivation](#2-background-and-motivation)
  - [3. Goals and non-goals](#3-goals-and-non-goals)
    - [Goals](#goals)
    - [Non-goals](#non-goals)
  - [4. Design](#4-design)
    - [4.1 The two mechanisms at a glance](#41-the-two-mechanisms-at-a-glance)
    - [4.2 Mechanism 1 — PII redactor](#42-mechanism-1--pii-redactor)
    - [4.3 Mechanism 2 — approved-LLM gate](#43-mechanism-2--approved-llm-gate)
    - [4.4 Mechanism 3 (defence-in-depth) — egress-allowlist gateway](#44-mechanism-3-defence-in-depth--egress-allowlist-gateway)
  - [5. Data flow](#5-data-flow)
  - [6. Implementation](#6-implementation)
    - [6.1 The redactor sub-tool — `tools/privacy-llm/redactor/`](#61-the-redactor-sub-tool--toolsprivacy-llmredactor)
    - [6.2 The checker sub-tool — `tools/privacy-llm/checker/` (PR #51)](#62-the-checker-sub-tool--toolsprivacy-llmchecker-pr-51)
    - [6.3 What never reaches any LLM](#63-what-never-reaches-any-llm)
    - [6.4 The egress gateway — `tools/egress-gateway/`](#64-the-egress-gateway--toolsegress-gateway)
  - [7. Adopter configuration](#7-adopter-configuration)
  - [8. Skill wiring summary](#8-skill-wiring-summary)
  - [9. Trust boundaries and status](#9-trust-boundaries-and-status)
  - [10. Open questions and future work](#10-open-questions-and-future-work)
    - [10.1 Resolved in PR-3](#101-resolved-in-pr-3)
    - [10.2 ASF Privacy VP/Legal VP ratification](#102-asf-privacy-vplegal-vp-ratification)
    - [10.3 MCP-layer hooks](#103-mcp-layer-hooks)
    - [10.4 Mapping-file lifecycle tools](#104-mapping-file-lifecycle-tools)
    - [10.5 Doc-cleanup follow-up](#105-doc-cleanup-follow-up)
    - [10.6 Egress-gateway wiring](#106-egress-gateway-wiring)
  - [11. References](#11-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- Source: ASF Confluence wiki (RFCs space). Public-safe re-export:
     wiki-internal links and members-only references have been stripped
     per the Apache Magpie project's RFC-AI-0004 § Privacy-by-Design
     principle (no exposing of SSO-gated URLs in public artefacts).
     The authoritative source remains the Confluence page; this file
     is a public mirror for review by adopters who do not have ASF SSO. -->

# RFC-AI-0003: Privacy-aware LLM routing for foundation private information

Apache Magpie — third-party PII redaction + approved-LLM gate

apache/magpie maintainers

2026-05-04

**Status — provisional.** The default-approved LLM registry described in this RFC reflects the framework maintainer's working position pending ASF Privacy VP/Legal VP ratification of an authoritative approved-model list for foundation private data. When such a list lands, the registry will be updated to point at it as source-of-truth.

# RFC: privacy-aware LLM routing for foundation private mail

| Field | Value |
|---|---|
| **Status** | Provisional — pending ASF Privacy VP/Legal VP ratification |
| **Targets** | `apache/magpie` (the Apache Magpie framework) + adopting projects |
| **Implemented in** | [PR #48](https://github.com/apache/magpie/pull/48) (foundation), [PR #50](https://github.com/apache/magpie/pull/50) (refinement + skill-side redactor wiring), [PR #51](https://github.com/apache/magpie/pull/51) (gate-check + skill-side gate wiring) |
| **Source-of-truth docs** | [`tools/privacy-llm/{tool,pii,models,wiring}.md`](https://github.com/apache/magpie/tree/main/tools/privacy-llm), [`docs/setup/privacy-llm.md`](https://github.com/apache/magpie/blob/main/docs/setup/privacy-llm.md), [`AGENTS.md → Privacy-LLM`](https://github.com/apache/magpie/blob/main/AGENTS.md) |
| **Reference implementation** | [`tools/privacy-llm/redactor/`](https://github.com/apache/magpie/tree/main/tools/privacy-llm/redactor) (PII redactor, stdlib-only Python, 48 unit tests), [`tools/privacy-llm/checker/`](https://github.com/apache/magpie/tree/main/tools/privacy-llm/checker) (approved-LLM gate-check, stdlib-only Python, 33 unit tests) |

## 1. Abstract

The Apache Magpie framework lets agents drive ASF security workflows that read **two distinct classes of private mail**: external reporters' mail to a project's `<security-list>` and PMC-internal mail on `<private-list>`. Both classes must not leak through any LLM in the active stack — but they require **different** remediations, and a single conflated mechanism would either over-block (refuse to process `<security-list>` content needlessly) or under-protect (let `<private-list>` bodies flow through arbitrary LLMs).

This RFC describes — and the linked PRs implement — a **two-mechanism design**:

1. A **PII redactor** that swaps third-party identifiers in `<security-list>` mail for hash-prefixed tokens before any LLM step, with a deterministic local mapping that is reversed only at the outbound boundary.
2. An **approved-LLM pre-flight gate** that refuses to fetch `<private-list>` content unless every LLM in the active stack matches the framework's default-approved registry or an adopter-declared opt-in entry.

The reporter's own identity flows through the agent's context as-is, by design — they sent the mail and are operationally known to the security team. Collaborators on the project's `<tracker>` repo are similarly exempt: their identity is already public via collaborator status.

Both mechanisms are now landed: the redactor (PR #48 + PR #50) and the gate-check (PR #51). The full design is shipped, end-to-end, behind explicit Step 0 pre-flight calls in every `<security-list>`-touching skill.

**Complementary network-layer control.** The two mechanisms above operate at the application layer — they decide what a skill deliberately *sends* to an LLM. They do not, by themselves, stop private data from leaving over an arbitrary HTTP call (a buggy tool, or a prompt-injection payload that coaxes the agent into exfiltration). §4.4 adds an optional **egress-allowlist gateway** (`tools/egress-gateway/`) as defence-in-depth: a default-deny host allowlist that funnels all tool egress through a single chokepoint, so private data physically cannot reach a non-sanctioned host even if a higher layer is bypassed. It is layered *under* the two LLM-routing mechanisms, not a replacement for them.

## 2. Background and motivation

ASF security work routinely handles two kinds of private content:

- **`<security-list>` mail.** External reporters send vulnerability reports to the project's `security@` list. The reporter is a known correspondent (the team replies, attributes credit, and references them across the tracker discussion). The body, however, frequently mentions **third parties** — a co-researcher, a victim the reporter observed, a named individual called out in the body — whose identities are not operationally needed by the security team and which absolutely should not flow through arbitrary LLMs.
- **`<private-list>` mail.** PMC-private foundation lists (`private@<project>.apache.org` and any cross-project relay lists the security team subscribes to) are wholly private. Every byte — body and metadata alike — is sensitive.

A single mechanism cannot serve both. PII redaction is necessary but insufficient for `<private-list>` (the body itself is private, not just the identifiers). An approved-LLM gate alone is insufficient for `<security-list>` (an LLM may be approved to receive the body but third-party PII still belongs in the local map, not in any LLM's context window or inference logs).

Two earlier candidate designs were rejected:

- **"Just redact everything before any LLM call."** This loses the reporter's identity, which the team needs operationally for replies, CVE credit, and cross-skill handoff. It also creates a much larger attack surface for over-redaction false positives in code excerpts (CVEs, IPs that identify production servers, etc.).
- **"Just gate every LLM call against an allowlist."** This misses third-party PII inside `<security-list>` content — that mail is allowed through approved LLMs, but the third-party identifiers are still in the body unredacted.

The two-mechanism design lets each remedy do what it is good at, and explicitly separates *what is gated* from *what is redacted*.

## 3. Goals and non-goals

### Goals

- **G1.** Third-party PII in `<security-list>` mail never enters an LLM's context in the clear.
- **G2.** `<private-list>` content cannot reach any LLM the adopter has not explicitly approved.
- **G3.** The reporter's own identity continues to flow through normally — replies, CVE credits, sync comments work as before.
- **G4.** Adopting a stricter posture (e.g. "redact collaborators too") is a single config flip, not a code change.
- **G5.** Adding a new LLM hop (summariser, classifier, delegated-analysis) is a deliberate act with PMC sign-off, not something a skill can grow into silently.
- **G6.** The mechanism is **cross-cutting**: hosting it under `tools/gmail/` would couple it to one fetch backend, hosting it under any single skill would create N drifting copies. A dedicated `tools/privacy-llm/` directory keeps the contract in one place.

### Non-goals

- **N1.** A content classifier. The redactor does not guess which strings are PII; the calling skill identifies them explicitly via `--field <type>:<value>` arguments.
- **N2.** A replacement for the existing public-surface confidentiality rules in [`AGENTS.md`](https://github.com/apache/magpie/blob/main/AGENTS.md). Those govern human-visible surfaces (public PRs, public issue comments, public mail replies); privacy-llm governs machine-routed surfaces. **Both apply, layered.**
- **N3.** An MCP-layer interception. Claude Code's MCP runtime does not (yet) support per-tool transformation hooks, so the redactor and gate-check run as explicit steps inside the skill. If a future MCP gains hook support, the call points can move into the hook without changing the contract.
- **N4.** A ratified ASF-wide approved-model registry. The default-approved list reflects the framework maintainer's working position pending ASF Privacy VP/Legal VP guidance; see §9.

## 4. Design

### 4.1 The two mechanisms at a glance

| Data class | Source | What `privacy-llm` does | Gate runs at |
|---|---|---|---|
| `<security-list>` body — reporter's own PII | Gmail / PonyMail public archive | **Not redacted.** Reporter is operationally known; identity flows through context as-is. | n/a |
| `<security-list>` body — third-party PII | Gmail / PonyMail | **Redacted.** Names, emails, phones, IPs, personal handles of *non-reporter, non-collaborator* individuals replaced with `N-…`, `E-…`, `P-…`, `IP-…`, `H-…`, `A-…` identifiers. Mapping kept local; never sent to any LLM. | Immediately after fetch, before any further processing. |
| `<private-list>` content | Gmail / PonyMail (PMC-private archive) | **Pre-flight gate.** Refuse to fetch unless every entry in the active LLM stack is in the approved-model registry. No redaction (the body is private as a whole). | Step 0 pre-flight on every skill that may read a `<private-list>` thread. |
| Outbound drafts referencing redacted third parties | Skill draft assembly | Reverse identifiers → real values just before the draft is written, only for identifiers actually referenced in the draft. | Final assembly, after the LLM step that composed the draft body. |

### 4.2 Mechanism 1 — PII redactor

#### Field types and identifier shape

| Field | Code | Identifier example | Sources skills should redact |
|---|---|---|---|
| Third-party name | `N` | `N-a3f9d2` | Body, signature lines, CVE credit fields, HackerOne/GHSA fields — names of non-reporter, non-collaborator individuals. |
| Email address | `E` | `E-b8c247` | Same scope. Reporter's own `From:` is not redacted. |
| Phone number | `P` | `P-7d4e91` | Third-party signature blocks; "call me at" patterns. |
| IP address (v4/v6) | `IP` | `IP-1a5cef` | Reproducer logs; "I tested from" lines. **Not** IPs that identify a vulnerable production server. |
| Personal handle | `H` | `H-9e3b04` | Personal GitHub/Twitter/IRC/Slack handles of third parties (not the reporter, not collaborators). |
| Postal/employer address | `A` | `A-…` | "I work at"/"my address is" lines referring to non-reporter individuals. |

The identifier format is `<TYPE>-<6-char-lowercase-hex>` where the hex is `sha256(value.strip().lower())[:24-bits]`. The 6-char default gives ~16M slots before collision pressure becomes meaningful — comfortably above any single ASF project's lifetime PII volume. On collision (two distinct values hashing to the same prefix), the second-detected value's hex is extended in 8-bit increments (`N-a3f9d2ab`, `N-a3f9d2abcd`, …) until the new identifier is unique. Extension is permanent for that mapping entry.

#### Determinism and idempotency

- **Deterministic.** `pii-redact name:"Jane Smith"` produces the same `N-…` on every machine and every run, because the identifier is derived from a normalised hash of the value. The mapping file is convenience storage for `pii-reveal`; the identifier itself is reproducible without it.
- **Idempotent.** Running `pii-redact` twice on the same input with the same `--field` values writes the mapping file once and produces identical output the second time.
- **Cross-machine compatible.** Two contributors redacting the same body produce the same identifier text without sharing the mapping file. Reveal is per-machine: a contributor can only reveal identifiers in their own local map; identifiers others created pass through unchanged (no risk of collision-corruption).

#### Mapping store

Path: `~/.config/apache-magpie/pii-mapping.json` — outside the project tree, per the framework's home-dir tool-credentials rule.

Format:

```text
{
  "version": 1,
  "entries": {
    "N-a3f9d2": {"type": "name", "value": "Jane Smith"},
    "E-b8c247": {"type": "email", "value": "jane.smith@example.com"}
  }
}
```

Properties:

- File mode `0o600`, atomic writes (`tempfile + os.replace`).
- Per-machine, never committed.
- Append-only in normal operation. Manual `rm` is supported but loses the reverse mapping; the agent has to re-fetch source data to rebuild on demand.

#### Skill wiring — the redact-after-fetch protocol

Every `<security-list>`-touching skill follows this canonical sequence:

1. **Resolve collaborators** — `gh api repos/<tracker>/collaborators --jq '.[].login'`. Same source-of-truth as the prompt-injection rule's "who is authorised to instruct the agent" lookup.
2. **Identify third-party PII candidates** in the body, signature lines, CVE credit fields, HackerOne/GHSA fields.
3. **Filter the candidate set**: drop the reporter's own values, drop every collaborator. What remains is the **should-be-redacted set** — third-party PII that is neither the reporter nor a collaborator.
4. **Call the redactor** with `--field <type>:<value>` for each remaining candidate.
5. **Use the redacted body for all subsequent processing.** The original un-redacted body is dropped from the agent's working set; if it is needed again, the skill re-fetches.

#### Reveal-before-send protocol

When a skill is about to emit a body that **(a)** carries a redacted third-party identifier AND **(b)** is destined for a surface that needs the real value (a draft reply to the reporter, a CVE credit line), `pii-reveal` runs once on the rendered text right before the send tool is called. Reveal does **not** run on internal status comments / sync messages where the redacted form is fine for the security team.

### 4.3 Mechanism 2 — approved-LLM gate

#### The default-approved registry

Four classes are pre-approved by the framework:

| Class | Rationale | Examples |
|---|---|---|
| **Claude Code itself** | The Claude Code instance running framework skills is treated as approved for the data it directly processes. See §9 for the limits of this default. | The agent invoking the skill. The checker matches the case-insensitive substring `claude code` in the bullet's raw text. |
| **`*.apache.org` endpoints** | Anything served from an ASF domain runs on infra under ASF governance — data residency, retention, access bounded by the ASF infra agreement. | Future ASF inference endpoint at e.g. `inference.apache.org`. |
| **Local-only inference** | Data never leaves the user's machine. | Ollama / vLLM / llama.cpp on `127.0.0.1`, `localhost`, `::1`. |
| **Air-gapped on-prem** | Same rationale as local, scaled to the contributor's organisation, on infra the adopter operationally controls and which has no path to a third-party LLM operator. | PMC-hosted inference appliance on a private VLAN. |

#### The opt-in tier

Every other LLM endpoint requires explicit declaration in `<project-config>/privacy-llm.md`, with three required fields per entry:

- the endpoint URL (or provider product name);
- the data-residency / retention contract that backs the choice (link to a contract clause, vendor doc, or BAA-equivalent);
- the security-team member who approved the addition (`Approved-by: <initials> <YYYY-MM-DD>`).

The framework intentionally does not ship a curated allow-list of third-party endpoints. The opt-in mechanism puts the choice — and the responsibility — on the adopting project's security team, where ASF policy expects it to live.

The gate-check **rejects placeholder text** in the `Approved-by` line — strings containing `<pmc-member-initials>`, `<initials>`, `<yyyy-mm-dd>`, or the literal `yyyy-mm-dd` are not accepted as a valid sign-off. An adopter that copies the template and forgets to fill in the approver gets a clear failure rather than a silent pass.

Setup recipes in [`docs/setup/privacy-llm.md`](https://github.com/apache/magpie/blob/main/docs/setup/privacy-llm.md) cover six concrete variants: Claude Code only, Local Ollama, Local vLLM, Apache-hosted endpoint, AWS Bedrock (opt-in), Direct Anthropic API (opt-in).

#### The pre-flight check

Skills run this check at Step 0 by shelling out to the `privacy-llm-check` console script (PR #51):

```text
uv run --project <framework>/tools/privacy-llm/checker privacy-llm-check \
  --reads-private-list                 # set when the skill may read <private-list>
```

The checker:

1. **Locates the config.** Precedence: `--config <path>` → `$PRIVACY_LLM_CONFIG` → `<cwd>/.apache-magpie/privacy-llm.md` → `<cwd>/.apache-magpie-overrides/privacy-llm.md`.
2. **Parses** the *Currently configured LLM stack* and *Approved third-party endpoints (opt-in)* sections. The parser is permissive about comments and whitespace but strict about the section-heading anchors.
3. **Applies the rules** for every active-stack entry:
   - Claude Code → ✓ default-approved
   - URL host ending in `.apache.org` → ✓ default-approved
   - URL host in `{localhost, 127.0.0.1, ::1}` → ✓ default-approved
   - Otherwise: match against the opt-in registry. A valid match requires a non-empty *Data-residency contract* sub-bullet AND a non-placeholder *Approved-by* sub-bullet.
4. **Returns an exit code:**
   - `0` — all entries approved.
   - `1` — one or more entries unapproved (or empty stack); stderr lists the offending entries plus a `Fix: edit <path>` pointer.
   - `2` — config file could not be located or parsed.

The check is deliberately conservative: any single unapproved entry stops the skill. Adding a new LLM hop is a deliberate act, not an emergent one.

**Defence-in-depth:** the gate-check is **also required** for `<security-list>`-only skills, even though their body classification permits Claude-Code-default LLMs by construction. Running the check at Step 0 ensures the adopter's config is in a sane state — no half-configured opt-in entries, no LLMs in the active stack the adopter forgot to approve — before any private content flows. The `--reads-private-list` flag controls only the printed banner; the validation logic is the same either way.

### 4.4 Mechanism 3 (defence-in-depth) — egress-allowlist gateway

The PII redactor and approved-LLM gate both operate at the application layer: they constrain what a skill deliberately sends to an LLM. Neither stops an *unintended* outbound flow — a buggy skill, a mis-wired tool, or a prompt-injection payload hidden in an inbound report that coaxes the agent into `curl`-ing private data to an attacker-controlled host. [`docs/setup/secure-agent-setup.md`](https://github.com/apache/magpie/blob/main/docs/setup/secure-agent-setup.md) flags exactly this: network egress via `Bash(curl *)` / `Bash(wget *)` bypasses the sandbox's own proxy.

The egress-allowlist gateway closes that gap at the network layer. It is a local `proxy.py` forward proxy (shipped as [`tools/egress-gateway/`](../../tools/egress-gateway/)) that enforces a **default-deny host allowlist** in its `before_upstream_connection` hook: any CONNECT / request to a host not on the allowlist is rejected with `403` before a socket is opened. Tools point `HTTPS_PROXY` / `HTTP_PROXY` at it; Python `urllib`-based tools (ponymail, whimsy, jira, …) honour that with no code change.

| Property | Value |
|---|---|
| Layer | Network egress (host-level), below the application-layer LLM controls |
| Policy | Default-deny; allowlist mirrors `sandbox.network.allowedDomains` (ASF infra, GitHub, Google APIs, PyPI), suffix-matched; loopback always allowed; adopter extends via `EGRESS_ALLOW_EXTRA` |
| Granularity | Host only — HTTPS is tunnelled via CONNECT, so no URL-path or payload inspection (no TLS interception) |
| Relationship | Defence-in-depth. Layered *under* mechanisms 1 + 2, never a replacement: the redactor still strips third-party PII, the gate still bounds which LLM may receive a body, and the gateway additionally bounds which host *any* tool may reach. |

The gateway runs **outside the sandbox** — it must bind a listener and make unrestricted outbound, which is precisely its job as the chokepoint. Sandboxed tools reach it over loopback, which requires `localhost` / `127.0.0.1` in `sandbox.network.allowedDomains` (loopback-only; this does not widen the internet egress surface — that becomes the gateway's responsibility). The gateway's allowlist and `sandbox.network.allowedDomains` encode the same egress policy at two layers and should be kept in sync.

This mechanism is **optional and provisional**: it ships as a tool with a documented contract and unit-tested allowlist policy, but it is not yet wired into a setup skill or the `privacy-llm-check` gate. See §10.6.

## 5. Data flow

```text
                 ┌─────────────────────┐
fetch (Gmail / ──┤  raw body + PII     │
PonyMail)        └──────────┬──────────┘
                            │  pii-redact (per-field, after collaborator filter)
                            ▼
                 ┌──────────────────────┐
                 │ body w/ identifiers  │ ◄─── what Claude / any
                 └──────────┬───────────┘      downstream LLM ever sees
                            │
                  …agent processing,
                  draft composition,
                  cross-skill handoff…
                            │
                            ▼
                 ┌──────────────────────┐
                 │ draft w/ identifiers │
                 └──────────┬───────────┘
                            │  pii-reveal (only at outbound boundary)
                            ▼
                 ┌──────────────────────┐
                 │ draft w/ real names  │ ──► sent to reporter
                 └──────────────────────┘
```

Three rules govern the lifecycle:

1. **Redact immediately after fetch.** The window between the `mcp__claude_ai_Gmail__get_thread` (or equivalent) tool call and the redact call is a single tool invocation wide.
2. **Operate on identifiers throughout.** All intermediate work (analysis, summarisation, draft composition, prior-art lookup, cross-skill handoff) runs against `<TYPE>-<hex>` text.
3. **Reveal only at the outbound boundary.** `pii-reveal` runs exactly once per draft, at the moment the rendered draft is handed to the send/draft-create tool. It does not run while the agent is *thinking about* the draft — only when the bytes are leaving the framework.

The gate-check (`privacy-llm-check`) sits **upstream** of this pipeline at Step 0 — before any fetch, before any redact, before the agent has touched private data at all. Its failure mode is "skill never starts"; its success mode is "skill starts and the redactor takes over downstream".

## 6. Implementation

`tools/privacy-llm/` ships **two stdlib-only `uv` Python sub-tools**, each with its own `pyproject.toml`, lock file, and test suite.

### 6.1 The redactor sub-tool — `tools/privacy-llm/redactor/`

Three console scripts:

| Script | Purpose |
|---|---|
| `pii-redact` | Replace declared PII values in stdin with identifiers; persist new mappings to the local file. |
| `pii-reveal` | Replace identifiers in stdin with stored real values from the local mapping. |
| `pii-list` | Print the current mapping for debugging (text or JSON). |

Three call sites in skill files:

```text
# Redact (immediately after fetch):
echo "$BODY" | uv run --project <framework>/tools/privacy-llm/redactor pii-redact \
  --field name:"Other Researcher" \
  --field email:"other@example.com" \
  --field handle:"otherresearcher-personal"

# Reveal (only at outbound boundary):
echo "$DRAFT" | uv run --project <framework>/tools/privacy-llm/redactor pii-reveal

# List (debugging only — output goes to user's terminal, never to LLM):
uv run --project <framework>/tools/privacy-llm/redactor pii-list
```

`<framework>` is the standard placeholder convention — substitutes to the snapshot path inside an adopter, or to `.` standalone. The redactor reads no config file: it just does what the caller passes via `--field`. Per-project knobs are applied by the calling skill (see §7).

The implementation is **stdlib-only** by design — `argparse`, `hashlib`, `json`, `pathlib`, `tempfile`, `os`. No third-party runtime dependencies. The dev group adds `pytest`, `ruff`, `mypy` for lint and test. Tests all passing.

### 6.2 The checker sub-tool — `tools/privacy-llm/checker/` (PR #51)

One console script:

| Script | Purpose |
|---|---|
| `privacy-llm-check` | Parse `<project-config>/privacy-llm.md`, verify every entry in the *Currently configured LLM stack* section is approved per the rules in [`models.md`](https://github.com/apache/magpie/blob/main/tools/privacy-llm/models.md). |

The internal structure is two modules:

- **`checker/config.py`** — parses the markdown config file into `LLMEntry` and `OptInEntry` dataclasses. Permissive about comments and whitespace; strict about the heading anchors `## Currently configured LLM stack` and `## Approved third-party endpoints (opt-in)` since those are the contract surfaces the gate-check relies on.
- **`checker/check.py`** — applies the default-approval rules (Claude Code substring match, `*.apache.org` host suffix, local-host set), falls back to the opt-in registry, and produces a `Verdict` per stack entry with a human-readable reason.

Skill invocation pattern:

```text
# Default lookup against <cwd>/.apache-magpie/privacy-llm.md or
# <cwd>/.apache-magpie-overrides/privacy-llm.md:
uv run --project <framework>/tools/privacy-llm/checker privacy-llm-check \
  --reads-private-list

# Sample success output (stdout):
# privacy-llm-check: every active-stack entry is approved (skill reads <private-list>)
# ✓ Claude Code (the agent running framework skills) — Claude Code itself (default-approved)
# ✓ Local Ollama at http://127.0.0.1:11434/ — local-only inference at 127.0.0.1 (default-approved)

# Sample failure (stderr, exit 1):
# privacy-llm-check: 1 of 2 active-stack entries are not approved.
# ✓ Claude Code (the agent running framework skills) — Claude Code itself (default-approved)
# ✗ AWS Bedrock at https://bedrock-runtime.eu-central-1.amazonaws.com — no default-approval rule matches and no opt-in entry was declared for this LLM. Add an entry under 'Approved third-party endpoints (opt-in)' with a Data-residency contract line and an Approved-by sign-off, or remove this LLM from the active stack.
#
# Fix: edit /repo/.apache-magpie/privacy-llm.md per tools/privacy-llm/models.md.
```

Implementation: stdlib-only (`argparse`, `dataclasses`, `re`, `urllib.parse`, `pathlib`). Test count: **33 unit tests**, all passing, including a fixture test that the shipped [`projects/_template/privacy-llm.md`](https://github.com/apache/magpie/blob/main/projects/_template/privacy-llm.md) parses + approves out of the box. Pre-commit hooks (ruff, ruff-format, mypy, pytest) wired into the framework's `prek` config in PR #51.

### 6.3 What never reaches any LLM

The framework treats these surfaces as off-limits to LLM context, even when an "approved" LLM is in the stack:

- The contents of `~/.config/apache-magpie/pii-mapping.json`. The file is read by `pii-redact` / `pii-reveal` only. Skills MUST NOT include the mapping in any LLM-bound prompt, summary, or status comment. For debugging, run `pii-list` in the user's terminal — that output goes to the user's screen, not to Claude's context.
- The `--field <type>:<value>` arguments themselves. Every value passed there is exactly what the redactor is replacing.
- Any draft text *before* `pii-reveal` runs, when the destination is a non-internal surface (e.g. a public PR comment) — the body would still carry identifiers, which leak no PII, but skills should not emit identifier-laden drafts to non-internal destinations by accident. The destination check in the approved-LLM gate is a separate safety net for this.

### 6.4 The egress gateway — `tools/egress-gateway/`

A `proxy.py`-based forward proxy whose only first-party code is the allowlist plugin (`egress_gateway.allowlist.EgressAllowlistPlugin`). The host-matching policy (`host_allowed`) is a pure function, unit-tested in isolation; the proxy.py integration is intentionally not exercised in CI (it needs to bind a port). Unlike the stdlib-only `privacy-llm` sub-tools, this one carries a third-party runtime dependency (`proxy.py`) — which is why it is a separate tool rather than a `privacy-llm` sub-tool. Contract: [`tools/egress-gateway/tool.md`](../../tools/egress-gateway/tool.md); how-to: [`tools/egress-gateway/README.md`](../../tools/egress-gateway/README.md).

## 7. Adopter configuration

Adopters declare their privacy-LLM posture in a single markdown file at `<project-config>/privacy-llm.md` (template at [`projects/_template/privacy-llm.md`](https://github.com/apache/magpie/blob/main/projects/_template/privacy-llm.md)). The file has four sections:

- **Currently configured LLM stack** — every LLM the adopter has wired into any skill, one per line.
- **Approved third-party endpoints (opt-in)** — entries beyond the default-approved set, each with the data-residency contract link and PMC `Approved-by` line. The checker rejects placeholder text (`<initials>`, `<YYYY-MM-DD>`, …).
- **Private mailing lists** — every PMC-private list the security team reads. The framework's `tools/ponymail/` reuses this list for its `private_lists` config knob, so the two stay in sync.
- **Redaction configuration** — three per-project knobs:

| Knob | Default | Purpose |
|---|---|---|
| `collaborator_source` | `<tracker>` from `<project-config>/project.md` | Override if collaborators are tracked in a different repo (parent-org roster, separate roster repo). |
| `collaborator_exemption` | `enabled` | Flip to `disabled` for a stricter posture: every non-reporter individual gets redacted, including collaborators. |
| `redaction_field_types` | all six | Disable individual types if a project has decided a different sensitivity tradeoff (rare). |

The redactor itself reads no config — knobs are applied by the calling skill at filter time, before `--field` arguments are constructed. The checker reads only the *Currently configured LLM stack*, *Approved third-party endpoints (opt-in)* sections — the other knobs are skill-side concerns. A skill that does not respect a knob is a framework bug.

## 8. Skill wiring summary

Every skill that touches `<security-list>` (or may escalate to `<private-list>`) carries a Step 0 *Privacy-LLM contract* bullet that calls `privacy-llm-check`, plus the redact-after-fetch and (where applicable) reveal-before-send steps.

| Skill | Reads | Drafts | Step 0 gate-check | Redact-after-fetch | Reveal-before-send |
|---|---|---|---|---|---|
| `security-issue-import` | `<security-list>` | reporter receipt-of-confirmation reply | ✓ | ✓ | ✓ |
| `security-issue-sync` | `<security-list>`, may escalate to `<private-list>` | reporter status updates | ✓ (`--reads-private-list`) | ✓ | ✓ |
| `security-issue-invalidate` | `<security-list>` | reporter invalidation reply | ✓ | ✓ | ✓ |
| `security-cve-allocate` | tracker + Vulnogram | (tracker already redacted) | ✓ | n/a (downstream of redaction) | n/a |
| `security-issue-import-from-md` | adopter-supplied markdown | n/a | ✓ | n/a | n/a |
| `security-issue-import-from-pr` | public PR | n/a | n/a (no `<security-list>` content) | n/a | n/a |
| `security-issue-fix` | tracker (already redacted) | n/a (PR is public; no PII) | n/a | n/a | n/a |
| `security-issue-deduplicate` | two trackers (already redacted) | n/a | n/a | n/a | n/a |

Only `security-issue-sync` passes `--reads-private-list` today (it may escalate threads to PMC-private foundation lists). The other wired skills run the checker without the flag — the validation logic is the same; the flag only affects the printed banner.

## 9. Trust boundaries and status

The default-approved registry reflects the framework maintainer's **working position** pending ASF Privacy VP/Legal VP ratification of an authoritative approved-LLM list for foundation private data. Specifically:

- The "Claude Code itself" default reflects the framework maintainer's current trust posture. If ASF Privacy VP/Legal VP subsequently rules that Anthropic-hosted endpoints require a data-processing agreement for foundation private data, the framework will narrow this default and bump the registry version. Adopters running Variant 1 (Claude Code only) at that point will need to re-evaluate.
- The `*.apache.org` blanket approval assumes infra-level governance. If a future ASF endpoint runs at `*.apache.org` but proxies to a third-party LLM, that endpoint may need re-classification.

When ASF Privacy VP/Legal VP do ratify a list, [`tools/privacy-llm/models.md`](https://github.com/apache/magpie/blob/main/tools/privacy-llm/models.md) becomes the *pointer* to that list rather than the list itself, and the default-approved entries get re-checked against it. Until then, that file is the framework's source-of-truth for adopters and the rationale-of-record for the choices it encodes.

PMC members and ASF Privacy VP/Legal VP reviewers who want to formalise the list should open an issue on [`apache/magpie`](https://github.com/apache/magpie) referencing this RFC.

## 10. Open questions and future work

### 10.1 Resolved in PR-3

Earlier drafts of this RFC listed "gate-call wiring" as deferred to PR-3. **PR #51 has now landed it**: the `tools/privacy-llm/checker/` sub-tool ships `privacy-llm-check` with the full default-approved logic, opt-in matching, placeholder rejection, and config auto-location. Every Gmail-touching skill calls it explicitly at Step 0. The full two-mechanism design is now live, end-to-end.

### 10.2 ASF Privacy VP/Legal VP ratification

The single largest remaining open question is the ASF-wide policy for AI-assisted handling of foundation private data. The framework's working position is documented and adopter-overridable, but a ratified list would let the framework bump from "provisional" to "stable" and remove the burden of per-project sign-off for default-approved entries.

Concrete asks for the ASF Privacy VP / Legal VP:

- **Confirm or narrow the "Claude Code itself" default.** Today the framework treats the running Claude Code instance as approved for the data it processes. A formal data-processing agreement between ASF and Anthropic for foundation private data would make this stable; absence of one might narrow the default to "Claude Code is approved only for `<security-list>` content, never for `<private-list>`".
- **Confirm the `*.apache.org` blanket.** The framework assumes any endpoint at an ASF domain runs under ASF infra governance. A formal articulation of what that means (including whether `*.apache.org` proxies to third parties are permitted) would let the framework codify the boundary precisely.
- **Publish a curated allow-list of opt-in endpoints**, if desired. The framework currently leaves the list open and shifts the responsibility to per-project security teams. A foundation-wide list would centralise the diligence.

### 10.3 MCP-layer hooks

If a future Claude Code MCP runtime gains per-tool transformation hooks, the redactor and gate-check call points can move from explicit-step-inside-the-skill into the hook without changing the contract. The current explicit-step design is forward-compatible with that migration: the `--field <type>:<value>` interface decouples *what to redact* (skill knowledge) from *how to redact* (helper logic), and the checker reads the same `<project-config>/privacy-llm.md` an MCP hook would.

### 10.4 Mapping-file lifecycle tools

The framework currently does not ship a cleanup tool for the mapping file. Manual `rm` is supported but loses the reverse mapping. Possible future additions: `pii-list --filter-stale` (entries that have not been revealed in N days), `pii-export` (cross-machine sync), `pii-rotate` (re-hash with a longer prefix). None blocking; all out of scope for the foundation.

### 10.5 Doc-cleanup follow-up

A small handful of references in [`docs/setup/privacy-llm.md`](https://github.com/apache/magpie/blob/main/docs/setup/privacy-llm.md) still describe `privacy-llm-check` as "PR-3" pending. Now that PR #51 has merged, those should be cleaned up to drop the "(PR-3)" phrasing — minor doc churn, no contract change. Filed as a follow-up for the next cleanup PR.

### 10.6 Egress-gateway wiring

The egress-allowlist gateway (§4.4, [`tools/egress-gateway/`](../../tools/egress-gateway/)) ships as a tool with a documented contract but is not yet wired into the setup flow. Possible follow-ups: a `setup-isolated-setup-*` step that launches / health-checks the gateway and persists `HTTPS_PROXY` into the adopter's per-machine settings; sourcing the gateway allowlist directly from `sandbox.network.allowedDomains` so the two cannot drift; and a `privacy-llm-check`-style assertion that the gateway is reachable when an adopter has opted into it. None blocking — the tool is usable standalone today.

## 11. References

- **Source-of-truth contracts**
  - [`tools/privacy-llm/tool.md`](https://github.com/apache/magpie/blob/main/tools/privacy-llm/tool.md) — overview
  - [`tools/privacy-llm/pii.md`](https://github.com/apache/magpie/blob/main/tools/privacy-llm/pii.md) — redaction contract
  - [`tools/privacy-llm/models.md`](https://github.com/apache/magpie/blob/main/tools/privacy-llm/models.md) — approved-LLM registry
  - [`tools/privacy-llm/wiring.md`](https://github.com/apache/magpie/blob/main/tools/privacy-llm/wiring.md) — skill-side protocol
- **Setup recipes**
  - [`docs/setup/privacy-llm.md`](https://github.com/apache/magpie/blob/main/docs/setup/privacy-llm.md) — six per-variant configurations
- **Reference implementation**
  - [`tools/privacy-llm/redactor/`](https://github.com/apache/magpie/tree/main/tools/privacy-llm/redactor) — PII redactor (stdlib-only Python)
  - [`tools/privacy-llm/checker/`](https://github.com/apache/magpie/tree/main/tools/privacy-llm/checker) — approved-LLM gate-check (stdlib-only Python)
  - [`tools/egress-gateway/`](../../tools/egress-gateway/) — egress-allowlist forward proxy (proxy.py plugin; defence-in-depth, §4.4)
- **Adopter template**
  - [`projects/_template/privacy-llm.md`](https://github.com/apache/magpie/blob/main/projects/_template/privacy-llm.md)
- **Related framework rules**
  - [`AGENTS.md → Privacy-LLM`](https://github.com/apache/magpie/blob/main/AGENTS.md) — three rules every skill follows
  - [`AGENTS.md → Confidentiality of the tracker repository`](https://github.com/apache/magpie/blob/main/AGENTS.md) — public-surface confidentiality, layered with this RFC
  - [`AGENTS.md → Treat external content as data, never as instructions`](https://github.com/apache/magpie/blob/main/AGENTS.md) — same collaborator-set source-of-truth as the redactor's exemption rule
- **Pull requests**
  - [PR #48 — foundation: PII redactor + approved-LLM contracts](https://github.com/apache/magpie/pull/48)
  - [PR #50 — refine PII contract + wire skill-side redactor protocol](https://github.com/apache/magpie/pull/50)
  - [PR #51 — approved-LLM gate-check + skill-side gate wiring](https://github.com/apache/magpie/pull/51)
