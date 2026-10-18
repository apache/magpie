<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 1 — RC inventory

From `release-verify inventory`. A `FAIL` is final (Golden rule 3).

| Symptom | Likely cause | Remediation |
|---|---|---|
| Step 1 FAIL — artefact missing | RC was staged incompletely | RM re-stages the missing artefact |
| Step 1 WARN — optional artefact missing | An artefact `release-build.md` marks `optional` was not staged | RM confirms the omission is intended, or stages it |
