<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Failure modes

Companion to [`SKILL.md`](SKILL.md).

| Symptom | Likely cause | Remediation |
|---|---|---|
| Pool returns 0 candidates | Thresholds too high or tracker genuinely healthy | Surface and stop; suggest reducing `warn_days` or widening the filter |
| Pool exceeds 50 | Very large stale backlog | Stop; ask user to narrow with component/label filter or smaller threshold |
| Timestamp unavailable for an issue | Tracker API doesn't return `updated_at` for this issue type | Skip the issue, mark `SKIP-NO-TIMESTAMPS`, surface in recap |
| Second close confirmation refused | User changed their mind after seeing the comment posted | Leave the issue open; it already has the pre-close notice |
| Post call fails mid-loop | Transient rate-limit or auth expiry | Stop, surface the failed item, instruct the user to retry remaining items |
