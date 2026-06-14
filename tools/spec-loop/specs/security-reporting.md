<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Security reporting & dashboards
status: experimental
kind: feature
mode: infra
source: >
  README.md § Skill families (security) and AGENTS.md § Reusable skills.
  Implemented by tools/security-tracker-stats-dashboard/ and the
  security-tracker-stats-dashboard skill.
acceptance:
  - A single command produces a self-contained HTML dashboard of tracker
    statistics without modifying any tracker state.
  - The dashboard is read-only; no tracker labels, milestones, or issue
    bodies are written.
  - The tool ships its own tests.
---

# Security reporting & dashboards

## What it does

Generates read-only aggregate views of the security tracker's issue
backlog — lifecycle-band breakdowns, time-to-triage trends, per-scope
pressure, and velocity charts — so the security team can review campaign
health without navigating the tracker issue-by-issue.

## Where it lives

- `tools/security-tracker-stats-dashboard/` — Python tool that fetches
  issue and event data from `<tracker>` (via `gh`) and renders a
  self-contained HTML file. Supports incremental resume (re-runs extend
  the existing data rather than re-fetching everything), configurable
  lifecycle categories, milestone annotations, and a null-`upstream_repo`
  path for trackers whose fixes land across multiple repos.
- Skill: `security-tracker-stats-dashboard` — invokes the tool, surfaces
  the output path, and handles staleness detection (~24 h default). Reads
  only; never posts to the tracker.

## Behaviour & contract

- **Read-only.** Neither the tool nor the skill writes to any tracker
  issue, label, milestone, or project board field.
- **Self-contained output.** The rendered HTML embeds all data; no
  external service is needed to view it.
- **Incremental by default.** Resume behaviour extends an existing dataset
  without re-fetching all history; a full rebuild is an opt-in flag.
- **Config-driven.** Lifecycle category bands, time-to-triage signal,
  milestone vertical annotations, and the null-`upstream_repo` path are
  declared in the tool's `default-config.yaml` and overridden per-adopter.

## Out of scope

- Writing back any artefact to the tracker (that is the lifecycle skills).
- Publishing the dashboard publicly — output is a local file; distribution
  is the security team's choice.

## Acceptance criteria

1. `render.py` / `run.sh` produces a valid HTML file from `<tracker>` data.
2. No tracker state is mutated (read-only `gh` calls only).
3. The tool ships its own tests under `tools/security-tracker-stats-dashboard/`.

## Validation

```bash
uv run --directory tools/security-tracker-stats-dashboard --group dev pytest
bash -n tools/security-tracker-stats-dashboard/run.sh
shellcheck tools/security-tracker-stats-dashboard/run.sh
```

## Known gaps

- `experimental` — no adopter pilot has run the dashboard end-to-end.
- CI integration is a follow-on item.
