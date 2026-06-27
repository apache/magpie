<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Project-agnosticism (de-ASF coupling)
status: experimental
kind: feature
mode: infra
source: >
  MISSION.md § Abstract and § Affordability and vendor neutrality
  ("'project' means both an ASF PMC and any non-ASF community, neither is
  a second-class citizen"). README.md § Skill families. The placeholder +
  adapter contract in adapters.md and adoption-and-setup.md, and the
  backend-flag model proven in docs/release-management/ (distribution /
  approval / announcement backends).
acceptance:
  - No shipped skill hardcodes an ASF-only assumption a non-ASF adopter
    cannot satisfy; every ASF-specific surface is a placeholder, an
    adapter backend, or a capability-flag branch with a documented
    non-ASF path and a sensible default.
  - Behavioural branches that differ by ecosystem (list vote vs
    PR-approval, svn dist vs github-releases, ICLA vs DCO, mailing-list
    intake vs GitHub discussion) are selected by a declared
    `<project-config>` flag, not by editing the skill.
  - The catalogue stays runnable by an ASF adopter unchanged: ASF is the
    default profile, not a removed one.
---

# Project-agnosticism (de-ASF coupling)

## What it does

Keeps the skill catalogue usable by any open-source community, not just
ASF projects, by ensuring every ASF-specific assumption lives behind one
of three generalisation mechanisms rather than being baked into a skill.
MISSION makes non-ASF adopters first-class; this area is the standing
audit and the mechanism that holds that promise as the catalogue grows.

The three mechanisms, in order of preference:

1. **Placeholders** for project-specific *values* (`<tracker>`,
   `<upstream>`, `<security-list>`, `<default-branch>`, …), resolved from
   `<project-config>/`. This is the default and already widely used.
2. **Adapters** for swapping the backing *system* a step talks to
   (`tools/gmail`, `tools/ponymail`, `tools/jira`, `tools/github`,
   `tools/mail-source`). See [adapters.md](adapters.md).
3. **Capability / backend flags** for the harder case: a step whose
   *workflow itself* differs by ecosystem. The adopter declares the
   profile in `<project-config>` and the skill branches on it, keeping the
   step sequence identical while only the emitted commands / wording
   change. This is the "conditional flags" mechanism, already modelled in
   `docs/release-management/` (`release_dist_backend`,
   `release_approval_mechanism`, `release_announce_backend`).

## Where it lives

- The placeholder + config-resolution contract: `adapters.md`,
  `adoption-and-setup.md`, and the adopter scaffold
  `projects/_template/`.
- The backend-flag precedent: `docs/release-management/README.md`
  (§ adopter backends) and `projects/_template/release-management-config.md`.
- The skills carrying residual ASF coupling to audit, by family:
  - **security**: `security@`-style intake and the ASF security-team
    relay (`security-issue-import-via-forwarder`), CVE allocation assuming
    an ASF CNA (`security-cve-allocate`), Vulnogram as the CVE tool.
  - **contributor / committer growth**: `committer-onboarding`
    (ICLA gate, PMC vote semantics, `dev@` announce),
    `contributor-nomination` (committer-vs-PMC roster framing).
  - **release-management** (proposed): the whole ASF release ritual,
    already designed with backend flags; the audit confirms the non-ASF
    paths stay first-class as the skills land.
  - any skill whose prose names `apache.org` lists, `svn` dist trees,
    `incubator`, or ASF-only governance steps without a flag.

## Behaviour & contract

- **ASF is the default profile, never the only one.** Generalising a
  skill must not regress the ASF path; the ASF behaviour becomes the
  default value of the new flag / adapter, so an ASF adopter sees no
  change.
- **Prefer the lightest mechanism.** A value goes in a placeholder; a
  system swap goes in an adapter; only a genuine workflow fork gets a
  capability flag. Do not add a flag where a placeholder suffices.
- **Every flag has a documented non-ASF path.** A capability flag that
  only enumerates ASF options (e.g. an approval mechanism with just
  `dev-list-vote`) is incomplete; it must name at least one non-ASF
  option (`pr-approval`, `maintainer-roster`, `github-discussion`, …) and
  describe the adopter-facing default.
- **Advisory, not paternalistic.** The audit surfaces candidate coupling
  for a maintainer to judge; some ASF strings are legitimate (examples,
  the ASF default profile, ASF-specific docs). It does not auto-rewrite.

## Out of scope

- Removing or de-prioritising ASF support: ASF is the reference adopter
  and the default profile.
- The privacy gate and sandbox ([privacy-llm-gate.md](privacy-llm-gate.md),
  [agent-isolation-sandbox.md](agent-isolation-sandbox.md)), which are
  already project-agnostic.
- The runtime adapter implementations themselves (that is
  [adapters.md](adapters.md)); this area governs the *coupling audit* and
  the *flag contract*, not the adapter code.

## Acceptance criteria

1. Every shipped skill is auditable for ASF coupling, and each residual
   coupling is a placeholder, an adapter backend, or a capability-flag
   branch with a non-ASF default.
2. Ecosystem-divergent workflow steps branch on a declared
   `<project-config>` flag, not on skill edits.
3. The ASF profile runs the catalogue unchanged (default-valued flags),
   and a non-ASF profile can be declared without editing any skill body.

## Validation

```bash
# Advisory sweep: surface ASF-coupled tokens in skill bodies that should
# be a placeholder, an adapter backend, or a capability-flag branch.
# Expected to flag legitimate ASF-default examples too; a human judges.
grep -rInE 'apache\.org|[[:alpha:]]+@apache|\bdev@|\bannounce@|\bICLA\b|\bsvn (mv|co|commit)|\bincubator\b|Vulnogram' skills/ \
  | grep -vE '<[a-z-]+>' | head -40
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **ASF-coupling lint is advisory only.** Check #10 in
  `tools/skill-and-tool-validator` (SOFT category `asf_coupling`) now
  surfaces coupled tokens automatically on every validator run.  The 86
  advisory hits in the current catalogue are real candidates for
  generalisation (mostly bare `PMC` and a few `announce@apache.org` /
  `dist/dev/` hits); a human judges which warrant a placeholder or
  capability-flag change.  No remaining tooling gap — the lint exists.
- **No non-ASF adopter profile fixture exists** to run the catalogue
  against. A `projects/_template` non-ASF profile plus a smoke eval that
  drives a representative skill through it would turn acceptance #3 into a
  measurable gate.
- **The capability-flag vocabulary for security intake and CVE allocation
  is now documented** in
  `projects/_template/security-intake-config.md` (intake channel,
  forwarder relay, CNA tool, allocation gate, and new
  `disclosure_governance` flags). Skills read these flags in follow-on
  updates as each flag is wired in.
- **Contributor intake capability flags** (ICLA vs DCO vs none, governance
  model) are documented in `projects/_template/committer-onboarding-config.md`
  (added by the `capability-flags-committer-intake` work item).
