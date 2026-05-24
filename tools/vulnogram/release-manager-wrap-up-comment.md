<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [✅ Lifecycle complete — `CVE_ID`](#-lifecycle-complete--cve_id)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!--
     Wrap-up comment posted by `security-issue-sync` AFTER the
     tracker has been auto-closed at the end of the
     post-advisory lifecycle close-out (Step 6 of the
     release-manager hand-off comment templates;
     `Advisory archived on <users-list>` row of Step 2b in
     `.claude/skills/security-issue-sync/SKILL.md`).

     **INFORMATIONAL ONLY.** The combined apply that triggers
     this comment runs when the advisory's archive URL is captured
     on `<users-list>` AND every intermediate write (label flip,
     JSON re-push, REVIEW → PUBLIC via `vulnogram-api-record-publish`,
     tracker close, project-board archive, conditional milestone
     close) succeeded — all sync-driven. By the time this comment
     posts:

       * the tracker is already closed (`completed`);
       * the `announced` label has moved the board item to the
         `Announced` column AND sync has archived it from the
         board (`archiveProjectV2Item` mutation);
       * the milestone is closed (last-sibling case only — sync
         skips the milestone close otherwise).

     **No residual actions for the RM.** This template intentionally
     carries no asks. The post-2026-05-24 design (see RM feedback
     on airflow-s#415) is: when the auto-archive + auto-close-
     milestone are sync-driven, asking the RM to do them anyway
     creates a confusion class — "agent says it's done, but also
     asks me to do it manually?". The wrap-up comment stays as a
     timeline marker for audit-trail purposes but does not solicit
     manual actions.

     Idempotency: the HTML marker on the first line is the skill's
     idempotency anchor. On a re-sync where this comment already
     exists, sync skips the post.

     Placeholders the skill substitutes:

       CVE_ID                    e.g. CVE-2026-40690
       RM_HANDLE                 GitHub handle of the release manager
                                 (with leading `@`)
       PUBLISH_TIMESTAMP         ISO-8601 timestamp of the
                                 `vulnogram-api-record-publish` call
                                 that flipped REVIEW → PUBLIC.
       ADVISORY_URL              The captured `<users-list>` archive
                                 URL for the advisory.
       MILESTONE_BULLET          Optional. Set when sync detected
                                 every milestone-sibling was also
                                 closed at this moment, and reads:
                                 `Milestone [`MILESTONE_TITLE`](MILESTONE_URL)
                                 closed automatically (every tracker on
                                 it is now done).`
                                 Unset otherwise; sync omits the line
                                 entirely.
-->
<!-- apache-steward: release-manager-wrap-up v1 -->

## ✅ Lifecycle complete — `CVE_ID`

RM_HANDLE — the post-advisory close-out for [`CVE_ID`](ADVISORY_URL) ran cleanly:

- Vulnogram record moved `REVIEW → PUBLIC` at `PUBLISH_TIMESTAMP` (CNA-feed dispatch to `cve.org` triggered).
- Tracker labels flipped `fix released → announced - emails sent + announced`.
- Tracker closed as `completed`.
- Board item archived from the `Announced` column.
- MILESTONE_BULLET

CVE will propagate to [`cve.org`](https://www.cve.org/CVERecord?id=CVE_ID) within a few hours. On the next sync run after that, a courtesy *"CVE is live on cve.org"* note will go to the reporter on the original email thread.

**Nothing else is owed on your side.** Thanks for shepherding `CVE_ID` through the release + advisory.

---

**References:**

- The combined apply that brought the tracker to this state is documented in `.claude/skills/security-issue-sync/SKILL.md` Step 2b (`Advisory archived on <users-list>` row).
- The state-transition tool: [`vulnogram-api-record-publish`](oauth-api/README.md).
