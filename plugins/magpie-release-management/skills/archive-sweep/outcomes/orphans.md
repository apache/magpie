<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Outcome — orphans and pre-releases

**Orphans.** A release on the distribution surface but on no train in `<project-config>/release-trains.md` is listed in `orphans` and never archived (Golden rule 3).
The hand-off block lists each one; the RM decides whether to archive it, keep it, or reconcile it into a known train.

**Pre-releases.** A pre-release in the release area is listed in `prereleases`, never counted as a train's latest and never archived; it is a hand-off to the RM, who decides whether it belongs there.

Neither ever appears in `past_retention` or in `render`'s `commands` (`not_archived` names them).
Copy their `handoff_reasons` into the Step 1 JSON and repeat them in the Step 3 hand-back.
