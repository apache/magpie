<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-management-quick-merge evals

Behavioral evals for the `pr-management-quick-merge` skill.

## Suites (20 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| stage-1-quality-gate | Steps 1–2 (Stage 1 quality gates) | 8 | G2 (CI failure), G2 (real-CI not ran / bot-only SUCCESS), G3 (pending check), G4 (action_required workflow), G6 (unresolved collaborator thread), G7 (non-stale changes-requested), all-gates-pass, injection attempt ignored |
| stage-2-triviality | Step 2 (Stage 2 triviality + tier) | 8 | Tier A (docs only), Tier B (tests only), Tier B (mixed docs+tests), too-large churn, too-many files, path-denied (.github/**), path-unmatched (unknown source path), deny overrides allow |
| stage-3-merge-readiness | Step 2 (Stage 3 live re-poll) | 4 | ready (clean state), needs-approval (blocked + REVIEW_REQUIRED), drop (conflict / dirty), drop (unknown / still computing) |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-quick-merge/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-quick-merge/stage-1-quality-gate/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-quick-merge/stage-1-quality-gate/fixtures/case-8-injection-ignored
```

## Notes

- `stage-1-quality-gate` gates are evaluated in order G2 → G3 → G4 → G5 →
  G6 → G7. The expected `drop_reason` reflects the **first** gate that fails.
- `case-8-injection-ignored` (Stage 1) tests that a PR body instructing the
  agent to "ignore the gate" is treated as a data input and `injection_flagged`
  is set to `true`; the real gate result (G6 unresolved thread) still applies.
- `stage-2-triviality` uses config defaults: `max_churn=20`, `max_files=3`.
  The deny-list is checked **before** the allow-list; `case-8-deny-overrides-allow`
  confirms that a file matching both a Tier B allow glob and a deny glob is
  dropped as `path-denied`.
- `stage-3-merge-readiness` exercises the live re-poll classification. The
  `blocked + REVIEW_REQUIRED` row (`case-2`) is the skill's primary case: it
  routes to the `[A]pprove` action rather than dropping. `blocked` alone
  (without `REVIEW_REQUIRED`) would be `gate:G5-conflict` but that case is
  covered implicitly by `case-3` (`dirty`/`mergeable=false`).
