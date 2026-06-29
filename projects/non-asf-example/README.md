<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Velox Stream — non-ASF adopter profile fixture](#velox-stream--non-asf-adopter-profile-fixture)
  - [What differs from an ASF profile](#what-differs-from-an-asf-profile)
  - [Files](#files)
  - [Smoke eval](#smoke-eval)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Velox Stream — non-ASF adopter profile fixture

This directory is a **worked example** of a non-ASF adopter profile. It
does **not** represent a real project. Its purpose is to demonstrate
and test acceptance criterion 3 of
[`docs/specs/project-agnosticism.md`](../../tools/spec-loop/specs/project-agnosticism.md):

> A non-ASF profile can be declared without editing any skill body.

The fictional project — **Velox Stream** — is a community-governed
stream-processing library hosted entirely on GitHub, using DCO
contributor sign-off, GitHub Security Advisories for security intake,
direct MITRE CVE allocation, and GitHub Releases for distribution. None
of these choices require editing any skill body; each maps to a
configuration flag or placeholder declared below.

## What differs from an ASF profile

This fixture sets `organization: independent` and inherits the
[`organizations/independent/`](../../organizations/independent/) baseline,
where an ASF project sets `organization: ASF` and inherits
[`organizations/ASF/`](../../organizations/ASF/). The two organizations
carry the differences below — the *skills* are identical:

| Dimension | ASF default | This fixture (non-ASF) |
|---|---|---|
| Governance | PMC membership, ICLA | DCO sign-off, no formal governance body |
| CVE authority | ASF Vulnogram | MITRE direct (`mitre-form`) |
| Security intake | `security@<project>.apache.org` email | GitHub Security Advisories (GHSA) |
| Mail archive | PonyMail (`lists.apache.org`) | None (no mailing lists) |
| Distribution | `dist.apache.org` / `closer.lua` | GitHub Releases |
| Announcement | `announce@apache.org` list | GitHub Releases + Discussions |
| Project metadata | `apache-projects-mcp` | `none` (maintainer-supplied roster) |
| Committer intake | ICLA gate + ASF member vote | DCO + maintainer team decision |

## Files

- [`project.md`](project.md) — core identity, repositories, security workflow config
- [`issue-tracker-config.md`](issue-tracker-config.md) — GitHub Issues on the
  upstream repo
- [`stale-sweep-config.md`](stale-sweep-config.md) — stale-sweep thresholds

## Smoke eval

`tools/skill-evals/evals/non-asf-profile-smoke/` drives the
`issue-stale-sweep` skill through this profile and asserts that:

1. Pre-flight (step 1) passes with no Apache-specific fields present.
2. Issue classification (step 3) produces correct output for a non-ASF
   project without requiring any Apache labels or governance signals.
3. The skill body was not edited — only the config files differ.
