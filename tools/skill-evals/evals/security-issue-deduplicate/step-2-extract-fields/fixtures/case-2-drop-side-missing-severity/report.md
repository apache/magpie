<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Mock: gh issue view 287 (keep) --repo airflow-s/airflow-s

**Body:**
### The issue description
DAG serialization leaks environment variable names in task output when debug logging is enabled.

### Short public summary for publish
_No response_

### Affected versions
apache/airflow 2.7.3

### Security mailing list thread
No public archive URL — tracked privately on Gmail thread 18f3a2b9c1d4e999

### Public advisory URL
_No response_

### Reporter credited as
Bob Svensson (bob@corp.io)

### PR with the fix
_No response_

### CWE
CWE-200 Exposure of Sensitive Information

### Severity
MEDIUM

### CVE tool link
_No response_

**Labels:** security issue, airflow, needs triage
**Milestone:** null
**CVE JSON attachment comment:** no

---

## Mock: gh issue view 301 (drop) --repo airflow-s/airflow-s

**Body:**
### The issue description
Task logs may expose environment variable names when the airflow.cfg debug_log_level is set. Depending on the secrets backend configuration, values could be partially exposed.

### Short public summary for publish
_No response_

### Affected versions
apache/airflow 2.7.0, 2.7.1, 2.7.2, 2.7.3

### Security mailing list thread
https://lists.apache.org/thread/envleak456

### Public advisory URL
_No response_

### Reporter credited as
Diana Park (diana@vuln.io)

### PR with the fix
_No response_

### CWE
CWE-200 Exposure of Sensitive Information

### Severity
HIGH

### CVE tool link
_No response_

**Labels:** security issue, airflow, needs triage
**Milestone:** null
**CVE JSON attachment comment:** no
