<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC source artefact: apache-airflow-2.11.0-source-release.tar.gz (unpacked to apache-airflow-2.11.0-source-release/)

Previous release found at:
  https://dist.apache.org/repos/dist/release/airflow/2.10.0/apache-airflow-2.10.0-source-release.tar.gz
  (its NOTICE and LICENSE fetched into previous/)

Tool run:

```bash
uv run --project .apache-magpie/tools/release-verify release-verify notice-license \
  --tree apache-airflow-2.11.0-source-release --previous previous
```

Tool output:

```json
{
  "step": "notice-license",
  "status": "REVIEW",
  "notice_present": true,
  "license_present": true,
  "notice_diff_lines": 2,
  "notice_diff": "--- previous/NOTICE\n+++ rc/NOTICE\n@@ -1,4 +1,4 @@\n-Apache Airflow 2.10.0\n+Apache Airflow 2.11.0\n Copyright 2016-2026 The Apache Software Foundation\n \n This product includes software developed at\n",
  "license_diff_lines": 0,
  "license_diff": "",
  "previous": "previous"
}
```
