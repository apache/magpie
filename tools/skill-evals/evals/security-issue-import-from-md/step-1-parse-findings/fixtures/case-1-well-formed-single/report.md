<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Mock: Read /tmp/ai-security-review-2025-05-01.md

```markdown
# Arbitrary callable invocation via pickle deserialization in XCom backend

## Details

The `CustomXComBackend` implementation in `airflow/models/xcom.py` calls
`pickle.loads()` on values fetched from the XCom storage backend without
any type validation. An attacker with write access to the XCom storage
(e.g., a compromised worker node or a malicious provider plugin) can inject
a crafted pickle payload that invokes arbitrary Python callables during
deserialization on the scheduler or triggerer process.

The vulnerable path is `BaseXCom.deserialize_value()` at line 312 of
`airflow/models/xcom.py`. The deserializer is called in the scheduler
main loop without sandboxing.

## Location

[airflow/models/xcom.py#L312](https://github.com/apache/airflow/blob/main/airflow/models/xcom.py#L312)

## Impact

Arbitrary code execution on the scheduler process with the scheduler's OS
user privileges. A compromised worker or malicious provider can escalate
to full scheduler compromise.

## Reproduction steps

1. Stand up a local Airflow deployment with `AIRFLOW__CORE__XCOM_BACKEND` set
   to a custom backend that writes raw values.
2. From a worker context, inject a crafted pickle payload into XCom storage.
3. Trigger a DAG run that reads the XCom value in the scheduler.
4. Observe arbitrary code execution in the scheduler process.

## Recommended fix

Replace `pickle.loads()` with a type-restricted deserializer (e.g. JSON or
a safe pickle replacement). Enforce a HMAC signature check on XCom values
before deserialization to ensure only scheduler-originated values are
accepted.

---
**Severity:** HIGH
**Status:** Open
**Category:** Insecure Deserialization / RCE
**Repository:** apache/airflow
**Branch:** main
**Date created:** 2025-05-01
```
