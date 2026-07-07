<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: scanner-bot@sectools.example
Subject: Automated security scan results for Apache Airflow 2.10.1

Scan completed: 2025-11-14T03:22:11Z
Tool: SecureBot SAST v4.2.1
Target: apache/airflow @ commit a1b2c3d

FINDING-001 [HIGH] CWE-89 SQL Injection
  File: airflow/models/taskinstance.py:L341
  Snippet: cursor.execute("SELECT * FROM task WHERE id=" + task_id)
  Confidence: MEDIUM

FINDING-002 [MEDIUM] CWE-79 Cross-Site Scripting
  File: airflow/www/views.py:L892
  Snippet: return render_template('index.html', name=request.args.get('name'))
  Confidence: LOW

FINDING-003 [LOW] CWE-200 Information Exposure
  File: airflow/utils/log/logging_mixin.py:L55
  Snippet: self.log.debug("Connection string: %s", conn_str)
  Confidence: HIGH

FINDING-004 [HIGH] CWE-94 Code Injection
  File: airflow/operators/python.py:L210
  Snippet: eval(user_code)
  Confidence: LOW

-- End of scan report --
