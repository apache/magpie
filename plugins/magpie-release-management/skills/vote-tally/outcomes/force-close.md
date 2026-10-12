<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Outcome — `--force-close <reason>`

The flag lets the tally proceed before the window closes, or past unresolved ambiguous votes.
Pass `--force-close` to `vote-tally tally`:

- ambiguous votes are excluded from all tally counts; they are listed under `ambiguous` and counted in `excluded_ambiguous_count`;
- the Step 3 render lists each one as `AMBIGUOUS  excluded (--force-close)` in the vote details and sets `force_close_logged: true`.

It never reclassifies an `AMBIGUOUS` vote as `+1` (Hard rules).
In the hand-back, restate the reason and name the excluded ambiguous votes.
