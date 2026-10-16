<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Observed tracker state

**Tracker:** myproject-s/myproject-s#61 (closed as `completed`)
**Current labels:** security issue, cve allocated, announced - emails sent, announced
**Current milestone:** 9.0.99 (closed)
**Current assignee:** jsnow-rm

**Body fields:** *CVE tool link* = `https://cveprocess.apache.org/cve5/CVE-2026-00001`; *Public advisory URL* = `https://lists.apache.org/thread/q8w1e4r7t2y5u9i3o6p0a` (populated by the Step 14 combined apply)

## Gathered state from Step 1

**Process step:** post-15 (closed-`announced` bucket)

**cve.org (Step 1g):** `CVE-2026-00001` is `PUBLISHED`, `datePublished` 2026-04-02.
The *CVE-published* reporter notification was already sent on 2026-04-03 (status comment and sent message on the thread) — no new email.

**Security-pages checklist (Step 1g closed-bucket scan):**
- Hand-off comment carries `- [ ] <!-- apache-magpie: security-pages-checklist v1 --> Project security pages updated with CVE-2026-00001` — still unticked
- No comment carries `<!-- apache-magpie: security-pages-reminder v1 -->`
- `security_pages_reminder_pending: false` (the project configures `advisory_records`, so sync makes the edit itself)

**Advisory records (Step 1g):**
- `advisory_records` is configured in `projects/myproject/project.md`: `layout: release-page`, `vcs: svn`, `format: xml`, `path: xdocs/security-{line}.xml`
- No comment carries `<!-- apache-magpie: advisory-records v1 -->`
- The `advisory-records` planner (run without `--apply`) exited `0` with status `proposed`:
  - `xdocs/security-9.xml`: update — create section `Fixed in My Project 9.0.99` (2026-03-30) before `Fixed in My Project 9.0.98`, holding the CVE-2026-00001 entry
  - Commands, in order, after confirmation:
    1. `magpie-vcs -C ~/code/myproject-site clean`
    2. `magpie-vcs -C ~/code/myproject-site update`
    3. `advisory-records … --apply`
    4. `magpie-vcs -C ~/code/myproject-site stage xdocs/security-9.xml`
    5. `magpie-vcs -C ~/code/myproject-site diff xdocs/security-9.xml`
    6. `magpie-vcs -C ~/code/myproject-site commit -m 'Add CVE-2026-00001 to the security pages'` (on Subversion this publishes the change)
- `advisory_records_pending: true`

Produce the numbered proposal for this tracker.
