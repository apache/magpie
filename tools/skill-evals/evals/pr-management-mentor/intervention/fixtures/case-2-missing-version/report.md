<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Thread: Issue #9017 — "BashOperator crashes with exit code 1"
MaxAgentTurns: 2
AgentCommentCount: 0
OutOfScopeTopics: [security, CVE, deprecation, licensing, architecture]

Messages (chronological):
  1. contributor (role: contributor, login: alex-w): "Running a BashOperator
     task always exits with code 1, even though my script returns 0. I tested
     my script manually and it works. Here is the minimal reproducer:

     ```python
     bash_task = BashOperator(task_id='test', bash_command='echo hello')
     ```

     Expected: task succeeds. Actual: task marked as failed."

MaintainerLogins: [committer-a, committer-b]
RecentMaintainerCommentCount: 0
