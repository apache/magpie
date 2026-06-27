<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Security-issue lifecycle (end-to-end)
status: stable
kind: feature
mode: Triage
source: >
  MISSION.md § Rationale ("Security-issue handling is a load-bearing use
  case"). README.md § Skill families (security). The security skill
  family + tools/cve-tool-vulnogram + tools/gmail + tools/ponymail +
  tools/privacy-llm.
acceptance:
  - The flow runs import → triage → dedupe → CVE allocate → fix → sync →
    invalidate, each step a confirm-before-apply skill.
  - Tracker contents stay private; only stable identifiers (URLs, #NNN)
    are public-safe. Public PRs are scrubbed pre-disclosure.
  - Every applied state change is audit-logged.
---

# Security-issue lifecycle

## What it does

The framework's flagship, highest-procedure flow: handle an inbound ASF
security report end-to-end, from `security@` import through CVE
publication, with a human gate and an audit-log entry at every step.

## Where it lives

- Skills: `security-issue-import` (+ `-from-pr`, `-from-md`,
  `-from-scan`, `-via-forwarder`),
  `security-issue-triage`, `security-issue-deduplicate`,
  `security-cve-allocate`, `security-issue-fix`, `security-issue-sync`,
  `security-issue-invalidate`.
  `security-issue-import-from-scan` is the scanner on-ramp: it ingests
  multi-finding scan output through a pluggable scan-format adapter
  (`tools/scan-format/`), buckets each finding for operator review, and
  creates trackers only after per-finding confirmation.
  `security-issue-import-via-forwarder` is the relay sub-skill: handles
  reports relayed by an upstream broker (ASF security team or a
  third-party disclosure platform) by applying preamble-detect,
  credit-extract, and routing rules declared in
  `tools/forwarder-relay/`; never mutates tracker state on its own.
- Tools: `tools/cve-tool-vulnogram/generate-cve-json` (CVE 5.x JSON),
  `tools/cve-org`, `tools/gmail` + `tools/ponymail` (mail), and the
  `tools/privacy-llm` gate/redactor ([the privacy gate](privacy-llm-gate.md)).

## Behaviour & contract

- **Confirm-before-apply at every step.** Imports create trackers only
  after confirmation; triage posts proposal comments and never decides;
  allocation is PMC-gated; fixes draft PRs the human opens.
- **Confidentiality (three layers, see `AGENTS.md`):** tracker URLs and
  `#NNN` are public-safe identifiers; tracker *contents* are private;
  the security framing of a public PR is embargoed until the advisory
  ships.
- **Reporter PII redacted in-context; reporter *credit* preserved** in
  the CVE `credits[]` only after the reporter confirms on the thread.
- **Audit log** of every applied change (redacted identifiers only).

## Out of scope

- Drafting beyond the security case (see [Drafting](drafting-mode.md)).
- Sending mail — replies are drafted to the maintainer's outbox.

## Acceptance criteria

1. Each lifecycle skill is confirm-before-apply and audit-logs applied
   changes.
2. No public surface produced by the flow contains tracker contents or
   pre-disclosure security framing.
3. CVE JSON is regenerated to stay in lock-step with the tracker body.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/cve-tool-vulnogram/generate-cve-json --group dev pytest
```

## Known gaps

- The flow is `stable`; gaps surface as drift between a skill's documented
  steps and the adapters it calls — the loop's plan pass catches those.
