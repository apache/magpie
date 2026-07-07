<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Velox Stream — stale-sweep configuration (non-ASF fixture)](#velox-stream--stale-sweep-configuration-non-asf-fixture)
  - [Thresholds](#thresholds)
  - [Exclusion labels](#exclusion-labels)
  - [Component / area filter defaults](#component--area-filter-defaults)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Velox Stream — stale-sweep configuration (non-ASF fixture)

Per-project thresholds for the
[`issue-stale-sweep`](../../skills/issue-stale-sweep/SKILL.md) skill,
used as a non-ASF adopter fixture. See [`README.md`](README.md) for
context.

## Thresholds

Velox Stream is a smaller project with a faster activity cadence, so the
thresholds are tighter than the framework defaults.

| Field | Value | Rationale |
|---|---|---|
| `warn_days` | 60 | Post a nudge after 60 days of inactivity |
| `close_days` | 120 | Propose close after 120 days post-nudge |
| `hard_close_days` | 240 | Unconditional close after 240 days |

```yaml
warn_days: 60
close_days: 120
hard_close_days: 240
```

## Exclusion labels

```yaml
exclude_labels:
  - blocked
  - confirmed-bug
  - awaiting-upstream
  - pinned
```

## Component / area filter defaults

```yaml
default_component_filter: []
```

## Cross-references

- [`issue-tracker-config.md`](issue-tracker-config.md) — tracker URL
  and auth.
- [`issue-stale-sweep`](../../skills/issue-stale-sweep/SKILL.md) — the
  skill that reads this configuration.
