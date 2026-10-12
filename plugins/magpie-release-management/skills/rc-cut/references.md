<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-rc-cut — references

- [`docs/release-management/process.md`](../../../../docs/release-management/process.md) —
  Steps 4–5 context.
- [`docs/release-management/spec.md`](../../../../docs/release-management/spec.md) —
  `release-rc-cut` per-skill specification.
- [`<project-config>/release-build.md`](../../../magpie-setup/templates/release-build.md) —
  adopter keys this skill reads (`build_command`, `expected_artefacts`,
  `digest_set`, `binary_exclude_list`, `source_archive_*`,
  `export_ignore_reviewed`, `reproducibility_*`).
- [`docs/release-management/reproducibility.md`](../../../../docs/release-management/reproducibility.md) —
  the source-archive contract, the reproducible-builds.org rule mapping,
  the reproducibility checks, and the ASF automated-signing option.
- [`tools/reproducible-archive`](../../../../tools/reproducible-archive/README.md) —
  `repro-archive build` / `check` / `compare` / `recipe` / `epoch`.
- [reproducible-builds.org § Archive metadata](https://reproducible-builds.org/docs/archives/) —
  the archive rules the source artefact satisfies.
- [Infra § Automated release signing](https://infra.apache.org/release-signing.html#automated-release-signing) —
  🪶 ASF-specific policy behind Step 2c.
- [`<project-config>/release-management-config.md`](../../../magpie-setup/templates/release-management-config.md) —
  adopter keys this skill reads (`release_dist_backend`,
  `release_dist_url_template`, `release_publish_command_template`,
  `rm_key_fingerprint`, `release_branch_base`, `git_upstream_remote`).
- `release-keys-sync` — upstream step; the RM's public key must be in
  `KEYS` before the RC is tagged.
- `release-prepare` — upstream step; the prep PR it creates must be merged.
- `release-verify-rc` — downstream step; verifies the staged RC before
  the `[VOTE]` thread opens.
- `release-vote-draft` — downstream step; reads the planning-issue comment
  this skill posts to construct the `[VOTE]` email.
- [ASF release policy](https://www.apache.org/legal/release-policy.html) —
  governance on release tagging, signing, and distribution.
- [ASF release distribution § sigs-and-sums](https://infra.apache.org/release-distribution.html#sigs-and-sums) —
  MD5 / SHA-1 prohibition; SHA-512 baseline.
- [ASF release signing](https://infra.apache.org/release-signing.html) —
  key-management and signing-command guidance.
