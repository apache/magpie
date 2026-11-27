<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# setup-upstream-fix — evals

Behavioural evals for the two decision steps that keep the skill
honest:

- **step-0-preflight** — where Steps 4–5 happen: in this session when it
  already runs in the framework checkout, otherwise never by cloning
  inside the adopter's sandbox, but through a brief sent to a live
  session in the user's framework clone, or written to a file for the
  user to paste into one.
- **step-2-classify** — is an encountered quirk a *framework
  defect* (proceed), a *local misconfiguration* (stop, remediate
  locally), *already fixed upstream* (propose upgrade), or
  *uncertain* (offer an issue, not a fix PR)? This is the gate
  that keeps local problems out of `apache/magpie`.
- **step-3-dedup** — before proposing a new fix PR, does an
  existing issue/PR already cover it? `none` → propose; an open
  issue/PR → inform, don't duplicate; a merged fix → propose
  upgrade.
- **step-5-adversarial-review** — the shared pre-PR block in a
  non-security skill: skipped silently under `mode: on-demand`, `off`,
  or an empty reviewer list; run with the drafted title and body file
  under `mode: on-pr-create`.

Each case feeds a `report.md` to the model against the named step
of `SKILL.md` and asserts the JSON in `expected.json`.

`pointer-routing/` (2 cases, whole body with no sibling text): the agent finds `pre-pr-adversarial-review.md` from the pointer alone at the review point and opens nothing before it; the output spec names no file, so removing the pointer fails the case.

## Run history

Live model runs over this whole eval directory, newest first.
Generated from [`runs.jsonl`](runs.jsonl) by `skill-eval-journal render`;
do not edit the table by hand.
Columns and rules: [Recording runs](../../README.md#recording-runs).

| Date | Ref | Model | Runs | Result | Notes |
|---|---|---|---|---|---|
| 2026-11-27 | `493c5161` (fix/upstream-fix-vetted-dedup-search) | `opus[1m]` | 2 | pass |  |
| 2026-11-27 | `160b4de7` (fix/upstream-fix-vetted-dedup-search) | `opus[1m]` | 1 | pass |  |
| 2026-11-22 | `95a76395` (fix/upstream-fix-session-handoff) | `opus[1m]` | 5 | pass |  |
| 2026-11-22 | `8c9d7fe6` (fix/upstream-fix-session-handoff) | `opus[1m]` | 2 | pass |  |
