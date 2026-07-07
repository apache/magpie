<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Merge scenario

**Keep:** airflow-s/airflow-s#312 (Alice Nguyen, thread: Gmail 18f3a2b9c1d4e507, CVE: CVE-2025-44812)
**Drop:** airflow-s/airflow-s#328 (Carlos Mendez, thread: https://lists.apache.org/thread/xyz987abc)
**Merge date:** 2025-05-16
**Author handle:** triager-a

**Merge analysis:** Same root-cause bug — `pickle.loads()` in `BaseXCom.deserialize_value()` at line 312 of `airflow/models/xcom.py`. Alice reported it via a compromised-worker injection path; Carlos described a database-write path. Same vulnerable function, same fix.

Build the rollup entry for the **dropped** tracker (#328).
