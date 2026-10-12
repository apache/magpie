<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Override — `--skip-verify-check <reason>`

Resolves the verify-rc gate (Golden rule 5): Step 0's verdict reports `skip_verify_override: true` and no verify-rc blocker.
The reason is logged in both outputs:

- **Step 2** — pass it as `--skip-verify-check "<reason>"`; the body carries
  `[SKIP-VERIFY: release-verify-rc was not run for this RC; the RM accepted this with the reason: <reason>.]` and `skip_verify_logged` is `true`.
- **Step 4** — restate the reason in the hand-back.

A verify-rc `FAIL` is never drafted over without this override (Hard rules).
