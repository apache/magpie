<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [security-tracker-stats.md (template)](#security-tracker-statsmd-template)
  - [YAML config path](#yaml-config-path)
  - [Default output path](#default-output-path)
  - [Cache directory](#cache-directory)
  - [Refresh cadence](#refresh-cadence)
  - [Rejected-without-tracker ledger](#rejected-without-tracker-ledger)
  - [Example overlay (`security-tracker-stats.yaml`)](#example-overlay-security-tracker-statsyaml)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-tracker-stats.md (template)

Per-project configuration consumed by the
[`security-tracker-stats-dashboard`](../../skills/security-tracker-stats-dashboard/SKILL.md)
skill. Copy this file into your project's `<project-config>/`
directory and edit the values below. Everything is optional — the
skill falls back to
[`tools/security-tracker-stats-dashboard/default-config.yaml`](../../tools/security-tracker-stats-dashboard/default-config.yaml)
when a key is unset.

## YAML config path

```yaml
tracker_stats_config: .apache-magpie-overrides/security-tracker-stats.yaml
```

The renderer reads its configuration from the YAML file pointed at by
the `TRACKER_STATS_CONFIG` env var. The skill resolves this from
`tracker_stats_config:` above (interpreting it relative to the
adopter repo root). Adopters who want the framework's defaults
verbatim can leave this unset; the skill will skip the overlay step.

The YAML schema is documented inline at
[`tools/security-tracker-stats-dashboard/default-config.yaml`](../../tools/security-tracker-stats-dashboard/default-config.yaml).

## Default output path

```yaml
tracker_stats_output: tmp/tracker_stats.html
```

The skill writes the rendered HTML to this path (relative to the
adopter repo root, or absolute) when the user does not pass an
explicit `<output-path>` argument. The
`airflow-s/airflow-s` adopter uses `tmp/airflow_s_monthly.html`
(committed into `tmp/` as the canonical artefact for security-team
review).

## Cache directory

```yaml
tracker_stats_cache: /tmp/tracker-stats-cache
```

Where the fetch scripts persist their cache. Safe to delete (forces a
full re-fetch). The skill resolves this to the `TRACKER_STATS_CACHE`
env var.

## Refresh cadence

```yaml
tracker_stats_refresh_hours: 24
```

The skill considers the cache stale when `issues.json` is older than
this many hours, and proposes a refresh before re-rendering. Lower
this for fast-moving trackers; raise it for trackers where the
dashboard is reviewed weekly or monthly.

## Rejected-without-tracker ledger

```yaml
rejections_ledger_label: rejections-ledger
```

Lives in the renderer's YAML overlay (the file pointed at by
`tracker_stats_config:` above), not in `project.md`. Names the label
on the single open **ledger issue** that records reports the
`security-issue-import` skill rejected with a canned reply **without
creating a tracker** — see the *Rejected-without-tracker ledger* note
in [`project.md`](project.md) for the convention. The renderer
identifies any issue carrying this label as the ledger, excludes it
from all tracker classification, and parses its comments for the
`<!-- rejection v1 -->` / `<!-- rejection-backfill v1 count: N -->`
markers to produce a *rejected (no tracker)* count (a per-bucket area
series plus a `<dated> + <historical> = <total>` headline).

Set to `null` to disable the stat entirely (no ledger issue needed).
The ASF/Airflow default is `rejections-ledger`, matching
`tracker.labels.rejections_ledger` in `project.md`. To turn the stat
on, create the open ledger issue, label it, and keep this knob
pointed at the same label.

## Example overlay (`security-tracker-stats.yaml`)

A minimal overlay that swaps to quarterly buckets and adds a
project-specific milestone:

```yaml
buckets: quarterly

rejections_ledger_label: rejections-ledger

milestones:
  - date: 2026-04-20
    label: skill adoption
  - date: 2026-09-01
    label: handover to PMC sec team
```

A bigger overlay that renames the scope labels for a non-Airflow
adopter and removes the upstream-PR charts entirely (because fixes
land in many repos, not a single `<upstream>`):

```yaml
upstream_repo: null

scope_labels: [core, plugins, docs]

milestones: []

# Re-state the full categories list to align with the project's
# label conventions. The framework's default categories assume
# `needs triage`, `pr merged`, `fix released`, `announced - emails
# sent`, `cve allocated` — projects with different label vocabularies
# need to re-state predicates explicitly.
categories:
  - name: fixed_released
    color: "#2ca02c"
    predicate:
      any_of:
        - any_label: [released]
        - all_of:
            state: closed
            state_reason: COMPLETED
            any_label: [security-fix]
  - name: closed_other
    color: "#888888"
    predicate:
      state: closed
  - name: open_untriaged
    color: "#d62728"
    predicate:
      all_of:
        state: open
        any_of:
          - any_label: [needs triage]
          - no_scope_label: true
  - name: open_pr_merged
    color: "#e67e22"
    predicate:
      all_of:
        state: open
        any_label: [pr merged]
  - name: open_triaged
    color: "#f1c40f"
    predicate:
      state: open
```
