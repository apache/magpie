<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: researcher@independent.example
Subject: Airflow REST API exposes sensitive connection passwords in plaintext

Hi Airflow security team,

I discovered that the GET /api/v1/connections/{conn_id} endpoint returns the
connection password in the response JSON under the "password" field, without
any masking. An authenticated user with "read connection" permission can
retrieve passwords for all connections they have access to.

Steps to reproduce:
1. Create a connection with a non-empty password via the Airflow UI.
2. Authenticate with any account that has "read connection" permission.
3. GET /api/v1/connections/<conn_id> — "password" is present in the response.

This affects Airflow 2.9.x and 2.10.x. The relevant code is in
airflow/api_fastapi/core_api/routes/connections.py.

Regards,
Alex Researcher
