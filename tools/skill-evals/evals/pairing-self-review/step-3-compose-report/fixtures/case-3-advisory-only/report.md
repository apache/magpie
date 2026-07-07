<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base cc1122)
Files changed: 2 (1 added, 1 modified)
Diff size: 35 additions, 0 deletions

Classified findings:
  correctness: no findings
  security: no findings
  conventions:
    - advisory | airflow/utils/string_utils.py:1
      summary: New file missing SPDX license header
      evidence: "+def truncate(value: str, max_len: int = 100) -> str:"
