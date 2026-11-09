<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Thread: PR #14205 — "fix(logging): use UTC timestamp in all log lines"
MaxAgentTurns: 2
AgentCommentCount: 0
OutOfScopeTopics: [security, CVE, deprecation, licensing, architecture]

Messages (chronological):
  1. contributor (role: contributor, login: yuki-m): "Switches all internal log
     timestamps to UTC to avoid ambiguity in multi-timezone deployments.
     Tested on Airflow 2.9.1. Added a regression test in
     tests/core/test_logging.py. Changelog entry added."
  2. contributor (role: contributor, login: yuki-m): "Let me know if you want
     me to split the test into a separate commit."

ConventionPointersTriggers: []

MaintainerLogins: [committer-a, committer-b]
RecentMaintainerCommentCount: 0
