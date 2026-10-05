<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § JVM artefact checks: `nexus_staging_repo`
unset. The Step 1 listing for this RC contains no `.jar` and no
`.pom` — a source-only RC (the project publishes no Maven artefacts).

Things to classify here:

- The JVM-only gate skips the step before anything else: a project
  with no Maven artefacts has no Nexus staging repository and must
  not be warned about one. `SKIP`, stated explicitly.
- The unset `nexus_staging_repo` key is consistent with that —
  nothing here needs to be configured.
