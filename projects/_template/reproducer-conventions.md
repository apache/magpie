<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — reproducer evidence-package layout](#todo-project-name--reproducer-evidence-package-layout)
  - [Campaign directory layout](#campaign-directory-layout)
  - [Optional probe files](#optional-probe-files)
  - [Why frozen copies](#why-frozen-copies)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — reproducer evidence-package layout

Directory layout used by [`issue-reproducer`](../../skills/issue-reproducer/SKILL.md)
when writing per-issue evidence packages, and consumed by
[`issue-reassess-stats`](../../skills/issue-reassess-stats/SKILL.md)
for campaign-level aggregation.

## Campaign directory layout

```text
~/work/<project>-reassess/<campaign-id>/<ISSUE-KEY>/
├── description.md      (frozen copy of the issue body at extraction time)
├── issue.json          (frozen JSON snapshot from the tracker)
├── original.<ext>      (verbatim code from the issue, untouched)
├── reproducer.<ext>    (the adapted runnable form)
├── run.log             (captured stdout + stderr from execution)
└── verdict.json        (the structured verdict)
```

Substitute:

- `<project>` — the project's short name (typically the
  `short_name` field from [`project.md`](project.md)).
- `<campaign-id>` — the campaign identifier
  (e.g., `pilot-2026-05-13`).
- `<ISSUE-KEY>` — the tracker's issue key
  (e.g., `<KEY>-9999`).
- `<ext>` — the file extension matching the project's runtime
  (e.g., `.py` for Python, `.foo` for a fictional Foo language).

## Optional probe files

When a [cross-family probe](../../skills/issue-reproducer/probe-templates.md)
was run alongside the reproducer, also persist:

```text
├── cross-type-probe.<ext>           (the probe script across type variants)
├── cross-type-probe.log             (captured output)
├── operator-variants-probe.<ext>    (across operator variants)
└── operator-variants-probe.log
```

A separate `cross-type-probe-findings.md` is added when the probe
surfaces project-wide signal worth recording outside `verdict.json`.

## Why frozen copies

`description.md` and `issue.json` are deliberately **frozen** at
extraction time. The tracker may change (comments added, fields
edited, status changed) between extraction and re-verification.
Frozen copies make the verdict auditable against the same input
state the agent reviewed.

The same logic applies when re-running a campaign against a newer
codebase — comparing fresh runs against frozen description gives a
clean before/after, where comparing against live tracker state
introduces moving targets.

## Cross-references

- [`runtime-invocation.md`](runtime-invocation.md) — how the
  reproducer is executed.
- [`reassess-pool-defaults.md`](reassess-pool-defaults.md) — named
  pools that surface candidates for evidence packages.
- [`issue-reproducer/verdict-composition.md`](../../skills/issue-reproducer/verdict-composition.md) —
  the `verdict.json` schema.
