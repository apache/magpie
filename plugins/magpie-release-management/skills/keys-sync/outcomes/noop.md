<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 0 outcome — `noop`

The configured fingerprint is already in KEYS, and the keyserver's primary UID for it is one of that KEYS entry's UIDs (Golden rule 3).
Report `noop_reason` as the verdict printed it — it names the UID — and stop: emit no KEYS block and no command.
The RM proceeds directly to `release-rc-cut`.
