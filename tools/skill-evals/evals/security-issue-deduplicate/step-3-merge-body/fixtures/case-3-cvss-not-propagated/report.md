<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Two trackers describe the same underlying vulnerability and must be merged into one issue body. Both trackers' fields are given below, in the same format.

## Kept tracker (issue #42) — the primary report

The issue description: SSRF via connection test API.

Affected versions: >= 2.9.0, < 2.10.3

Security mailing list thread: Alice Example: https://lists.apache.org/thread/abc123

Reporter credited as: Alice Example

CWE: CWE-918

Severity: Unknown

CVE tool link: https://cveprocess.apache.org/cve5/CVE-2024-12345

## Drop tracker (issue #67) — fold into the kept tracker as a second independent report

The issue description: Same SSRF via redirect chain, additional vector via
the Celery worker HTTP hook. Reporter assessed CVSS 8.8 (High).

Affected versions: >= 2.9.0, < 2.10.3

Security mailing list thread: Bob Researcher: https://lists.apache.org/thread/xyz789

Reporter credited as: Bob Researcher

CWE: CWE-918

Severity: CVSSv3 8.8 HIGH (reporter-assessed)

CVE tool link: _No response_
