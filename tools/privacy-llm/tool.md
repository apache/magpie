<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Tool: privacy-llm](#tool-privacy-llm)
  - [What this tool provides](#what-this-tool-provides)
  - [Why this is its own tool](#why-this-is-its-own-tool)
  - [The two mechanisms — what is gated, and what is redacted](#the-two-mechanisms--what-is-gated-and-what-is-redacted)
  - [How skills consume this tool](#how-skills-consume-this-tool)
  - [What this tool is NOT for](#what-this-tool-is-not-for)
  - [Failure modes](#failure-modes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Tool: privacy-llm

This directory documents the **privacy-llm** tool adapter — the
contract every framework skill follows when it touches private mail
content (`<security-list>` reporter mail, `<private-list>` PMC
escalation mail) or routes that content through any LLM step.

The tool exists because two distinct, easily-confused privacy
concerns share a single workflow:

1. **Reporter PII** in `<security-list>` content — the body is OK to
   process, but the reporter's *identity* (name, email, phone, IP,
   personal handles) must never enter any LLM in the clear.
2. **Wholly private list content** on `<private-list>` and other
   PMC-private foundation lists — the body itself must never reach
   a non-approved LLM.

These two concerns produce different remediations. Mixing them up
(e.g. assuming PII redaction is enough for `<private-list>` content)
is a real foot-gun the framework guards against.

A project opts into this tool by naming it in its manifest under
*Tools enabled*. For the adopting project see
[`../../<project-config>/project.md`](../../<project-config>/project.md#tools-enabled).
The tool is **mandatory** for any project that uses `tools/gmail/`
or `tools/ponymail/` — those tools surface private content into the
agent's context, and `privacy-llm` is what stops it from leaking.

## What this tool provides

| Capability | File | What it covers |
|---|---|---|
| PII redaction contract | [`pii.md`](pii.md) | Which fields are PII, the hash-prefixed identifier format (`N-a3f9d2`, `E-b8c247`, …), the local mapping store at `~/.config/apache-magpie/pii-mapping.json`, the redact-then-reveal lifecycle. |
| Approved-LLM registry | [`models.md`](models.md) | Which LLMs the framework treats as privacy-approved (Claude Code by default; anything at `*.apache.org`; local Ollama / vLLM; everything else opt-in), how to declare additions in `<project-config>/privacy-llm.md`, and what the pre-flight gate checks. |
| Skill-wiring pattern | [`wiring.md`](wiring.md) | The canonical step-by-step pattern every `<security-list>`- or `<private-list>`-touching skill follows when applying the contract — Step 0 pre-flight, redact-after-fetch, reveal-before-send, plus edge cases. Skill `SKILL.md` files link here from their pre-flight section rather than copying the protocol. |
| Per-project configuration | [`projects/_template/privacy-llm.md`](../../projects/_template/privacy-llm.md) | Template the adopter copies into `<project-config>/privacy-llm.md` to declare their LLM stack, private mailing-list set, collaborator source, and redaction-tuning knobs (collaborator exemption, enabled field types). Defaults are documented inline. |
| Setup recipes | [`../../docs/setup/privacy-llm.md`](../../docs/setup/privacy-llm.md) | Copy-pasteable configurations for the supported variants — local inference, Apache-hosted endpoint, AWS Bedrock, opt-in third-party. Marked **provisional pending ASF Legal Affairs ratification** of an authoritative approved-model list. |
| Reference Python helper — redactor | [`redactor/`](redactor/) | A small `uv` project exposing three console scripts — `pii-redact`, `pii-reveal`, `pii-list` — that skills shell out to so the redaction lifecycle is consistent across every consumer. |
| Reference Python helper — gate-check | [`checker/`](checker/) | A small `uv` project exposing one console script — `privacy-llm-check` — that parses `<project-config>/privacy-llm.md` and verifies every active-stack entry is approved per [`models.md`](models.md). Skills shell out to it at Step 0 (pre-flight). |

## Why this is its own tool

The redaction lifecycle is **cross-cutting**: it sits between every
private-data fetch tool (Gmail, PonyMail, future mail backends) and
every LLM consumer of that data (Claude itself, any future
delegated-summarization step, any non-Claude analysis hop). Hosting
it under `tools/gmail/` or `tools/ponymail/` would couple it to one
backend; hosting it under any single skill would create N copies
that drift. A dedicated `tools/privacy-llm/` directory keeps the
contract in one place and the helper code in one project.

The same argument applies to the approved-model registry — it gates
*outbound* LLM calls regardless of which skill is making the call,
so it must live above the per-skill / per-tool layer.

## The two mechanisms — what is gated, and what is redacted

The framework's two privacy mechanisms apply to different data
classes and run at different points in the pipeline:

| Data class | Source | What `privacy-llm` does | Gate runs at |
|---|---|---|---|
| `<security-list>` body — reporter's own PII | Gmail / PonyMail public archive | **Not redacted.** The reporter sent the mail and is operationally known to the security team (CVE credit, reply threads, etc.). Their identity flows through the agent's context as-is. | n/a |
| `<security-list>` body — third-party PII | Gmail / PonyMail | **Redacted** — names, emails, phones, IPs, personal handles of *non-reporter, non-collaborator* individuals replaced with hash-prefixed identifiers (`N-…`, `E-…`, …). Collaborators on `<tracker>` (`gh api repos/<tracker>/collaborators`) are exempt — already public/known. Mapping kept local; never sent to any LLM. | Immediately after fetch, before any further processing. |
| `<private-list>` content | Gmail / PonyMail (PMC-private archive) | **Pre-flight gate** — refuse to fetch unless the active LLM stack is in the approved-model registry. No redaction (the body is private as a whole). | Step 0 pre-flight on every skill that may read a `<private-list>` thread. |
| Outbound drafts that reference redacted third parties | Skill draft assembly | Reverse identifiers → real names just before the draft is written (only for third-party identifiers actually referenced in the draft). | Final assembly, after the LLM step that composed the draft body. |

The decision tree the skill follows on every fetch is captured in
[`pii.md`](pii.md) (redaction lifecycle) and [`models.md`](models.md)
(gate semantics).

## How skills consume this tool

Three integration points:

1. **Step 0 — pre-flight gate.** Skills that may read
   `<private-list>` content (`security-issue-import`,
   `security-issue-sync`, `security-issue-fix`,
   `security-issue-deduplicate` when escalating to PMC) read the
   adopter's `<project-config>/privacy-llm.md` and refuse to run if
   no approved model is wired. The check is implemented per
   [`models.md`](models.md#the-pre-flight-check).
2. **After fetch — redact PII.** Any skill that fetches Gmail or
   PonyMail content shells out to `pii-redact` on the body before
   doing further processing. The redactor is idempotent — running
   twice on already-redacted text produces the same identifiers and
   does not double-encode.
3. **Before send — reveal identifiers.** When assembling a draft
   that needs real names (the reporter reply, a CVE credit line),
   shell out to `pii-reveal` on the rendered draft text. Reveal
   only happens at the *outbound boundary* — the LLM step that
   composes the draft operates on identifiers throughout.

Concrete invocation patterns are in
[`pii.md`](pii.md#how-skills-call-the-redactor) and
[`models.md`](models.md#how-skills-call-the-gate).

## What this tool is NOT for

- **Not a substitute for the existing confidentiality rules in
  [`AGENTS.md`](../../AGENTS.md#confidentiality-of-the-tracker-repository).**
  Those rules govern *human-visible* surfaces (public PRs, public
  issue comments, public mailing-list replies). `privacy-llm`
  governs *machine-routed* surfaces (LLM context, LLM API calls,
  delegated-summarization hops). Both apply; they are layered.
- **Not a content classifier.** The redactor doesn't try to *guess*
  which strings are PII — skills hand it the field values
  explicitly (third-party names parsed out of the body, emails
  from quoted headers other than the reporter's own, etc.). PII
  discovery + the reporter-vs-third-party + collaborator-vs-not
  filtering is the skill's job; redaction is the redactor's job.
- **Not an MCP-layer interception.** Claude Code's MCP runtime does
  not (yet) support per-tool transformation hooks. The redactor
  runs as an explicit step *inside the skill*, not as a transparent
  MCP middleware. If a future MCP gains hook support, the skill
  layer can move the redactor call into the hook without changing
  the contract.

## Failure modes

| Symptom | Likely cause | Remediation |
|---|---|---|
| Skill refuses to run with "no approved privacy LLM configured" | Adopter has not yet written `<project-config>/privacy-llm.md`, or it lists no approved entries | Follow [`docs/setup/privacy-llm.md`](../../docs/setup/privacy-llm.md) — the default `Claude Code` entry is enough for the local-only case |
| `pii-reveal` returns text with `N-a3f9d2`-style identifiers still in place | The mapping file at `~/.config/apache-magpie/pii-mapping.json` was deleted, truncated, or moved | Re-fetch the source; the redactor regenerates identifiers deterministically from the raw values, but it cannot reverse identifiers it has no mapping for |
| `pii-redact` produces different identifiers across runs | Identifier format was changed (the framework bumped the hash length, or the prefix scheme) — see the version field in `pii-mapping.json` | Migration logic lives in the next framework version's release notes; until then keep the mapping file pinned |
| Skill is meant to read `<security-list>` but is being gated by the approved-model pre-flight | Adopter has incorrectly classified `<security-list>` as private in `<project-config>/privacy-llm.md` | Remove `<security-list>` from the private-list set; PII redaction (which IS required for `<security-list>`) is independent of the gate |
