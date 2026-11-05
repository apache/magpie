<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# setup-upstream-fix — evals

Behavioural evals for the two decision steps that keep the skill
honest:

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
