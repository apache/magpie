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

- `tools/privacy-llm/checker/` — the approved-LLM gate
  (`privacy-llm-check`; `--config` to name the config file,
  `--reads-private-list` so the banner says a PMC-private list is in
  play, `--quiet` to print nothing on approval).
  The `checker` package also exports `check_endpoint(endpoint)`, the
  runtime counterpart for a tool that makes its own outbound LLM call
  (first consumer: [`tools/typed-decision/`](adapters.md), #1402).
  It rejects a non-HTTP(S) URL, a fragment, or userinfo; approves
  `localhost` and `*.apache.org` minus the carve-outs; and otherwise
  requires an opt-in entry in `privacy-llm.md` whose host matches exactly
  (or, for a name-only entry, the provider's default endpoint plus a
  whole-word name match) with a data-residency contract and a
  non-placeholder `Approved-by`.
  The free-text Claude Code rule of the stack check does not apply to it.
- `tools/privacy-llm/models.md` — the approved-model registry and its
  carve-outs.
- `tools/privacy-llm/redactor/` — the PII redactor (name→`N-<hash>`,
  email→`E-<hash>`, IP→`IP-<hash>`).
- `tools/privacy-llm/wiring.md` — the redact-after-fetch protocol every
  Gmail/PonyMail-reading skill follows.
- `tools/privacy-llm/pii.md` — the PII pattern catalogue.
- `docs/setup/privacy-llm.md` — adopter-facing setup.
- Adopter config: `<project-config>/privacy-llm.md`, scaffolded from
  `plugins/magpie-setup/templates/privacy-llm.md` (moved from
  `projects/_template/` in #1410). Without `--config` or
  `$PRIVACY_LLM_CONFIG`, the checker looks it up per config layer, first
  match wins: the personal layer (`<cwd>/.apache-magpie-local/` in an
  adopted repository, `<git-common-dir>/apache-magpie/` otherwise), then a
  legacy in-tree `.apache-magpie-local/` of an unadopted repository, then
  the committed `.apache-magpie-overrides/`. The `.apache-magpie/`
  framework snapshot is never looked in: it is replaced by every upgrade
  and holds no adopter config, and the earlier snapshot-then-overrides
  order never read the personal file `setup-privacy-llm` writes. A file
  found nowhere stops the gate.
- Skill: `setup-privacy-llm` (`plugins/magpie-setup/skills/privacy-llm/`)
  detects the LLM stack in use, writes `<project-config>/privacy-llm.md`,
  and runs the gate and the redactor end to end so the approval is
  demonstrated rather than declared.
- Consumers: the gate runs as a hard stop in the pre-flight of the
  security lifecycle skills that read private mail or tracker content
  (`security-issue-import`, `-import-from-md`, `-triage`, `-deduplicate`,
  `-sync`, `-fix`, `-invalidate`, `security-cve-allocate`), and outside
  the security family in `reviewer-routing`, `contributor-calibrate` and
  `committer-onboarding` (the last with `--reads-private-list`).

## Behaviour & contract

- **Policy is the PMC's; the gate is the framework's.** The approved-LLM
  list is per-PMC. The default: agent host trusted, `*.apache.org`
  auto-approved, `localhost` for local inference, everything else opt-in.
- **The `*.apache.org` default is rebuttable.** It assumes the endpoint
  runs on infra under ASF governance. An apache.org host that does not
  meet that assumption is carved out by exact host and rejected before
  the domain rule applies — `llm.apache.org` (LLMAO) is the first, since
  it serves from rented third-party GPU hardware and its pilot traffic is
  visible to gateway admins. The carve-out binds the private-data gate
  only; public-content skills may use such an endpoint freely.
- **Tool-initiated LLM calls are gated per endpoint, before any bytes
  leave.** A tool that calls a model itself checks the destination with
  `check_endpoint` before assembling the request; a denial means no network
  request is made.
  This gate is the egress boundary only: redaction of private source
  content stays the calling skill's job, per `wiring.md`.
- **Public-bound reviewer CLIs are outside the gate by design.** The
  `adversarial-review` reviewers (`codex`, `copilot`, `gemini`, `grok`,
  `claude`) receive only the diff and the public PR text, so `models.md`
  excludes them from the active stack
  ([adversarial review](adversarial-review.md)).
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
- **Branch-name confidentiality validation is shipped** as a SOFT
  advisory in `tools/skill-and-tool-validator`
  (`validate_branch_name_confidentiality`, category
  `branch-name-confidentiality`). It scans `git checkout -b` and
  `git switch -c` / `--create` examples in fenced code blocks under
  `skills/` and `docs/`, and flags concrete branch names that contain a
  CVE ID (`CVE-YYYY-NNNNN`), `security`, `vulnerability` / `vuln`, or
  `advisory`. Placeholder names and explicit bad-example lines are
  exempt. Advisory only unless `--strict`.
