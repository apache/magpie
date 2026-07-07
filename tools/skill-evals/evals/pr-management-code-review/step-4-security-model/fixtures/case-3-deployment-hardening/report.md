<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Default webserver bind address

Diff modifies: airflow/config_templates/default_airflow.cfg

--- a/airflow/config_templates/default_airflow.cfg
+++ b/airflow/config_templates/default_airflow.cfg
@@
 [webserver]
-web_server_host = 127.0.0.1
+web_server_host = 0.0.0.0

The webserver now binds on all interfaces by default; TLS termination is
left to the deploying operator.
