<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Changelog](#changelog)
  - [0.1.0](#010)
    - [Framework](#framework)
    - [Skill families](#skill-families)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Changelog

All notable changes to Apache Magpie are recorded here. This project
adheres to [Semantic Versioning](https://semver.org/).

## 0.1.0

First Apache Magpie release. Apache Magpie is a reusable, governance-
agnostic framework of agentic skills for maintaining open-source
projects — usable by ASF and non-ASF projects alike.

This initial release establishes the framework and its skill families:

### Framework

- Snapshot-based **adoption mechanism** (`magpie-setup`) so a project
  can adopt, upgrade, verify, and unadopt the framework from a pinned
  snapshot, with per-adopter and per-user configuration layers.
- **Agentic mode taxonomy** (Triage, Mentoring, Drafting, Pairing) and
  the state-change-boundary discipline every skill is held to
  (human-in-the-loop on every state change; the agent drafts, the human
  acts).
- **Trusted skill sources** — fetch, pin, and symlink skills from
  external trust-listed sources.

### Skill families

- **Security** — the security-issue lifecycle from intake through
  triage, CVE allocation, fix, and disclosure.
- **Release management** — the release lifecycle: planning, RC cut,
  verification, vote, promote, announce, archive, and audit, with both
  the `svnpubsub` and **Apache Trusted Releases (ATR)** distribution
  backends documented.
- **PR management** — triage, code review, quick-merge, and stats for a
  maintainer's pull-request queue.
- **Issue management** — triage, deduplication, reproduction, staleness
  sweeps, and backlog statistics.
- **Contributor & committer** — nomination briefs, activity sweeps,
  readiness tracking, and post-vote onboarding.
- **Audit** — CI-runner, dependency, license-compliance, and
  flaky-test audits.

See [`README.md`](README.md) and [`MISSION.md`](MISSION.md) for the
full scope, and [`docs/`](docs/) for the per-family documentation.
