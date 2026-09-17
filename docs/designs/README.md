<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Designs](#designs)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Designs

Design documents for changes that are in flight or recently landed. Each one
records what was decided and, more usefully, what was rejected and why — the
alternatives section is the part that saves the next person the argument.

A design here is not a promise that the work shipped as described. Each
carries a status line; read that first, and take seriously any section naming
what was designed and deliberately not built.

| Design | Status |
|---|---|
| [Install, adopt, upgrade](2026-09-13-install-adopt-upgrade.md) | Built, bar two items it names |
| [Body-owned configuration layers](2026-09-17-body-owned-config-layers.md) | Proposed — depends on the Incubator PMC and ComDev |

One document per subject, describing the result rather than the phases it was
built in. While a design is being implemented it may be split into plans; when
the work lands, the plans are folded back in and deleted. A reader arriving
later wants the decision and the rejected alternative, not the task list that
got there — and git keeps the task list.

These sit outside [`tools/spec-loop/specs/`](../../tools/spec-loop/specs/),
which is the durable record of what the framework guarantees. A design argues
for a change; a spec states what the shipped system does. When the two
disagree, the spec is right.
