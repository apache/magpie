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
- Skill: `security-tracker-stats-dashboard`
  (`plugins/magpie-security/skills/tracker-stats-dashboard/SKILL.md`,
  behind the `skills/security-tracker-stats-dashboard` symlink) — invokes
  the tool, surfaces the output path, and handles staleness detection
  (~24 h default). Reads only; never posts to the tracker.
- Adopter config: `<project-config>/security-tracker-stats.md`, scaffolded
  from `plugins/magpie-setup/templates/security-tracker-stats.md` (#1410);
  the skill declares it, with `project.md` and `scope-labels.md`, in
  `requires_config:`.

## Behaviour & contract

- **Read-only.** Neither the tool nor the skill writes to any tracker
  issue, label, milestone, or project board field.
- **Self-contained output.** The rendered HTML embeds all data; no
  external service is needed to view it.
- **Incremental by default.** Resume behaviour extends an existing dataset
  without re-fetching all history; a full rebuild is an opt-in flag. The
  per-issue event cache is trusted only when it was written after that
  issue's `updatedAt`; an issue relabelled since the cache was written is
  refetched rather than silently served its stale label history.
  The skill's freshness check and the fetch use the same cache directory:
  the configured `tracker_stats_cache` value, else `$TRACKER_STATS_CACHE`,
  else the fetch scripts' default; before #1444 the skill ignored the
  configured value, so it could judge freshness from a directory the
  fetch never wrote.
- **One list call, not one read per issue (#1443).**
  `fetch_issues.py` requests `body` and `closedByPullRequestsReferences`
  in its `gh issue list --state all --limit 1000` call, and
  `fetch_bodies.py` copies them from `issues.json` into
  `issue_extra.json`; a per-issue `gh issue view` runs only as a fallback
  for an issue whose list entry lacks the fields, such as an
  `issues.json` written before the change.
  When the list returns 1000 issues, `fetch_issues.py` warns that it hit
  the cap, that older issues are missing, and that every count in the
  dashboard is a floor.
- **Config-driven.** Lifecycle category bands, time-to-triage signal,
  milestone vertical annotations, and the null-`upstream_repo` path are
  declared in the tool's `default-config.yaml` and overridden per-adopter.
- **The current bucket is projected to its end-of-bucket value.** A partially
  elapsed month, quarter, or week is otherwise read as a genuine decline when
  it is only incomplete. The projection is linear on the elapsed fraction and
  splits by series kind: RATE series (counts accumulating from zero inside the
  bucket — reports opened, reports rejected) project `observed / fraction` and
  never below the observed count; LEVEL series (cumulative totals and
  end-of-bucket snapshots, which carry over) extrapolate only the movement
  within the bucket, `previous + (observed - previous) / fraction`, floored at
  zero. Mean-based signals are deliberately not projected — a mean over the
  items seen so far is already an estimate, not a partial accumulation. The
  output states the elapsed fraction and the observed-to-projected pair, and
  names the reason whenever projection is skipped (disabled, bucket already
  complete, or no baseline bucket to project from).

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
