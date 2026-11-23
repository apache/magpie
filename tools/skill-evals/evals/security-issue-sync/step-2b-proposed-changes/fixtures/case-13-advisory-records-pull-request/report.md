<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Observed tracker state

**Tracker:** myproject-s/myproject-s#64 (closed as `completed`)
**Current labels:** security issue, cve allocated, announced - emails sent, announced
**Current milestone:** 4.2.1 (closed)
**Current assignee:** jsnow-rm

**Body fields:** *CVE tool link* = `https://cveprocess.apache.org/cve5/CVE-2026-00004`; *Public advisory URL* = `https://lists.apache.org/thread/m3n5b7v9c1x2z4l6k8j0h` (populated by the Step 14 combined apply)

## Gathered state from Step 1

**Process step:** post-15 (closed-`announced` bucket)

**cve.org (Step 1g):** `CVE-2026-00004` is `PUBLISHED`, `datePublished` 2026-05-11.
The *CVE-published* reporter notification was already sent on 2026-05-12 (status comment and sent message on the thread) — no new email.

**Security-pages checklist (Step 1g closed-bucket scan):**
- Hand-off comment carries `- [ ] <!-- apache-magpie: security-pages-checklist v1 --> Project security pages updated with CVE-2026-00004` — still unticked
- `security_pages_reminder_pending: false` (the project configures `advisory_records`, so sync makes the edit itself)

**Advisory records (Step 1g):**
- `advisory_records` is configured in `projects/myproject/project.md`: `layout: cve-json-file`, `vcs: git`, `branch: main`, `path: security/cves/{cve_id}.json`, `publish: pull-request`, `pull_request.repo: myproject/myproject-site`
- `user.md → environment.advisory_records_fork` = `maya/myproject-site`, `advisory_records_fork_remote` = `fork`
- No comment carries `<!-- apache-magpie: advisory-records v1 -->`
- Branch lookup: `gh pr list --repo myproject/myproject-site --head advisory-records/CVE-2026-00004 --state all` returned no pull request (`records_pr_state: NONE`)
- The `advisory-records` planner (run without `--apply`) exited `0` with status `proposed`:
  - `security/cves/CVE-2026-00004.json`: create
  - Pull request: `maya:advisory-records/CVE-2026-00004` → `myproject/myproject-site` `main`, title `Add CVE-2026-00004 to the security pages`; body lists the file, the cve.org publication date and the public announcement URL
  - Commands, in order, after confirmation:
    1. `magpie-vcs -C ~/code/myproject-site clean`
    2. `magpie-vcs -C ~/code/myproject-site branch` (must print `main`)
    3. `magpie-vcs -C ~/code/myproject-site update`
    4. `magpie-vcs -C ~/code/myproject-site new-branch advisory-records/CVE-2026-00004`
    5. `advisory-records … --publish pull-request … --apply` (writes the file and the pull-request body file)
    6. `magpie-vcs -C ~/code/myproject-site stage security/cves/CVE-2026-00004.json`
    7. `magpie-vcs -C ~/code/myproject-site diff --cached security/cves/CVE-2026-00004.json`
    8. `magpie-vcs -C ~/code/myproject-site commit -m 'Add CVE-2026-00004 to the security pages'`
    9. `magpie-vcs -C ~/code/myproject-site push fork advisory-records/CVE-2026-00004` (publishes the branch on the fork)
    10. `magpie-vcs -C ~/code/myproject-site switch main`
    11. `MAGPIE_ALLOW_SECURITY_LANG=1 gh pr create --repo myproject/myproject-site --base main --head maya:advisory-records/CVE-2026-00004 --title 'Add CVE-2026-00004 to the security pages' --body-file <scratch>/CVE-2026-00004-pull-request.md` (publishes the pull request)
- `advisory_records_pending: true`

Produce the numbered proposal for this tracker.
