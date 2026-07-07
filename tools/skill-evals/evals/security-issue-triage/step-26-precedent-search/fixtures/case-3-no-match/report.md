<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Current issue: #241
Title: "SMTP header injection via DAG-configured email recipient"
Code pointer: airflow/utils/email.py — send_email_smtp()
Vulnerability class: header injection via DAG-author-controlled input

### gh search issues — rejection precedents

```json
[
  {
    "number": 155,
    "title": "Email body XSS via task failure message",
    "labels": ["not CVE worthy"],
    "closedAt": "2024-11-02T00:00:00Z",
    "body_excerpt": "Code pointer: airflow/utils/email.py — format_exception(). Closed: DAG author controls email content."
  }
]
```

Match assessment: MODERATE — same file (airflow/utils/email.py) but
different function and different vulnerability class (XSS vs. header
injection). Not the same shape.

### gh search issues — positive precedents

No results.

Budget: 2 of 3 additional calls used.
