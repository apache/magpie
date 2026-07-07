<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Diff against main (3 files changed, +187 -42):

diff --git a/airflow/models/xcom.py b/airflow/models/xcom.py
  [fix for bytes serialization — 4 lines changed]

diff --git a/airflow/models/xcom_arg.py b/airflow/models/xcom_arg.py
  [refactored XComArg to use a new _resolve() helper — 83 lines changed]

diff --git a/airflow/models/base.py b/airflow/models/base.py
  [extracted a shared validate_key() helper used by xcom.py and xcom_arg.py — 100 lines changed]
