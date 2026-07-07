<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Primary findings (my review):
- airflow/utils/log.py — code quality: `except Exception: pass` swallows errors.

Adversarial findings (second reviewer):
- airflow/models/dagrun.py — missing index on a frequently-filtered column.
- airflow/api/auth.py — authentication bypass: the token check returns early on a malformed header.
