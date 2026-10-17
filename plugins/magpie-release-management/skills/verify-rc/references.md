<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-verify-rc — references

This skill composes with:

- `release-vote-draft` (proposed) — downstream step;
  a PASS result here is the expected prerequisite before the `[VOTE]` thread is opened.
- `release-vote-tally` (proposed) — further downstream;
  tallies the vote responses after the `[VOTE]` thread closes.
- `release-announce-draft` — lands after the vote passes and the RC is promoted.

Sources:

- [`docs/release-management/process.md`](../../../../docs/release-management/process.md) —
  Step 6 context.
- [`docs/release-management/spec.md`](../../../../docs/release-management/spec.md) —
  `release-verify-rc` per-skill specification.
- [`<project-config>/release-management-config.md`](../../../magpie-setup/templates/release-management-config.md) —
  adopter keys this skill reads (`keys_file_url`, `keyserver`,
  `release_dist_url_template`, `version_manifest_files`).
- [`<project-config>/release-build.md`](../../../magpie-setup/templates/release-build.md) —
  expected artefact list, digest set, binary-exclude list, RAT config,
  `§ Source archive`, `§ Reproducibility checks`.
- [`docs/release-management/reproducibility.md`](../../../../docs/release-management/reproducibility.md) —
  Step 9 background: the source-archive contract, the reproducibility
  checks, and the 🪶 ASF-specific automated-signing validation.
- [`tools/release-verify`](../../../../tools/release-verify/README.md) —
  the Steps 1–3, 5–8 and 10 checks and their JSON.
- [`tools/release-management`](../../../../tools/release-management/README.md#verify-rc) —
  `release-management verify-rc`: the `release-verify` arguments from `release-build.md`,
  the Step 4, 6b, 6c, 7 and 9 classifications and the Step 10 report and attestation.
- [`tools/reproducible-archive`](../../../../tools/reproducible-archive/README.md) —
  `repro-archive check` / `build` / `compare`.
- [`tools/maven-artifact-verify`](../../../../tools/maven-artifact-verify/README.md) —
  the JVM-artefact checker behind Step 6b (blocking checks 1–3 of
  [issue #1173](https://github.com/apache/magpie/issues/1173)).
- [`tools/asf-nexus`](../../../../tools/asf-nexus/README.md) — the
  read-only Nexus staging-repository adapter behind Step 6c (check 4
  of [issue #1173](https://github.com/apache/magpie/issues/1173)):
  endpoint contract, recipes, classification rules.
- [ASF publishing Maven release artifacts](https://infra.apache.org/publishing-maven-artifacts.html) —
  the stage / close / vote / promote workflow behind Step 6c.
- [ASF Incubator distribution guidelines § Maven distribution](https://incubator.apache.org/guides/distribution.html) —
  the policy behind the Step 6b POM and disclaimer checks.
- [Maven Central publishing requirements](https://central.sonatype.org/publish/requirements/) —
  the mandatory sources/javadoc companions behind Step 6b check 3.
- [reproducible-builds.org § Archive metadata](https://reproducible-builds.org/docs/archives/) —
  the rules `repro-archive check` verifies.
- `release-keys-sync` (proposed) — remediation path when a signing
  key is not yet in the project `KEYS` file.
- `release-vote-draft` (proposed) — downstream step; opens the
  `[VOTE]` thread after this skill reports `PASS`.
- [Apache RAT](https://creadur.apache.org/rat/) — licence-header
  checking tool.
- [ASF release distribution](https://infra.apache.org/release-distribution.html) —
  binary and digest requirements.
- [ASF release policy § release approval](https://www.apache.org/legal/release-policy.html#release-approval) —
  voter obligation reminder.
