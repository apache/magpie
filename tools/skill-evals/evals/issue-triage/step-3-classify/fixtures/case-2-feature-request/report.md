<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: AIRFLOW-99202
Title: Add native support for scheduling DAGs based on upstream DAG completion
Reporter: carol-data-engineer
Status: Open
Component: scheduler
Filed: 2026-04-10

Body:
  Currently, triggering a DAG when another DAG completes requires using TriggerDagRunOperator
  or ExternalTaskSensor. I would like native "dataset-trigger" style scheduling that can
  declaratively say "run DAG B when DAG A's last task succeeds". This would simplify many
  pipeline topologies without requiring explicit sensor tasks.

  I understand Airflow 2.4+ added datasets, but they require producers to emit dataset events.
  I'm asking for a simpler DAG-completion-based trigger at the scheduler level.

Comments:
  (none)
