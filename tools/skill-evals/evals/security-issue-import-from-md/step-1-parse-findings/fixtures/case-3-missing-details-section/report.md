<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Mock: Read /tmp/partial-report-2025-03-20.md

```markdown
# SSRF via worker-supplied hostname in remote logging endpoint

## Location

[airflow/utils/log/s3_task_handler.py#L201](https://github.com/apache/airflow/blob/main/airflow/utils/log/s3_task_handler.py#L201)

## Impact

A compromised worker node can supply a crafted `endpoint_url` value that
causes the scheduler to make HTTP requests to arbitrary internal network
hosts during log read-back.

## Reproduction steps

1. Configure a custom S3 logging endpoint in `airflow.cfg`.
2. From a worker, write a crafted log entry that overrides the endpoint URL.
3. Trigger a log read on the scheduler/webserver.
4. Observe the outbound request to the attacker-controlled host.

## Recommended fix

Validate the `endpoint_url` against an allowlist of known-good S3 endpoints
before making the request.

---
**Severity:** MEDIUM
**Status:** Open
**Category:** Server-Side Request Forgery
**Repository:** apache/airflow
**Branch:** main
**Date created:** 2025-03-20
```
