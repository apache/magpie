<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 4 — Apache RAT

From `release-management verify-rc rat`.

| Symptom | Likely cause | Remediation |
|---|---|---|
| Step 4 WARN — RAT config absent | `release-build.md` has no RAT config section | RM adds RAT config; do not proceed to vote without it |
| Step 4 FAIL — unapproved headers | Source file missing or incorrect licence header | RM fixes headers and cuts a new RC |
