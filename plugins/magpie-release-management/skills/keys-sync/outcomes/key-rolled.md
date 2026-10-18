<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 0 outcome — key rolled (`blocked`)

The configured fingerprint is in KEYS, but none of the UIDs the keyserver reports for it is one of that entry's UIDs (key rolled, or every UID changed),
or the keyserver returned no key or no UID, so the two cannot be compared.
This is the Golden rule 4 hand-off: stop before any command is emitted and surface `blockers` as written, with both UIDs.

Present both options to the RM; **do not pick one for the RM**:

- **Append** the updated key block to KEYS, keeping the existing entry; or
- **Replace** the existing entry with the updated key block.

Either way, the RM updates `rm_key_fingerprint` if the key itself changed, then re-runs this skill.
When the keyserver returned no key or no UID, the RM uploads the public key (and verifies its email address there) and re-runs.
