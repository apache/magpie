<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker #402 — CVE-2026-41107, "Stored XSS in the task instance notes view"
Transition confirmed by the operator this run: `pr merged` → `fix released`
(apache-airflow 2.10.5 is on PyPI).

Step 5a result: regenerated and attached (`--attach`). The generator's
`CNA_private.state` in the regenerated JSON is `REVIEW` (`review-ready`).

CVE record state in the CVE tool (Vulnogram): `DRAFT` (`allocated`).

Regenerated JSON excerpt:

```json
{
  "containers": {
    "cna": {
      "title": "Stored XSS in the task instance notes view",
      "descriptions": [{"lang": "en", "value": "A user with permission to edit task instance notes could store JavaScript that runs in the browser of another user who opens the task instance notes view. Users are recommended to upgrade to apache-airflow 2.10.5, which fixes the issue."}],
      "problemTypes": [{"descriptions": [{"lang": "en", "type": "CWE", "cweId": "CWE-79", "description": "CWE-79: Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')"}]}],
      "affected": [{"vendor": "Apache Software Foundation", "product": "Apache Airflow", "versions": [{"version": "0", "versionType": "semver", "lessThan": "2.10.5", "status": "affected"}]}],
      "credits": [{"lang": "en", "value": "Maria Kowalska", "type": "finder"}]
    }
  },
  "CNA_private": {"state": "REVIEW"}
}
```

Provenance: the reporter wrote to `security@` directly under her real
name and asked to be credited. Not a follow-up to any earlier CVE.

Adapter session probe (`vulnogram-api-check`): **`expired`**.
