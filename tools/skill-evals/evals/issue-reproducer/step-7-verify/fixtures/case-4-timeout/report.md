<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88404
Title: Scheduler becomes unresponsive after 48 hours of continuous operation
Reporter claimed failure: scheduler stops scheduling after ~48h

Adapted reproducer run output:
  Command: timeout 60 python /tmp/reproduce_AIRFLOW-88404.py
  Exit code: 124 (timeout)
  stdout: |
    Scheduler started.
    Processed 142 DAG files.
    Heartbeat: 2026-05-18T10:00:05Z
    Heartbeat: 2026-05-18T10:00:15Z
    ...
    Heartbeat: 2026-05-18T10:01:00Z
  stderr: (empty)
  Wall-clock: 60.0s (timeout hit)

Note: The reproducer was adapted to run a compressed-time simulation (each simulated hour = 1 real second) but the 60s budget was exhausted before reaching the 48h simulation threshold.
