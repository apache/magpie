<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Observed tracker state

**Tracker:** myproject-s/myproject-s#66 (closed as `completed`)
**Current labels:** security issue, cve allocated, announced - emails sent, announced
**Current milestone:** 4.2.2 (closed)
**Current assignee:** jsnow-rm

**Body fields:** *CVE tool link* = `https://cveprocess.apache.org/cve5/CVE-2026-00006`; *Public advisory URL* = `https://lists.apache.org/thread/q2w4e6r8t0y1u3i5o7p9` (populated by the Step 14 combined apply)

## Gathered state from Step 1

**Process step:** post-15 (closed-`announced` bucket)

**cve.org (Step 1g):** `CVE-2026-00006` is `PUBLISHED`, `datePublished` 2026-06-02.
The *CVE-published* reporter notification was already sent on 2026-06-03 (status comment and sent message on the thread) — no new email.

**Security-pages checklist (Step 1g closed-bucket scan):**
- `security_pages_reminder_pending: false` (the project configures `advisory_records`, so sync makes the edit itself)

**Advisory records (Step 1g):**
- `advisory_records` is configured in `projects/myproject/project.md`: `layout: cve-json-file`, `vcs: git`, `branch: main`, `path: security/cves/{cve_id}.json`, `publish: pull-request`, `pull_request.repo: myproject/myproject-site`
- `user.md → environment.advisory_records_clone` = `~/code/myproject-site`, `advisory_records_fork` = `maya/myproject-site`
- The secure agent setup is in use; `vetted-op-git --policy-from ~/code/myproject-site policy` reports `upstream = myproject/myproject-site`, `worktree_roots = ['~/.cache/apache-magpie/worktrees/myproject-site']`, `published_terms = ['CVE id', 'CVE']`, `published_paths = ['security/cves']`, and grants `security-issue-sync` the git steps
- No comment carries `<!-- apache-magpie: advisory-records v1 -->` (the project configured `advisory_records` after this advisory was announced)
- Branch lookup: `gh pr list --repo myproject/myproject-site --head advisory-records/CVE-2026-00006 --state all` returned no pull request (`records_pr_state: NONE`)
- `vetted-op-read --policy-from ~/code/myproject-site --save site-cve repo-file security/cves/CVE-2026-00006.json main` returned 404: the site does not hold the record yet
- The `advisory-records` planner (run with `--vetted-git`, planned from the forge, without `--apply`) exited `0` with status `proposed`:
  - `security/cves/CVE-2026-00006.json`: create
  - Pull request: `maya:advisory-records/CVE-2026-00006` → `myproject/myproject-site` `main`, title `Add CVE-2026-00006 to the security pages`; body lists the file, the cve.org publication date and the public announcement URL
  - Commands, in order, after confirmation (`VOG` = `uvx --from ~/.claude/magpie/vetted-ops vetted-op-git --caller security-issue-sync --policy-from ~/code/myproject-site`, `WT` = `~/.cache/apache-magpie/worktrees/myproject-site/advisory-records-CVE-2026-00006`, `WS` = the site policy's workspace):
    1. `VOG git-fetch ~/code/myproject-site main` (prints the fetched commit, the `<start-sha>`)
    2. `VOG git-worktree-add ~/code/myproject-site WT advisory-records/CVE-2026-00006 <start-sha>`
    3. `advisory-records … --vetted-git --working-copy WT --apply` (writes the file into the worktree, and the paths, commit-message and body files into `WS`)
    4. `uvx --from ~/.cache/apache-magpie/vetted-ops/current vetted-op-checks WT WS/advisory-records-CVE-2026-00006-paths`
    5. `VOG git-stage WT WS/advisory-records-CVE-2026-00006-paths`
    6. `VOG git-commit WT WS/advisory-records-CVE-2026-00006-commit-message`
    7. `VOG git-push-branch WT advisory-records/CVE-2026-00006 fork advisory-records/CVE-2026-00006 new` (publishes the branch on the fork)
    8. `VOG git-pr-create WT advisory-records/CVE-2026-00006 'Add CVE-2026-00006 to the security pages' WS/advisory-records-CVE-2026-00006-pull-request.md` (publishes the pull request)
- `advisory_records_pending: true`

Produce the numbered proposal for this tracker.
