<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `SKIP-SECURITY`

**Fires when** the title, the body, a commit message or the most recent comment matches a security pattern — a CVE ID, "SQL injection", "remote code execution", "auth bypass", `XSS` and the like (the same list `pr-management-triage` uses).
[`stale-sweep classify`](../../../../../tools/pr-management/src/pr_management/stale_sweep/classify.py) decided it; `details.security_matches` lists each match and where.

**Action:** none — never post a stale comment on it. The recap reminds the maintainer to review it manually.

## What you judge

Whether the PR is in fact a public fix for an unreported vulnerability. If it may be, it is a matter for the project's security process (`<security-list>`), not for a public stale comment that draws attention to it.
