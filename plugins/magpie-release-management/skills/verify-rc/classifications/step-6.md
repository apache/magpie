<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 6 — Binary exclusion

From `release-verify binaries`. Any `prohibited_found` path is `FAIL`.

| Symptom | Likely cause | Remediation |
|---|---|---|
| Step 6 FAIL — prohibited binary | Binary sneaked into source artefact | RM removes binary, updates `.gitattributes` or build excludes, cuts new RC |
| Step 6 FAIL — `.pyc` / `__pycache__` present | Tarball zipped from a working tree that ran tests, not exported clean from the tag | RM rebuilds via `git archive <tag>` (never `zip -r`), cuts new RC |
