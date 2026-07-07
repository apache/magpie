<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Two trackers describe the same underlying vulnerability and must be merged into one issue body. Both trackers' fields are given below, in the same format.

## Kept tracker (issue #55) — the primary report

The issue description: Crafted XCom pickle payload triggers RCE in scheduler.

Affected versions: 2.10.0

Security mailing list thread: Carol Dev: https://lists.apache.org/thread/aaa111

Reporter credited as: Carol Dev

CWE: CWE-502

Severity: Unknown

CVE tool link: https://cveprocess.apache.org/cve5/CVE-2024-99999

## Drop tracker (issue #71) — fold into the kept tracker as a second independent report

The issue description: Same pickle RCE but reporter characterises it as
arbitrary code execution via unsafe deserialization of operator arguments,
classifying the primary weakness differently.

Affected versions: 2.10.0

Security mailing list thread: Dave Security: https://lists.apache.org/thread/bbb222

Reporter credited as: Dave Security

CWE: CWE-94

Severity: Unknown

CVE tool link: _No response_
