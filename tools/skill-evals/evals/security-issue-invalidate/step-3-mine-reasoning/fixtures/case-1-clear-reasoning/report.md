<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Tracker comments (airflow-s/airflow-s#312)

**Comment #1001 — @triager-a:**
> After review: the log endpoint requires session auth; the request must already carry a valid session cookie. This is not an unauthenticated read. The reporter's PoC curl command omits the `-b session=...` flag that the endpoint requires. Without a valid session the endpoint returns 403, not the log content.
URL: https://github.com/airflow-s/airflow-s/issues/312#issuecomment-1001

**Comment #1002 — @triager-b:**
> Confirmed: I tried the PoC against a fresh 2.8.1 install. The endpoint is gated by `@login_required` in `airflow/www/views.py` line 1821. Unauthenticated requests receive a 302 redirect to /login, never log content.
URL: https://github.com/airflow-s/airflow-s/issues/312#issuecomment-1002

**Comment #1003 — @triager-a:**
> The security model (https://airflow.apache.org/docs/apache-airflow/stable/security/security-model.html) explicitly states that authenticated UI users are trusted to read task logs for DAGs they have access to. Reading your own task logs is not a vulnerability — it is documented behaviour.
URL: https://github.com/airflow-s/airflow-s/issues/312#issuecomment-1003
