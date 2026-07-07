<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Repository: apache/polaris, default branch, 30-day window.
Total workflow runs analysed: 120.

Classification results:

FLAKY jobs (2):
- "unit-tests / python-3.11": failure_rate=0.16, rerun_recovery=5,
  evidence="Fails ~16% of runs; 5 of 8 failures resolved on re-run."
- "e2e-tests / chrome": failure_rate=0.175, rerun_recovery=7,
  evidence="Fails ~17.5% of runs; every failure resolved on re-run."

CONSISTENTLY-BROKEN jobs (1):
- "integration-tests / database": failure_rate=0.90, rerun_recovery=0,
  evidence="Fails 90% of runs with no re-run recoveries."

CLEAN jobs (8): lint/ruff, type-check/mypy, docs/build, unit-tests/python-3.10,
unit-tests/python-3.12, security/bandit, build/package, deploy/staging.
