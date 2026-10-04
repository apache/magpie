<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC: 2.11.0-rc1
release-build.md expected artefacts: apache-airflow-2.11.0-source-release.tar.gz, apache-airflow-2.11.0-bin.tar.gz
release-build.md digest set: sha512, sha256
No .md5 files in the staging directory.

Tool run:

```bash
uv run --project .apache-magpie/tools/release-verify release-verify checksums \
  --dir staging --expect apache-airflow-2.11.0-source-release.tar.gz --expect apache-airflow-2.11.0-bin.tar.gz \
  --digest sha512 --digest sha256
```

Tool output:

```json
{
  "step": "checksums",
  "status": "PASS",
  "results": [
    {
      "file": "apache-airflow-2.11.0-source-release.tar.gz",
      "digests": [
        {
          "type": "sha512",
          "classification": "PASS"
        },
        {
          "type": "sha256",
          "classification": "PASS"
        }
      ]
    },
    {
      "file": "apache-airflow-2.11.0-bin.tar.gz",
      "digests": [
        {
          "type": "sha512",
          "classification": "PASS"
        },
        {
          "type": "sha256",
          "classification": "PASS"
        }
      ]
    }
  ],
  "deprecated_md5_present": false,
  "paste_recipe": "sha512sum --check apache-airflow-2.11.0-source-release.tar.gz.sha512\nsha256sum --check apache-airflow-2.11.0-source-release.tar.gz.sha256\nsha512sum --check apache-airflow-2.11.0-bin.tar.gz.sha512\nsha256sum --check apache-airflow-2.11.0-bin.tar.gz.sha256"
}
```
