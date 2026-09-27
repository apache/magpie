<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — scope labels](#todo-project-name--scope-labels)
  - [Scope to CVE product / package-name table](#scope-to-cve-product--package-name-table)
  - [Default `packageName` and vendor](#default-packagename-and-vendor)
  - [Closing dispositions (not scope labels)](#closing-dispositions-not-scope-labels)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — scope labels

Every tracker gets **exactly one** scope label at Step 5 of the
handling process (valid/invalid consensus landed). The scope:

- pins the tracker to one product the CVE will be allocated against;
- drives the release train the fix backports to (see
  [`release-trains.md`](release-trains.md));
- determines the milestone format (see
  [`milestones.md`](milestones.md));
- maps to the `product` / `packageName` of the CVE record (see the
  table below).

TODO: list the project's scope labels, one row per label. If a report
affects more than one scope, the `security-issue-sync` skill surfaces
this as a blocker and the triager splits the report into per-scope
trackers.

## Scope to CVE product / package-name table

| Tracker scope label | CVE product | CVE container `packageName` | Collection URL |
|---|---|---|---|
| TODO: e.g. `foo` | TODO: e.g. `Apache Foo` | TODO: e.g. `apache-foo` | TODO: e.g. `https://pypi.python.org` |

## Default `packageName` and vendor

- `vendor`: TODO — usually from the `project.md → Identity` block.
- Default `packageName` for untagged / uncertain reports: TODO.

These defaults are declared in [`project.md`](project.md) under
*Identity* and *CVE tooling*; the CVE-JSON generator reads them from
there.

## Closing dispositions (not scope labels)

`invalid`, `not CVE worthy`, `duplicate`, and `wontfix` are **closing
dispositions**, not scope labels. They are set at Step 5 or Step 6
of the process when the tracker leaves the flow without a CVE. They
do not imply a product and never end up in the CVE-tool product
field. These are part of the generic lifecycle — see
[`../../tools/github/labels.md`](../../../tools/github/labels.md).
