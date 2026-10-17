<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2 — GPG signatures

From `release-verify signatures`. Anything but `PASS` is `FAIL` (Golden rule 3); private-key material in `KEYS` stops the skill (Golden rule 5).

| Symptom | Likely cause | Remediation |
|---|---|---|
| Step 2 FAIL — bad signature | Artefact was corrupted or signed with wrong key | RM re-signs and re-stages |
| Step 2 FAIL — key not in KEYS | Signing key not yet published | RM adds key via `release-keys-sync` (proposed) |
