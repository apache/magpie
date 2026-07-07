<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Script output from `python3 .claude/skills/magpie-list-skills/scripts/list_skills.py`:

issue
  issue-fix-workflow: Draft a fix for a triaged general issue.
  issue-reassess: Re-assess a batch of previously closed issues.
  issue-reassess-stats: Summarise reassessment campaign statistics.
  issue-reproducer: Build a minimal reproduction for an open issue.
  issue-triage: Triage a batch of open issues.

list-skills
  list-skills: Print a human-readable index of every skill in this repository.

pr-management
  pr-management-code-review: Review open pull requests against the project quality criteria.
  pr-management-mentor: Draft a mentor reply to a pull request.
  pr-management-stats: Produce a health dashboard for the open-PR backlog.
  pr-management-triage: Triage a batch of open pull requests.

security
  security-cve-allocate: Walk a security team member through allocating a CVE.
  security-issue-deduplicate: Check whether an incoming report duplicates an existing tracker.
  security-issue-fix: Draft a fix for a CVE-allocated security report.
  security-issue-import: Import new security reports from Gmail into the tracker.
  security-issue-import-from-md: Open one or more tracker issues from a markdown findings file.
  security-issue-import-from-pr: Import a security report from a GitHub pull request.
  security-issue-invalidate: Mark a security report as invalid.
  security-issue-sync: Synchronise tracker fields with the current state of a report.
  security-issue-triage: Triage an imported security report.

setup
  setup-isolated-setup-install: Install the framework's secure agent setup on this machine.
  setup-isolated-setup-update: Update the framework's secure agent setup to a newer version.
  setup-isolated-setup-verify: Walk the verification checklist for the framework's secure agent setup.
  setup-override-upstream: Promote a local .apache-magpie-overrides skill into a PR upstream.
  setup-shared-config-sync: Commit and push the user's shared Claude config to the sync repo.
  setup: Adopt and maintain the apache-magpie framework in a project repo.

write-skill
  write-skill: Author a new skill for the Apache Magpie framework, or update an existing one.

User: "Show me only the pr-management skills — I don't need the others."
