<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Mock: gh issue view 312 (keep) --repo airflow-s/airflow-s

**Body:**
### The issue description
Arbitrary callable invocation via pickle deserialization in XCom backend. A compromised worker can inject a crafted pickle payload that executes on the scheduler.

### Short public summary for publish
_No response_

### Affected versions
apache/airflow 2.8.0, 2.8.1, 2.9.0

### Security mailing list thread
No public archive URL — tracked privately on Gmail thread 18f3a2b9c1d4e507

### Public advisory URL
_No response_

### Reporter credited as
Alice Nguyen (alice@example.com)

### PR with the fix
https://github.com/apache/airflow/pull/52199

### CWE
CWE-502 Deserialization of Untrusted Data

### Severity
HIGH

### CVE tool link
https://cveprocess.apache.org/cve5/CVE-2025-44812

**Labels:** security issue, airflow, cve allocated, pr merged
**Milestone:** Airflow 3.2.2
**CVE JSON attachment comment:** yes (comment #9050)

---

## Mock: gh issue view 328 (drop) --repo airflow-s/airflow-s

**Body:**
### The issue description
Scheduler RCE via poisoned XCom value deserialization. An attacker with write access to the database can craft a pickle value that the scheduler executes during DAG processing.

### Short public summary for publish
_No response_

### Affected versions
apache/airflow 2.8.0, 2.8.1

### Security mailing list thread
https://lists.apache.org/thread/xyz987abc

### Public advisory URL
_No response_

### Reporter credited as
Carlos Mendez (carlos@infosec.io)

### PR with the fix
_No response_

### CWE
CWE-502 Deserialization of Untrusted Data

### Severity
HIGH

### CVE tool link
_No response_

**Labels:** security issue, airflow, needs triage
**Milestone:** null
**CVE JSON attachment comment:** no
