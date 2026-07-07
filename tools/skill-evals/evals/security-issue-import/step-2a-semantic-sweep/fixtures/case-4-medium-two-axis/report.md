<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: dave@bugbounty.example
Subject: Apache Airflow task callback URL allows SSRF to internal hosts

I found that when a task finishes, Airflow sends a POST request to the
callback URL configured in the task's on_success_callback handler.
By registering a DAG with a crafted callback URL (e.g. http://10.0.0.1/
pointing at an internal host), an authenticated DAG author can trigger outbound
requests to internal network endpoints.

This affects the task execution path, not the connection-test UI. Tested on
Airflow 2.10.0. The relevant code is in airflow/callbacks/callback_requests.py.
