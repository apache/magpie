<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-88101
Comment thread:

  comment-1 by potiuk (MEMBER), 2023-06-01:
    "Reproduced this on 2.6.0 main — RecursionError confirmed with 1001 DAGs."

  comment-2 by jedcunningham (MEMBER), 2024-02-14:
    "I tried on 2.8.0 and it did NOT reproduce — may have been fixed by the dag processor refactor."

  comment-3 by reporter (NONE), 2026-04-02:
    "Still happening on 2.9.0!"
