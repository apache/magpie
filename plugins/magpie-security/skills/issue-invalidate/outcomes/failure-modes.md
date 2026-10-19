<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-invalidate — failure modes

Read from [`SKILL.md` § *Failure modes*](../SKILL.md#failure-modes).

| Symptom | Likely cause | Fix |
|---|---|---|
| Step 0 hard stop fires (`cve allocated`) | The tracker has a CVE; closing as invalid here would orphan a CVE record | Reject the CVE in Vulnogram first, then re-invoke. The CVE-tool URL is in the *CVE tool link* body field. |
| Step 0 hard stop fires (`fix released` / `announced`) | The advisory has already shipped | Escalate to the team — closing as invalid here is a public retraction, not a routine close. |
| `archiveProjectV2Item` returns `not found` for the item | Project-board item ID has changed (rare; usually because the item was manually moved) | Re-run the introspection query. If the tracker is genuinely not on the board, skip 6e and note in the rollup. |
| Gmail draft creation fails with `oauth_curl` 401 | OAuth token expired | Re-run the credential refresh per [`tools/gmail/oauth-draft/README.md`](../../../../../tools/gmail/oauth-draft/README.md); do not fall back to `claude_ai_mcp` unless the [backend selection rule](../../../../../tools/gmail/draft-backends.md#how-the-skills-pick-a-backend) permits it (no links in the body). |
| The tracker title contains characters that break heredoc / shell quoting | Title with `'` or backticks | Use `--body-file` paths everywhere (already the convention); never inline issue titles into shell strings. |
| Rollup comment not found (very old tracker, pre-convention) | Rollup didn't exist yet | Nothing to do: Step 6a's `rollup-append` creates it with just the close entry. |
| The tracker is `security@`-imported but the inbound thread can't be located in Gmail | Thread was archived / Gmail account changed / threadId is stale | Surface to the user; offer the `silent` confirmation form — the close still happens, the rollup notes the missing reply. |
