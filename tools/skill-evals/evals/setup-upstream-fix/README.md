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

Each case feeds a `report.md` to the model against the named step
of `SKILL.md` and asserts the JSON in `expected.json`.
