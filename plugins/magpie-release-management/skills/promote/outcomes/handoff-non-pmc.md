<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Outcome — `handoff-non-pmc`

The RM passed every other check but does not appear on the roster at `release_approver_roster_path` (default `<project-config>/pmc-roster.md`).
The `dist/release/` tree (for `release_dist_backend = svnpubsub`) is PMC-write-only by default (Golden rule 5),
so this is a hand-off, not a blocker: the skill continues to Step 2.

Render Step 2 with the Step 0 verdict file (`--verdict`, which makes it a hand-off) and `--rm <RM's GitHub handle or apache_id> --roster-path <preflight values.roster_path>`.
The render puts the hand-off note first in `command_block` and in `handoff_note`:
ask a PMC member to run the command set on the RM's behalf, or request PMC access from VP of `<project>`.
The command set is still populated, so a PMC member can copy and run it;
the mirror note, the proposed label and the next steps are emitted as usual.

If the RM is already a PMC member and the roster is stale, the remediation is updating the roster, not bypassing the gate.
