<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC: 2.11.0-rc1
release-build.md expected artefacts: apache-airflow-2.11.0-source-release.tar.gz, apache-airflow-2.11.0-bin.tar.gz
KEYS: https://dist.apache.org/repos/dist/release/airflow/KEYS (downloaded to KEYS)

RC inventory from Step 1 (PASS):
  apache-airflow-2.11.0-source-release.tar.gz (FOUND)
  apache-airflow-2.11.0-source-release.tar.gz.asc
  apache-airflow-2.11.0-bin.tar.gz (FOUND)
  apache-airflow-2.11.0-bin.tar.gz.asc

Note: apache-airflow-2.11.0-bin.tar.gz was modified after it was signed.

Tool run:

```bash
uv run --project .apache-magpie/tools/release-verify release-verify signatures \
  --dir staging --expect apache-airflow-2.11.0-source-release.tar.gz --expect apache-airflow-2.11.0-bin.tar.gz \
  --keys KEYS --keys-url https://dist.apache.org/repos/dist/release/airflow/KEYS
```

Tool output:

```json
{
  "step": "signatures",
  "status": "FAIL",
  "results": [
    {
      "file": "apache-airflow-2.11.0-source-release.tar.gz",
      "sig_file": "apache-airflow-2.11.0-source-release.tar.gz.asc",
      "classification": "PASS",
      "fingerprint": "26389C7FF5982465406A1BDFB8E90D83CD36F86A",
      "key_in_keys": true
    },
    {
      "file": "apache-airflow-2.11.0-bin.tar.gz",
      "sig_file": "apache-airflow-2.11.0-bin.tar.gz.asc",
      "classification": "FAIL",
      "fingerprint": null,
      "key_in_keys": false,
      "detail": "BAD signature"
    }
  ],
  "keys_fingerprints": [
    "26389C7FF5982465406A1BDFB8E90D83CD36F86A"
  ],
  "paste_recipe": "curl -s 'https://dist.apache.org/repos/dist/release/airflow/KEYS' | gpg --import\ngpg --verify 'apache-airflow-2.11.0-source-release.tar.gz.asc' 'apache-airflow-2.11.0-source-release.tar.gz'\ngpg --verify 'apache-airflow-2.11.0-bin.tar.gz.asc' 'apache-airflow-2.11.0-bin.tar.gz'"
}
```
