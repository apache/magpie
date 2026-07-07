<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Two trackers describe the same underlying vulnerability and must be merged into one issue body. Both trackers' fields are given below, in the same format.

## Kept tracker (issue #55) — the primary report

The issue description: Crafted XCom value containing a pickle payload triggers RCE in the scheduler during DAG execution.

Affected versions: 2.10.0

Security mailing list thread: Carol Dev (initial): https://lists.apache.org/thread/aaa111

Reporter credited as: Carol Dev

CWE: CWE-502

Severity: Unknown

CVE tool link: https://cveprocess.apache.org/cve5/CVE-2024-99999

## Drop tracker (issue #71) — fold into the kept tracker as a second independent report

The issue description: XCom pickle deserialization is present from 2.7.0
onwards — the fix in the kept tracker's targeted version is incomplete
because the vulnerable code path also exists in the Celery worker context
from 2.7.0.

Affected versions: >= 2.7.0, < 2.10.3

Security mailing list thread: Dave Security (wider range): https://lists.apache.org/thread/bbb222

Reporter credited as: Dave Security

CWE: CWE-502

Severity: Unknown

CVE tool link: _No response_
