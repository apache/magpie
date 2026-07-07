<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Thread: Issue #15880 — "Possible RCE via template rendering"
MaxAgentTurns: 2
AgentCommentCount: 0
OutOfScopeTopics: [security, CVE, deprecation, licensing, architecture]

Messages (chronological):
  1. contributor (role: contributor, login: marco-v): "I found what looks like
     a remote code execution vulnerability in the Jinja2 template rendering
     path. If you pass a specially crafted DAG name, you can escape the
     sandbox. I have a proof of concept."

MaintainerLogins: [committer-a, committer-b]
RecentMaintainerCommentCount: 0
