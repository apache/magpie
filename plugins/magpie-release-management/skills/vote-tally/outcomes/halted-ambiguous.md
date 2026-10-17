<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Outcome — halted on an ambiguous vote

The tally reports `halted_on_ambiguous: true` and `result: null` when any counted vote is `AMBIGUOUS` (Golden rule 3):

- Stop and surface the list, each vote flagged `AMBIGUOUS, needs RM call` with its reason.
- Ask the RM to resolve each ambiguous vote on the thread (ask the voter to clarify, or accept a retraction) and then re-run, **or** pass `--force-close <reason>` to exclude ambiguous votes and proceed.
- Do NOT advance to Step 3 while unresolved ambiguous votes remain unless `--force-close` was passed; the Step 3 render refuses a halted tally.

A clear later vote from the same person replaces an earlier ambiguous one; an ambiguous latest vote still halts (see [`../superseded-votes.md`](../superseded-votes.md)).
