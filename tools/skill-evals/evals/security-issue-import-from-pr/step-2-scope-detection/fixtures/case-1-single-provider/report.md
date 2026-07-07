<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Mock: gh pr view 65703 --repo apache/airflow --json files

```json
{
  "number": 65703,
  "title": "fix(amazon): Prevent unauthorized access to team-scoped secrets in SM and SSM",
  "state": "MERGED",
  "author": {"login": "justinpakzad"},
  "files": [
    {"path": "providers/amazon/src/airflow/providers/amazon/aws/secrets/systems_manager.py"},
    {"path": "providers/amazon/src/airflow/providers/amazon/aws/secrets/secrets_manager.py"},
    {"path": "providers/amazon/src/airflow/providers/amazon/aws/hooks/base_aws.py"},
    {"path": "providers/amazon/tests/aws/secrets/test_systems_manager.py"},
    {"path": "providers/amazon/tests/aws/secrets/test_secrets_manager.py"}
  ]
}
```
