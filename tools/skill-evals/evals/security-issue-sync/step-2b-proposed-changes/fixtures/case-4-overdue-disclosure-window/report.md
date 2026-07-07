<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Observed tracker state

**Tracker:** myproject-s/myproject-s#88
**Current labels:** security issue, cve allocated
**Current milestone:** (none)
**Current assignee:** (none)

## Disclosure governance flags (Step 0.6)

Loaded from `projects/myproject/security-intake-config.md`:
- `window_days: 45`
- `grace_period_days: 14`
- `pre_announce_distributors: false`

## Gathered state from Step 1

**PR with the fix:** (none — no fix PR opened yet)
**Process step:** 7 (cve allocated, pending fix)

**Disclosure deadline check (Step 1a):**
- `issue_age_days: 60` (issue created 2026-04-30; today 2026-06-29)
- `overdue_for_disclosure: true` (60 > 45; `announced` label absent)
- `approaching_window_end: false` (window already exceeded)
- `grace_period_expired: false` (no fix shipped yet)
- `distributor_notify_pending: false`

Produce the numbered proposal for this tracker.
