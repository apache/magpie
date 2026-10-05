<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Staging-repository verification rules (check 4)](#staging-repository-verification-rules-check-4)
  - [Gate (when the check runs at all)](#gate-when-the-check-runs-at-all)
  - [Findings](#findings)
    - [Hard findings (`FAIL`)](#hard-findings-fail)
    - [Warnings (never `FAIL`)](#warnings-never-fail)
  - [Output contract](#output-contract)
  - [Deliberately out of scope here](#deliberately-out-of-scope-here)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Staging-repository verification rules (check 4)

The classification the calling skill applies to the probe output,
encoded from the boundary conditions of
[apache/magpie#1173](https://github.com/apache/magpie/issues/1173)
(check 4). The rules are deliberately conservative in the same
direction as `maven-artifact-verify`'s: a correct release must never
be failed, and an un-verifiable claim is reported as a warning naming
what to verify by hand — never silently passed.

## Gate (when the check runs at all)

Step 6c runs only when **all** of these hold; otherwise it `SKIP`s
with the reason stated explicitly:

- The Step 1 listing contains at least one `.jar` or `.pom`
  (JVM-only — a Python or Rust ASF project has no staging repository
  and must not be warned about one).
- `release-build.md § JVM artefact checks` does not declare
  `jvm_artefact_checks: off`.
- The project is an ASF one — the resolved `organization`
  (`<project-config>/project.md` → `organization`) is `ASF`, the
  same chain Step 9's automated-signing gate reads;
  `repository.apache.org` is ASF infrastructure. Non-ASF adopters
  skip on this gate alone.
- A staging repository id is resolvable: the
  `nexus_staging_repo` key of `release-build.md § JVM artefact
  checks`, then the planning issue body when the RM passed
  `--post-to`. Nexus assigns the id (`orgapache<project>-NNNN`) at
  deploy time and it cannot be predicted, so an unresolvable id is a
  clean `SKIP` naming where to supply it — never a guess.

## Findings

One line each, naming the artefact or repository and what is wrong.
`status` is `FAIL` when any hard finding is present, `WARN` when only
warnings remain, `PASS` otherwise.

### Hard findings (`FAIL`)

- **Repository not reachable.** `404` at the id given for this RC —
  the jar surface the vote is supposed to cover does not exist there.
  A hard `FAIL`, worded factually as "repository not reachable at the
  id given for this RC" — the same rule `operations.md` recipe 1, the
  Step 6c body and the troubleshooting table state; a `404` after a
  successful promotion is expected in other flows, so the phrasing
  stays factual either way. A sandbox network refusal is never this
  finding: it is `STATE-UNVERIFIED` / not-probed — one says the
  runner could not see, the other says nothing is there.
- **Repository `open`.** An open staging repository is still mutable
  and is not a valid vote target — a `FAIL`, distinct from the
  not-reachable case (the two must never be conflated: one says
  "nothing there", the other "something editable there").
- **Snapshots repository targeted.** The id is `snapshots` or the
  inventory resolves under
  `content/repositories/snapshots/` — never a valid vote target,
  whatever the version string claims.
- **Coordinates/version mismatch.** The inventory's
  `<groupId-with-slashes>/<artifactId>/<version>/` paths must
  correspond to the release version this RC declares (the plain
  version carried by the staged POMs Step 6b verified locally — the
  `-rcN` suffix lives in the dist path and tag, not in the Maven
  version). A mismatch means the vote would cover jars for some other
  version.
- **Missing `.asc`.** A `.jar` or `.pom` in the inventory with no
  sibling `.asc` — the same coverage the main artefacts get in Step 2.
- **Incomplete companion set.** A main jar whose `-sources.jar` or
  `-javadoc.jar` (or their `.asc` / checksum companions) is absent
  from the inventory — Maven Central's close-time validation will
  reject the promotion, and the RM should learn that before the
  `[VOTE]` opens, not after. `packaging=pom` modules are exempt (no
  jar to companion); other classifiers (`-tests`, `-shaded`,
  `-linux-x86_64`, …) are not part of the required set and are
  neither expected nor flagged.

### Warnings (never `FAIL`)

- **`STATE-UNVERIFIED`.** The staging API needs credentials the
  runner does not have (or the API call failed for another reason),
  so the authoritative `closed` state could not be confirmed on the
  anonymous path. Name what to verify by hand in the Nexus UI. A
  voter with no Nexus account hitting this is the expected shape of
  the anonymous path, not a defect in their environment — and so is
  a sandbox network refusal, which reports `STATE-UNVERIFIED` /
  not-probed, never "repository not reachable".
- **Stale sibling repositories.** The profile listing shows several
  staging repositories for the project. Surface all of them with
  their ids and states; proceed only with the one matching the RC's
  version and note the rest as stale from an earlier attempt.

## Output contract

`release-verify-rc` Step 6c returns exactly this JSON shape:

```json
{
  "step": "nexus-staging",
  "status": "PASS" | "WARN" | "FAIL" | "SKIP",
  "staging_repos": [
    {"id": "<repository id>", "state": "closed" | "open" | "unverified", "matches_rc": true}
  ],
  "nexus_findings": ["<one line per hard finding or warning>"],
  "paste_recipe": "<multi-line shell commands>"
}
```

`staging_repos` lists every staging repository surfaced for the
project (single entry on the anonymous path, one per sibling on the
authenticated path); `matches_rc` is whether the repository's
inventory corresponds to the RC's declared version. `nexus_findings`
carries only hard findings and warnings — a fully passing probe is an
empty list. `paste_recipe` mirrors the recipes in
[`operations.md`](operations.md) with every placeholder resolved to a
concrete value, so the RM can re-run the probe by hand.

## Deliberately out of scope here

- **Feeding the staged tree to `maven-artifact-verify`.** Checks 1–3
  (and, once they exist, the informational checks 5–7) should
  eventually run against the jars and POMs *in* the staging
  repository, so every check shares a single artefact source. That
  needs a download step this adapter does not have yet; until then,
  Step 6b keeps verifying the locally staged set and Step 6c verifies
  the remote surface, and the two report side by side.
- **Close / drop / promote.** Read-only by construction — see
  [`tool.md`](tool.md), *Read-only, by construction*.
