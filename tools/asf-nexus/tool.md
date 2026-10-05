<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Tool: ASF Nexus staging repository](#tool-asf-nexus-staging-repository)
  - [What this tool provides](#what-this-tool-provides)
  - [Read-only, by construction](#read-only-by-construction)
  - [The two read paths](#the-two-read-paths)
  - [When to use this tool alongside another](#when-to-use-this-tool-alongside-another)
  - [Centralized-model note](#centralized-model-note)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tool: ASF Nexus staging repository

## What this tool provides

| Capability | File | What it covers |
|---|---|---|
| Staging-repository probe | [`operations.md`](operations.md) | The `repository.apache.org` endpoint contract: which read paths are anonymous and which need credentials, the exact `curl` recipes, and the JSON shapes returned — verified against the live service in October 2026 |
| Staging-repository classification | [`staging-verification.md`](staging-verification.md) | How to judge a probe result: `closed` vs `open` vs unreachable, coordinates/version match against the RC, `.asc` and checksum coverage, complete companion set, the snapshots-repository exclusion, and the multiple-repositories case |

The consuming skill is `release-verify-rc` (Step 6c, JVM artefact
surface): it emits the paste-ready probe recipe and classifies the
result per [`staging-verification.md`](staging-verification.md). The
recipes and classification live here, not in the skill body — the
skill enforces *whether* the step runs; this adapter documents *what*
the commands are.

## Read-only, by construction

Every recipe in this adapter is a `GET`. The adapter has **no**
close, drop, promote, or upload recipe — not a disabled one, none at
all. Three reasons, in decreasing order of weight:

1. **Any voter may run `release-verify-rc`**, including someone with
   no karma on the target repository — the probe must work with
   credentials the voter does not have.
2. A staging-repository **promotion is irreversible**: once promoted,
   the artefacts sync to Maven Central, where they are immutable and
   can never be withdrawn. That is strictly less recoverable than the
   `dist/release/` move that already justifies the denylist and PMC
   gate in `release-promote`. If a future PR adds a Nexus close /
   drop / promote surface, it needs that equivalent golden rule first
   — it does not belong here.
3. The framework guarantees zero outbound calls unless a skill's
   adapter action explicitly makes them. Step 6c declares exactly one
   read surface — `repository.apache.org`, `GET` only — and nothing
   else.

## The two read paths

The live service splits its reads along exactly the line that matters
for this adapter (verified against `repository.apache.org` in October
2026 — see [`operations.md`](operations.md) for the probes):

| Path | Auth | What it answers |
|---|---|---|
| `https://repository.apache.org/content/repositories/<id>/` | anonymous | The artefact tree of a staging repository — existence, inventory, `.asc` / checksum coverage. Answers everything except the authoritative `state` field. |
| `https://repository.apache.org/service/local/staging/...` | ASF Nexus credentials | The staging REST API — the authoritative `state` (`open` / `closed`) and the profile-wide listing that surfaces *every* staging repository for the project (the stale-earlier-RC footgun). |

A voter without credentials gets the first path and reports
`STATE-UNVERIFIED` for the state question; the RM (who has
credentials and is the person whose close operation the state check
verifies) gets both. Neither path alone is allowed to fail a correct
RC: an unreachable API is `STATE-UNVERIFIED` (a warning naming what
to verify by hand in the Nexus UI), never a failure of the release.

## When to use this tool alongside another

`tools/asf-svn` and this adapter cover the two halves of an ASF JVM
release: `asf-svn` stages, promotes, and prunes the `dist/` tree;
`asf-nexus` verifies the Maven staging repository that runs in
parallel with it. `release-promote` handles only the `dist/` half
today — the Nexus half's close/drop/promote lifecycle is intentionally
out of scope here (see
[#1173](https://github.com/apache/magpie/issues/1173), "Out of
scope").

## Centralized-model note

There is no local checkout to reason about: the staging repository is
addressed by its id (`orgapache<project>-NNNN`, assigned by Nexus at
deploy time and not predictable, so it must be read from the planning
issue or passed in — the same way `release-promote` sources
`staging_url`). The snapshots repository
(`content/repositories/snapshots/`) is a different beast entirely and
is never a valid vote target — the classification rules treat it as a
hard finding, not a lookup miss.
