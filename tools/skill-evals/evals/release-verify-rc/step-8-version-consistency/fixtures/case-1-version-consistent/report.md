<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC tag: 2.11.0-rc1

version_manifest_files (from release-management-config.md): setup.cfg, airflow/__init__.py

Tool run:

```bash
uv run --project .apache-magpie/tools/release-verify release-verify version \
  --tree apache-airflow-2.11.0-source-release --rc-tag 2.11.0-rc1 --manifest setup.cfg --manifest airflow/__init__.py
```

Tool output:

```json
{
  "step": "version-consistency",
  "status": "PASS",
  "expected_version": "2.11.0",
  "results": [
    {
      "file": "setup.cfg",
      "extracted": "2.11.0",
      "match": true
    },
    {
      "file": "airflow/__init__.py",
      "extracted": "2.11.0",
      "match": true
    }
  ]
}
```
