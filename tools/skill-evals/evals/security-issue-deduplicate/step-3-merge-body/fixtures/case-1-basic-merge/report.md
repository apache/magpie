<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Two trackers describe the same underlying vulnerability and must be merged into one issue body. Both trackers' fields are given below, in the same format.

## Kept tracker (issue #42) — the primary report

The issue description: Authenticated user can send a crafted connection URL to /api/v1/connections/test, causing the Airflow API server to make outbound HTTP requests to internal network hosts.

Short public summary for publish: SSRF via connection test API endpoint allows authenticated users to probe internal hosts.

Affected versions: >= 2.9.0, < 2.10.3

Security mailing list thread: Alice Example (initial report): https://lists.apache.org/thread/abc123

Public advisory URL: _No response_

Reporter credited as: Alice Example

PR with the fix: _No response_

CWE: CWE-918

Severity: Unknown

CVE tool link: https://cveprocess.apache.org/cve5/CVE-2024-12345

## Drop tracker (issue #67) — fold into the kept tracker as a second independent report

The issue description: The /api/v1/connections/test endpoint follows HTTP
redirects to RFC-1918 addresses, bypassing the basic host check. An
authenticated API user can exploit this to reach metadata services
(e.g. 169.254.169.254) via a redirect chain.

Short public summary for publish: SSRF via redirect follow in connection
test allows authenticated users to reach cloud metadata endpoints.

Affected versions: >= 2.8.0, < 2.10.3

Security mailing list thread: Bob Researcher (redirect-chain vector):
https://lists.apache.org/thread/xyz789

Public advisory URL: _No response_

Reporter credited as: Bob Researcher

PR with the fix: _No response_

CWE: CWE-918

Severity: Unknown

CVE tool link: _No response_
