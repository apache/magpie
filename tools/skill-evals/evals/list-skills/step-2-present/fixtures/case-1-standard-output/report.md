<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Script output from `python3 .claude/skills/magpie-list-skills/scripts/list_skills.py`:

Skills installed for this repository (24 total)
==================================================

issue/  (5)
  /magpie-issue-fix-workflow     Draft a fix for a triaged general issue.
  /magpie-issue-reassess         Re-assess a batch of previously closed issues.
  /magpie-issue-reassess-stats   Summarise reassessment campaign statistics.
  /magpie-issue-reproducer       Build a minimal reproduction for an open issue.
  /magpie-issue-triage           Triage a batch of open issues.

pr-management/  (4)
  /magpie-pr-management-code-review  Review open pull requests against the project quality criteria.
  /magpie-pr-management-mentor       Draft a mentor reply to a pull request.
  /magpie-pr-management-stats        Produce a health dashboard for the open-PR backlog.
  /magpie-pr-management-triage       Triage a batch of open pull requests.

security/  (9)
  /magpie-security-cve-allocate           Walk a security team member through allocating a CVE.
  /magpie-security-issue-deduplicate      Check whether an incoming report duplicates an existing tracker.
  /magpie-security-issue-fix              Draft a fix for a CVE-allocated security report.
  /magpie-security-issue-import           Import new security reports from Gmail into the tracker.
  /magpie-security-issue-import-from-md   Open one or more tracker issues from a markdown findings file.
  /magpie-security-issue-import-from-pr   Import a security report from a GitHub pull request.
  /magpie-security-issue-invalidate       Mark a security report as invalid.
  /magpie-security-issue-sync             Synchronise tracker fields with the current state of a report.
  /magpie-security-issue-triage           Triage an imported security report.

setup/  (6)
  /magpie-setup                          Adopt and maintain the apache-magpie framework in a project repo.
  /magpie-setup-isolated-setup-install   Install the framework's secure agent setup on this machine.
  /magpie-setup-isolated-setup-update    Update the framework's secure agent setup to a newer version.
  /magpie-setup-isolated-setup-verify    Walk the verification checklist for the framework's secure agent setup.
  /magpie-setup-override-upstream        Promote a local .apache-magpie-overrides skill into a PR upstream.
  /magpie-setup-shared-config-sync       Commit and push the user's shared Claude config to the sync repo.

utilities/  (2)
  /magpie-list-skills   Print a human-readable index of every skill installed for this repository.
  /magpie-write-skill   Author a new skill for the Apache Magpie framework, or update an existing one.

Installed from:
   24  repository (.agents/skills)

Invoke a skill by typing the name shown above, or describe what you want to do.

User: "Thanks, that's exactly what I needed."
