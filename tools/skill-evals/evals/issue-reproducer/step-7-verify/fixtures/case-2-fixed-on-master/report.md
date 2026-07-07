<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-99606
Title: Pool slots not released after task timeout
Reporter claimed failure: pool slot held forever after execution_timeout exceeded

Adapted reproducer run output:
  Command: python /tmp/reproduce_AIRFLOW-99606.py
  Exit code: 0
  stdout: |
    Pool slot acquired: test_pool (used=1, open=9)
    Task timed out at 2s — triggering timeout handler
    Pool slot released: test_pool (used=0, open=10)
    All pool slots correctly returned.
  stderr: (empty)
  Wall-clock: 3.1s
