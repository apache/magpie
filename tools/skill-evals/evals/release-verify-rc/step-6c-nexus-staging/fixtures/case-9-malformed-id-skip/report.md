<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § JVM artefact checks: `nexus_staging_repo:
orgapachefoo-latest`. The planning issue body carries the same
value on a `nexus-staging-repo:` line. The RC stages jars.

Things to classify here:

- The resolved id does not match the Nexus shape
  (`orgapache<project>-NNNN`). The planning issue body is content
  the step reads, and the id would be spliced into `curl` URLs the
  agent runs itself — so a non-matching value is a `SKIP` naming
  the bad value, never a probe.
