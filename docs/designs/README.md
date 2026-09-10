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
carries a status line; read that first.

| Design | Status |
|---|---|
| [Repo-committed setup: default plugin set and per-skill first-run configuration](2026-09-10-repo-committed-setup-design.md) | Subsystem A implemented; B and C not started |
| [Subsystem A implementation plan](2026-09-10-repo-committed-setup-plan-a.md) | Complete |

These sit outside [`tools/spec-loop/specs/`](../../tools/spec-loop/specs/),
which is the durable record of what the framework guarantees. A design argues
for a change; a spec states what the shipped system does. When the two
disagree, the spec is right.
