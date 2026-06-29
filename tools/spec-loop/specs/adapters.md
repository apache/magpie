<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Adapters (Gmail / PonyMail / Jira / GitHub / mail-source)
status: experimental
kind: feature
mode: infra
source: >
  MISSION.md § Rationale ("ASF integrations live behind clean
  configuration boundaries; non-ASF adopters swap them") and § Technical
  scope (extensible adapter layer). Implemented in tools/gmail/,
  tools/ponymail/, tools/jira/, tools/github/, tools/mail-source/.
acceptance:
  - Project-specific integrations live behind adapter modules, not
    hardcoded into skills.
  - A non-ASF adopter can swap an adapter (e.g. private GitHub repo for
    private mailing list) with config substitution, not skill edits.
  - Mail-reading adapters route fetched content through the privacy
    redactor before any LLM read.
---

# Adapters (Gmail / PonyMail / Jira / GitHub)

## What it does

Isolates the systems a project already uses behind adapter modules so the
skills stay project-agnostic. The same skill executes against an ASF
project's private mailing list or a non-ASF project's private GitHub repo
by swapping the adapter, not the skill.

## Where it lives

- `tools/gmail/` — private-mail read/draft (drafts to the outbox; never
  sends).
- `tools/ponymail/` — public mailing-list archive search.
- `tools/jira/` — issue-tracker adapter for projects on Jira.
- `tools/github/` — issues/PRs/labels read + write-back helpers.
- `tools/mail-source/` — abstract mail backend contract (operations,
  capability matrix, adopter-declaration syntax) with concrete IMAP and
  mbox implementations. Skills (`security-issue-import`,
  `security-issue-sync`, `security-cve-allocate`) address every mail
  source through this contract rather than calling Gmail or PonyMail
  directly; the adopter's `<project-config>/project.md → Mail sources`
  section declares which backends are active and what role each plays.

## Behaviour & contract

- **Pluggable, config-driven.** Skills reference placeholders
  (`<tracker>`, `<upstream>`, `<security-list>`, …); the adapter resolves
  them from `<project-config>/`. No `apache/<project>` strings hardcoded
  into a skill.
- **Mail adapters draft, never send** — outbound goes to the maintainer's
  drafts folder; the human presses Send.
- **Mail adapters redact-after-fetch** — fetched private content passes
  through the privacy redactor
  ([privacy-llm-gate.md](privacy-llm-gate.md)) before any LLM read.
- **Write-back is confirm-before-apply** and routed through the sandbox's
  `ask` gate ([agent-isolation-sandbox.md](agent-isolation-sandbox.md)).
- **Adapter READMEs are contracts.** Every adapter README declares the
  capability it provides, prerequisites, credential/privacy handling,
  supported operations, and adopter config keys. These fields let a
  validator distinguish an intentional adapter surface from undocumented
  shell prose.
- **Private mail is hostile input.** Gmail, PonyMail, `mail-archive`, and
  `mail-source` content is external data, never instructions. Tests for
  mail adapters should include prompt-injection text in fetched mail and
  prove it is carried as report data only after redaction/gating.

## Out of scope

- The privacy *policy* and gate (separate area, referenced above).
- Sending outbound mail (a human action).

## Acceptance criteria

1. No skill hardcodes a project-specific repo/list; all go through an
   adapter + placeholder.
2. Mail adapters draft only and redact before LLM read.
3. Each adapter ships with its own tests.
4. Adapter READMEs declare capability, prerequisites,
   privacy/credential handling, operations, and config keys.
5. Mail-adapter tests prove private fetched content crosses the
   Privacy-LLM/redaction boundary before model-facing skill context.

## Validation

```bash
for t in gmail ponymail jira github; do
  uv run --project tools/$t --group dev pytest || echo "check tools/$t test setup"
done
```

## Known gaps

- `experimental` overall — adapter coverage varies; a new adopter system
  (e.g. GitLab, a different mail backend) is a gap the plan pass records.
- Adapters cover the *system-swap* case; the broader audit of residual
  ASF coupling across the catalogue, and the capability-flag mechanism for
  workflow branches that no adapter resolves, live in
  [project-agnosticism.md](project-agnosticism.md).
- **Adapter authoring smoke validation is missing.** The docs define the
  expected README contract, but no validator currently checks that each
  adapter declares capability, prerequisites, privacy/credential handling,
  operations, and config keys.
- **Mail-adapter privacy tests are thin.** The redaction contract exists,
  but adapter-level fixtures should prove that private mail and embedded
  prompt-injection attempts do not enter model-facing context untreated.
