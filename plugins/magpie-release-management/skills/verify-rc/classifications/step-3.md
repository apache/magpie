<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 3 — Checksums

From `release-verify checksums`. md5 never fails alone.

| Symptom | Likely cause | Remediation |
|---|---|---|
| Step 3 FAIL — checksum mismatch | Artefact was corrupted or a sha512 / sha256 digest file is wrong | RM regenerates artefact + digest files |
| Step 3 FAIL — `.sha512` missing | Required sha512 digest not staged | RM generates and stages the `.sha512` file |
| Step 3 WARN — `.md5` present | Deprecated md5 digest staged (matching or not) | RM drops the `.md5` file for the next RC |
