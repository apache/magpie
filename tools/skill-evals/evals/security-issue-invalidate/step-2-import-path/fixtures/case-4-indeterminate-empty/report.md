<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Mock: gh issue view 199 --repo airflow-s/airflow-s

```json
{
  "number": 199,
  "title": "Potential timing side-channel in password comparison",
  "state": "OPEN",
  "labels": [{"name": "security issue"}, {"name": "needs triage"}, {"name": "airflow"}],
  "body": "**Security mailing list thread:** _No response_\n\n**Affected versions:** 2.6.0\n\n**Reporter credited as:** _No response_\n\n**CVE tool link:** _No response_\n\n**PR with the fix:** _No response_",
  "comments": [
    {
      "author": {"login": "triager-c"},
      "body": "Python's == on str objects is not constant-time, but the password field is already hashed via bcrypt before any comparison. No meaningful side channel exists at the application level.",
      "url": "https://github.com/airflow-s/airflow-s/issues/199#issuecomment-4001"
    }
  ]
}
```
