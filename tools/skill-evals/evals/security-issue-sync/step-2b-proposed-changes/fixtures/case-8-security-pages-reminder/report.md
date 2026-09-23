<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Observed tracker state

**Tracker:** myproject-s/myproject-s#57
**Current labels:** security issue, cve allocated, announced - emails sent, announced
**Current milestone:** 2.3.0 (exists on tracker, all siblings closed)
**Current assignee:** jsnow-rm

**Body fields:** *Public advisory URL* = `https://lists.apache.org/list.html?users@myproject.apache.org` (populated by the Step 14 combined apply)

## Gathered state from Step 1

**Process step:** 15 (announced; tracker closed, CVE record `PUBLIC` on the CVE tool but not yet resolving on `cveawg.mitre.org` — no close proposal)

**Security-pages checklist status (Step 1d marker scan):**
- Hand-off comment (posted at the `pr merged` → `fix released` transition) carries
  `- [ ] <!-- apache-magpie: security-pages-checklist v1 --> Project security pages updated with CVE-2026-40187` — still unticked
- No comment anywhere on the tracker records the marker in ticked `- [x]` form
- `announced` label set + *Public advisory URL* populated → the advisory has demonstrably shipped
- `security_pages_url` = `https://myproject.apache.org/security` (from `projects/myproject/project.md`)
- RM (jsnow-rm) has made no reply since the wrap-up comment

Produce the numbered proposal for this tracker.
