<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Per-issue activity state

Companion to [`SKILL.md`](SKILL.md). What to fetch for each confirmed
candidate issue (Step 2) and how to build the per-issue state bag.

For each issue in the confirmed candidate pool, fetch (in parallel where
the tracker permits):

1. **Issue metadata** — title, status, labels, component, reporter
   identity, created-at, last-updated-at, last-comment-at, total comment
   count, last-commenter identity (reporter vs maintainer vs other).
2. **Prior stale-sweep nudge check** — search the issue's comments for a
   prior `REQUEST-UPDATE` nudge from this framework. Record whether one
   exists and how many days ago it was posted. This drives Golden rule 4.
3. **Recent-activity fingerprint** — was the last comment by the reporter
   (unread question waiting on maintainers), a maintainer (request pending
   on reporter), or a bot? This shapes the proposal text.
4. **Security screening** — apply Golden rule 6: scan the issue body and
   first/last comments for security signals. Mark security-flagged issues
   as `SKIP-SECURITY` and do not classify them further.

After gathering, build the per-issue state bag. If the tracker returns no
timestamps for an issue, mark it `SKIP-NO-TIMESTAMPS` and skip.
