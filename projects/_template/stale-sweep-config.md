<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — stale-sweep configuration](#todo-project-name--stale-sweep-configuration)
  - [Thresholds](#thresholds)
  - [Exclusion labels](#exclusion-labels)
  - [Component / area filter defaults](#component--area-filter-defaults)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — stale-sweep configuration

Per-project thresholds and defaults for the
[`issue-stale-sweep`](../../skills/issue-stale-sweep/SKILL.md) skill.
If this file is absent, the skill falls back to framework defaults
(90 / 180 / 365 days). Copy this file into your `<project-config>/`
directory and fill in the TODO values.

## Thresholds

| Field | Default | Description |
|---|---|---|
| `warn_days` | 90 | Days of inactivity before posting a `REQUEST-UPDATE` nudge |
| `close_days` | 180 | Days of inactivity (after a prior nudge with no response) before proposing `CLOSE-STALE` |
| `hard_close_days` | 365 | Days of inactivity that trigger `CLOSE-STALE` unconditionally, without requiring a prior nudge |

```yaml
warn_days: 90       # TODO: adjust for your project's activity cadence
close_days: 180     # TODO: must be > warn_days
hard_close_days: 365  # TODO: must be > close_days
```

## Exclusion labels

Issues carrying any of the following labels are excluded from stale
sweeps entirely, regardless of inactivity age. Add any project-specific
labels that should be exempt (e.g., labels for confirmed bugs awaiting
a fix, long-running feature discussions, or blockers on upstream
dependencies).

```yaml
exclude_labels:
  - blocked
  - confirmed-bug
  - awaiting-upstream
  # TODO: add project-specific exempt labels
```

## Component / area filter defaults

If the project wants stale sweeps to default to a subset of components,
set them here. An empty list means all open issues are eligible.

```yaml
default_component_filter: []   # TODO: e.g. ["scheduler", "api"] or leave empty
```

## Cross-references

- [`issue-tracker-config.md`](issue-tracker-config.md) — tracker URL,
  project key, auth model, close-status mapping.
- [`issue-stale-sweep`](../../skills/issue-stale-sweep/SKILL.md) — the
  skill that reads this configuration.
