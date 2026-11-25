<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 3 — Checksums

From `release-verify checksums`. md5 never fails alone.

| Symptom | Likely cause | Remediation |
|---|---|---|
| Step 3 FAIL — checksum mismatch | Artefact was corrupted or a sha256 / sha512 digest file is wrong | RM regenerates artefact + digest files |
| Step 3 FAIL — required digest missing | The required digest (`sha512` when the set lists it, else the first in the set) has no staged file | RM generates and stages the required digest file |
| Step 3 WARN — `.md5` present | Deprecated md5 digest staged (matching or not) | RM drops the `.md5` file for the next RC |
