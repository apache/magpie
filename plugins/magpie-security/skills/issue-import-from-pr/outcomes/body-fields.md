<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-pr — the tracker body fields

From Step 5b, as the table carried it; `security-management issue-import-from-pr render-body` fills every row except *Affected versions*, which the agent passes in.
Two differences from the table: the PR body goes in as an inert fenced block (byte-exact, info string `text`, a fence longer than any backtick run in it, so it renders as plain text and none of its headings, images or references take effect),
and the sentinel names the PR by its URL, as [`tracker-body-template.md`](../tracker-body-template.md) always did.

| Field | Value |
|---|---|
| **The issue description** | Two paragraphs: (1) a one-line note `> **Imported from public PR <upstream>#<N>** — there is no inbound \`security@\` report; the PR description below is the public statement of the vulnerability.` (2) the PR body verbatim, fenced if it is heavily templated. |
| **Short public summary for publish** | `_No response_` (the team writes this when drafting the advisory; not derivable from the PR). |
| **Affected versions** | Per the scope's *Affected versions* convention from [`scope-labels.md`](../../../../../<project-config>/scope-labels.md). The `packageName` shape comes from `scope_detection.labels.<scope>.packageName` in [`<project-config>/project.md`](../../../../../<project-config>/project.md#scope-detection). |
| **Security mailing list thread** | Sentinel: `N/A — opened from public PR <upstream>#<N>; no security@ thread`. Creating via `gh api` skips the form's required-field check, but the sentinel stops later `security-issue-sync` runs flagging the field as missing. |
| **Public advisory URL** | `_No response_`. |
| **Reporter credited as** | `_No response_`: the PR author is **not** credited as reporter, per the *[Reporter credit policy](../SKILL.md#reporter-credit-policy-for-public-pr-imports)* below. The user may fill it for another individual with a project-specific reason. |
| **PR with the fix** | `pr.url` (e.g. `https://github.com/<upstream>/pull/65703`). |
| **Remediation developer** | `pr.author.name` (else `pr.author.login`), one name per line, after the [bot/AI credit policy](../../../../../tools/cve-tool-vulnogram/bot-credits-policy.md): a bot author leaves the field `_No response_`, and Step 6 names the matched rule. No email-clarification step here, since there is no inbound reporter. |
| **CWE** | `_No response_` (the team assesses; not derivable). |
| **Severity** | `Unknown`. |
| **CVE tool link** | `_No response_` (filled by [`security-cve-allocate`](../../cve-allocate/SKILL.md)). |
