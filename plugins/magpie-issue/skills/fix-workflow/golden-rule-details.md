<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Golden rule details

Companion to [`SKILL.md`](SKILL.md). Full body text of Golden rules 1–7; SKILL.md keeps each rule's title with a pointer here.

## Golden rule 1 — every state-changing action is a proposal

Writing files in `<upstream>`, committing, pushing, opening a PR, posting to `<issue-tracker>`, transitioning workflow state — each requires explicit user confirmation; invoking the skill is **not** a blanket *"yes"*.

## Golden rule 2 — never autopilot the PR

Even when the fix is complete and clean, the skill does **not** open a PR (draft or otherwise), comment on the issue, self-assign, or transition workflow state on autopilot; the hand-back contract (Step 8) is firm.
With explicit instruction the skill *may* open a **draft** PR after the user reviews the title, body, and diff — never non-draft, never on autopilot.

## Golden rule 3 — failing test first

The project's fix-workflow convention is *failing test on `<default-branch>` first, then the smallest production change that turns it green*.
If the issue carries an adapted reproducer (a `verdict.json` from [`issue-reproducer`](../reproducer/SKILL.md)), it is the starting point for the regression test — but the **test** lives in the project's test tree, not in a scratch file.

## Golden rule 4 — smallest fix; scope discipline

The diff is the test, the production change, and any directly-required edit — nothing else.
No drive-by reformatting, no stray imports, no speculative refactor.

## Golden rule 5 — grounded identifiers only

AI tooling reaches for plausible method or flag names that don't exist or have been renamed; `grep` the identifier in the working tree before depending on it.
If it isn't there, it isn't there.

## Golden rule 6 — cause, not symptom

The reproducer throws an exception at line N; the patch adds a guard at line N — *sometimes* correct, often not; the symptom may reflect earlier state the surrounding code assumed was populated.
Trace one or two frames up before reaching for the local guard.

## Golden rule 7 — green build is the floor, not the ceiling

The targeted test passing means the change isn't obviously wrong, not that it is right.
Scope discipline, regression-test quality, and the hand-back contract all still apply.
