<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker #377 — CVE-2026-40991
Change confirmed by the operator this run: field correction to
*Affected versions* (triggers a regen). Tracker label stays `cve allocated`.

Step 5a result: regenerated and attached. Generator state: `DRAFT`
(`allocated`; no fix released yet).

CVE record state in the CVE tool (Vulnogram): `DRAFT` (`allocated`).

Regenerated JSON excerpt (the generator copied the GitHub issue title verbatim):

```json
{
  "containers": {
    "cna": {
      "title": "[GHSA-7f3q-9xw2-hm4c] Path traversal in the DAG file processor",
      "descriptions": [{"lang": "en", "value": "A DAG author could make the DAG file processor read files outside the DAGs folder when a crafted relative path is placed in the bundle configuration. Users are recommended to upgrade to apache-airflow 2.10.6, which fixes the issue."}],
      "problemTypes": [{"descriptions": [{"lang": "en", "type": "CWE", "cweId": "CWE-22", "description": "CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')"}]}],
      "affected": [{"vendor": "Apache Software Foundation", "product": "Apache Airflow", "versions": [{"version": "0", "versionType": "semver", "lessThan": "2.10.6", "status": "affected"}]}],
      "credits": [{"lang": "en", "value": "Tomasz Nowak", "type": "finder"}]
    }
  },
  "CNA_private": {"state": "DRAFT"}
}
```

Provenance: GitHub Security Advisory submission, reporter credited
publicly on the GHSA. Not a follow-up to any earlier CVE.

Adapter session probe (`vulnogram-api-check`): `valid`.
