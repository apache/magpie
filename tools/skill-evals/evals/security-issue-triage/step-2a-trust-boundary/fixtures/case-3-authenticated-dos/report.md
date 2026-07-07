<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Reporter claims: An authenticated Airflow UI user can trigger a DAG run
with a very large conf JSON payload (e.g. 50 MB). The scheduler parses this
payload synchronously on each heartbeat, causing CPU saturation and making
the scheduler unresponsive to all other DAG runs for 30-60 seconds.

Attacker: Authenticated Airflow UI user (has DAG trigger permissions)
Component: Airflow scheduler, DAG run conf parsing
Effect: temporary denial of service against the scheduler, affecting all
  concurrent DAG runs
