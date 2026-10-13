<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Outcome — schema violations

`schema_violations` names every required field of [`audit-record-schema.md`](../audit-record-schema.md) whose value is `MISSING`,
each as `"<field> — required field is MISSING"`.

Surface the list to the RM before Step 3. It does **not** block the PR proposal:
the RM decides whether to gather the missing data and re-run, or to propose the incomplete record with its `_MISSING_` markers visible
(the PR body lists every missing field).
A maximally incomplete record still renders in full; the violations are additive, never a reason to skip the hand-back.
