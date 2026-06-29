<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Privacy-LLM gate + PII redaction
status: stable
kind: feature
mode: infra
source: >
  MISSION.md § Privacy, security and supply-chain integrity
  ("Privacy-aware LLM routing", "PII redaction at the boundary").
  Implemented in tools/privacy-llm/ (checker, redactor, wiring.md, pii.md)
  and documented in docs/setup/privacy-llm.md.
acceptance:
  - Private content reaches only LLMs the project's PMC has approved; the
    gate refuses to route private bytes through a non-approved model.
  - PII is redacted to stable hashed identifiers before any LLM read; the
    reverse map stays on the maintainer's local disk (mode 0600).
  - Every public artefact is scrubbed for private-content leakage before
    it leaves the framework's control.
---

# Privacy-LLM gate + PII redaction

## What it does

Treats private content — security reports, embargoed CVE detail,
PMC-private mail, contributor PII — as chain-of-custody material. Three
mechanisms: an **approved-LLM gate** that verifies the model-of-the-moment
is on the PMC's allow-list before any private read; a **redactor** that
maps reporter names/emails/IPs to stable hashed identifiers before the
LLM sees them; and a **confidentiality scrub** that checks every public
artefact for leakage before emission.

## Where it lives

- `tools/privacy-llm/checker/` — the approved-LLM gate.
- `tools/privacy-llm/redactor/` — the PII redactor (name→`N-<hash>`,
  email→`E-<hash>`, IP→`IP-<hash>`).
- `tools/privacy-llm/wiring.md` — the redact-after-fetch protocol every
  Gmail/PonyMail-reading skill follows.
- `tools/privacy-llm/pii.md` — the PII pattern catalogue.
- `docs/setup/privacy-llm.md` — adopter-facing setup.

## Behaviour & contract

- **Policy is the PMC's; the gate is the framework's.** The approved-LLM
  list is per-PMC. The default: agent host trusted, `*.apache.org`
  auto-approved, `localhost` for local inference, everything else opt-in.
- **Redact before read; reveal locally.** Skills operate on hashed
  identifiers; the reverse map never goes to an LLM and is never committed.
- **Reporter credit is preserved** (CVE `credits[]`) only after the
  reporter confirms on the inbound thread — credit is a deliberate output,
  not in-context PII.
- **Confidentiality scrub before public emission** — regex for CVE IDs in
  pre-disclosure PRs, reporter names from the local map, list addresses,
  and any project-declared private string; failures stop the flow.
- **Audit log is privacy-aware** — references hashed identifiers, never
  raw PII.
- **Public branch names are public artefacts.** Generated branch names,
  commit-message examples, PR-body templates, changelog snippets, and
  release-note text must avoid embargo-breaking security terms before
  disclosure. In particular, pre-disclosure public branch names must not
  contain CVE IDs, `security`, `vulnerability`, `advisory`, or
  tracker-private title fragments.

## Out of scope

- Setting the approved-LLM *policy* (that is the PMC's, per adopter).
- Enforcing OS-level isolation — that is the sandbox
  ([agent-isolation-sandbox.md](agent-isolation-sandbox.md)).

## Acceptance criteria

1. The gate blocks a private read when the active model is not approved.
2. The redactor produces stable hashed identifiers and keeps the reverse
   map local (0600, gitignored).
3. The scrub catches CVE IDs / reporter names / list addresses before any
   public write.
4. Generated public branch-name examples are scrubbed for CVE IDs and
   embargoed security framing before use.

## Validation

```bash
uv run --project tools/privacy-llm --group dev pytest
```

## Known gaps

- `stable`; gaps surface as new PII patterns or new public-emission
  surfaces not yet covered by the scrub — caught as drift by the plan pass.
- **Branch-name confidentiality validation is missing.** Security-fix
  workflows already require neutral branch names, but no deterministic
  check scans skill/docs examples for CVE IDs or embargoed terms in
  generated branch names.
