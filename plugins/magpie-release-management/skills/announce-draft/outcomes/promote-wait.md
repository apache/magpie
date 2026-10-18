<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Blocked — promote-wait gate active

**Likely cause:** the promote commit is less than one hour ago (Golden rule 3).

The blocker `release-config preflight` printed names the exact UTC time the gate clears; surface it as written.
`promote_clear_after_utc` carries that time only when the gate is the only blocker;
when the `promoted` label check also fails, the verdict reports `null`.

**Remediation:** wait until `promote_clear_after_utc`, or pass `--skip-promote-wait <reason>`.
The reason is logged in both outputs: the Step 2 body and the Step 4 hand-back.
