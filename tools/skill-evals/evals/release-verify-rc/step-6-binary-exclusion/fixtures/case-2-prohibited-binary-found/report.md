<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md Binary-exclude list (known-accepted): *.class
(no additional prohibited globs beyond the fixed baseline)

RC source artefact: apache-airflow-2.11.0-source-release.tar.gz (unpacked to apache-airflow-2.11.0-source-release/)

Tool run:

```bash
uv run --project .apache-magpie/tools/release-verify release-verify binaries \
  --tree apache-airflow-2.11.0-source-release --accept '*.class'
```

Tool output:

```json
{
  "step": "binary-exclusion",
  "status": "FAIL",
  "prohibited_found": [
    "airflow/vendor/some-lib/some-lib-1.0.jar"
  ],
  "expected_binaries": [],
  "paste_recipe": "find apache-airflow-2.11.0-source-release \\( -type f \\( -name '*.class' -o -name '*.jar' -o -name '*.so' -o -name '*.dylib' -o -name '*.dll' -o -name '*.exe' -o -name '*.pyc' \\) -o -type d -name '__pycache__' \\) -print"
}
```
