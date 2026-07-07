<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Observed tracker state

**Tracker:** airflow-s/airflow-s#401
**Current labels:** security issue, cve allocated, pr merged
**Current milestone:** Airflow 3.2.3 (exists on tracker)
**Current assignee:** mik-laj (collaborator)

## Disclosure governance flags (Step 0.6)

Loaded from `projects/airflow/security-intake-config.md`:
- `window_days: 90`
- `grace_period_days: 14`
- `pre_announce_distributors: true`

## Gathered state from Step 1

**PR with the fix:** apache/airflow#67241
**PR state:** MERGED (merged 2026-06-20)
**PR milestone:** Airflow 3.2.3 (pending release — not yet tagged)

**Process step:** 11 (pr merged — fix in main, awaiting release)

**Disclosure deadline check (Step 1a):**
- `issue_age_days: 58` (within 90-day window)
- `overdue_for_disclosure: false`
- `approaching_window_end: false`
- `grace_period_expired: false`
- `distributor_notify_pending: true` (pre_announce_distributors true; pr merged label present; announced label absent)

Produce the numbered proposal for this tracker.
