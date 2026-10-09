<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `security_language_signal` — row 7b

**Fires when** the title, the body (outside the triage fold) or any commit message matches a security pattern: a CVE ID, or a phrase such as "remote code execution", "SQL injection", `XSS`, "privilege escalation".
[`classify`](../../../../../tools/pr-management/README.md#triage-classify--pr-management-triage-step-2) decided it; `details.security_matches` lists every match with its location (`title`, `body`, or `commit <sha7>: <subject>`) — the renderer fills `<security_matches>` from it verbatim.

**Proposed action:** `comment` — [`actions/comment.md`](../actions/comment.md), with the security-language body: ask the contributor to neutralise the wording, or confirm the disclosure is complete.

## What you judge

Whether the PR is in fact a public fix for an unreported vulnerability.
If it looks like one, stop: this is a matter for the project's security process (`<security-list>`), not for triage — do not post anything that confirms the security nature of the change on the public PR.
If the language is incidental (a test named after an attack class, an unrelated CVE in a dependency bump note), skip or post the neutral body.
