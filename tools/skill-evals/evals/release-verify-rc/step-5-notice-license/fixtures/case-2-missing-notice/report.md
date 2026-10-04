<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC source artefact: apache-airflow-2.11.0-source-release.tar.gz (unpacked to apache-airflow-2.11.0-source-release/)

The unpacked RC artefact has a LICENSE at its root but no NOTICE.
No previous release was fetched for this run.

Tool run:

```bash
uv run --project .apache-magpie/tools/release-verify release-verify notice-license \
  --tree apache-airflow-2.11.0-source-release
```

Tool output:

```json
{
  "step": "notice-license",
  "status": "FAIL",
  "notice_present": false,
  "license_present": true,
  "notice_diff_lines": null,
  "notice_diff": null,
  "license_diff_lines": null,
  "license_diff": null,
  "previous": null,
  "detail": "NOTICE absent from the root of the current RC artefact (apache-airflow-2.11.0-source-release); this RC is defective whatever any previous release contains. Diff line counts are null because there is no file to diff."
}
```
