<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Product overview

Apache Magpie is a **project-agnostic
framework for agent-assisted repository maintainership and development**.
It is not an application with a `src/` tree — it is a substrate plus a
catalogue of agent-readable **skills** (Markdown + YAML) and deterministic
**tools** (`uv`/Python). The specs in this directory describe that
functionality so the build loop can keep the code in sync with the
intended behaviour.

These specs are **unordered** — the filename is a topic, not a priority.
What to build next comes from [`../IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md),
not from any numbering.

## Substrate

Issue/PR ingestion, GitHub write-back, mail threading, audit logging, and
pluggable adapters for the systems a project already uses (Gmail,
PonyMail, Jira, GitHub, Vulnogram). Per-project configuration declares
which modes are on, eligible change classes, reviewers, and where reports
come from.

## The modes (MISSION taxonomy)

Each mode is an independently toggleable set of skills. Maturity mirrors
[`docs/modes.md`](../../../docs/modes.md):

| Mode | Spec | Maturity |
|---|---|---|
| Triage | [triage-mode.md](triage-mode.md) | stable (security) / experimental (PR, issue, contributor-nomination) |
| Mentoring | [mentoring-mode.md](mentoring-mode.md) | experimental (1 skill) |
| Drafting | [drafting-mode.md](drafting-mode.md) | stable (security) / experimental (issue) |
| Pairing | [pairing-mode.md](pairing-mode.md) | experimental (1 skill) |

> **Auto-merge** is the fifth MISSION mode but is deliberately **off** by
> sequencing policy (`.asf.yaml` `allow_auto_merge: false`) — it has no
> implementation and nothing to build, so it is documented as a boundary
> in [`docs/modes.md`](../../../docs/modes.md), not as a spec here.

## Cross-cutting functionality

| Area | Spec |
|---|---|
| Security-issue lifecycle (the load-bearing use case) | [security-issue-lifecycle.md](security-issue-lifecycle.md) |
| Privacy-LLM gate + PII redaction | [privacy-llm-gate.md](privacy-llm-gate.md) |
| Agent isolation / layered sandbox | [agent-isolation-sandbox.md](agent-isolation-sandbox.md) |
| CVE tooling | [cve-tooling.md](cve-tooling.md) |
| Security reporting & dashboards | [security-reporting.md](security-reporting.md) |
| Adoption & setup | [adoption-and-setup.md](adoption-and-setup.md) |
| Adapters (Gmail / PonyMail / Jira / GitHub / mail-source) | [adapters.md](adapters.md) |
| Meta & quality tooling | [meta-and-quality-tooling.md](meta-and-quality-tooling.md) |

## The non-negotiables every area inherits

- **Human-in-the-loop on every state change.** Outputs are proposals;
  the human confirms. (`docs/rfcs/` holds the normative statement; this
  spec system respects it as a constraint and never edits it.)
- **Drafts, never sends; the human presses the button** — no skill calls
  `git push` / `gh pr create` on autopilot.
- **Secure sandbox by default**, vendor neutrality, privacy by design.

## How these specs are built

The build loop (see [`../README.md`](../README.md)) compares each spec
against the code and turns the gaps into work items in the plan — one
work item, one branch, one PR.
