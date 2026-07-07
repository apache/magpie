<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tool: Apache Verum
Confirmed findings (user selected all):

verum:DEAD-001:airflow/models/connection.py:210 — unreachable block after early return
verum:DOC-004:airflow/models/connection.py:15  — missing module-level docstring
verum:SEC-cve-2024-12345:airflow/models/connection.py:88 — potential credential exposure via log output [security; CVE-2024-12345]

Note: Finding verum:SEC-cve-2024-12345 carries CVE-2024-12345 and is labelled security by the tool.
