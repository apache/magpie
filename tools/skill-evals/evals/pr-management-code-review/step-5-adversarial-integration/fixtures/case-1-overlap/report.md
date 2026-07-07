<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Primary findings (my review):
- airflow/core/scheduler.py — N+1 query: a User lookup runs once per dag in a loop.
- airflow/api/client.py — breaking change: public create_dag() drops the `schedule` parameter with no deprecation.

Adversarial findings (second reviewer):
- airflow/api/client.py — removing the public `schedule` arg breaks callers; needs a deprecation cycle.
- airflow/core/executors/base.py — race condition: shutdown() can run while a task is still being enqueued.
