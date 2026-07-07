<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Mock: gh issue view 319 (keep) --repo airflow-s/airflow-s

**Body:**
### The issue description
SSRF via S3 log handler endpoint_url parameter. A worker can supply an arbitrary endpoint_url that causes the scheduler to make HTTP requests to internal network hosts during log read-back.

### Short public summary for publish
_No response_

### Affected versions
apache/airflow 2.8.0, 2.8.1

### Security mailing list thread
https://lists.apache.org/thread/ssrf001

### Public advisory URL
_No response_

### Reporter credited as
Eve Chen (eve@security.io)

### PR with the fix
_No response_

### CWE
CWE-918 Server-Side Request Forgery (SSRF)

### Severity
HIGH

### CVE tool link
_No response_

**Labels:** security issue, airflow, needs triage
**Milestone:** null
**CVE JSON attachment comment:** no

---

## Mock: gh issue view 334 (drop) --repo airflow-s/airflow-s

**Body:**
### The issue description
Arbitrary HTTP requests from scheduler process via misconfigured logging backend. The S3TaskHandler does not validate the endpoint_url against an allowlist before making requests.

### Short public summary for publish
_No response_

### Affected versions
apache/airflow 2.8.0

### Security mailing list thread
https://lists.apache.org/thread/ssrf002

### Public advisory URL
_No response_

### Reporter credited as
Frank Osei (frank@pentest.com)

### PR with the fix
_No response_

### CWE
CWE-441 Unintended Proxy or Intermediary

### Severity
HIGH

### CVE tool link
_No response_

**Labels:** security issue, airflow, needs triage
**Milestone:** null
**CVE JSON attachment comment:** no
