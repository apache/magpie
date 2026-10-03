<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker #350 — CVE-2026-39870, "Sensitive connection fields exposed in the REST API"
Change confirmed by the operator this run: *Public advisory URL* body
field populated with the archived users-list advisory URL, and the
tracker moved to `announced` (close-out).

Step 5a result: regenerated and attached. The regen adds a
`references[]` entry tagged `vendor-advisory` with that URL.
Generator state: `PUBLIC` (`public`).

CVE record state in the CVE tool (Vulnogram): `PUBLIC` (`public`) —
the record was published earlier; the published record does not yet
carry the `vendor-advisory` reference.

Regenerated JSON excerpt:

```json
{
  "containers": {
    "cna": {
      "title": "Sensitive connection fields exposed in the REST API",
      "descriptions": [{"lang": "en", "value": "An authenticated user with read access to connections could retrieve connection passwords in clear text through the connections REST API endpoint. Users are recommended to upgrade to apache-airflow 2.10.4, which fixes the issue."}],
      "problemTypes": [{"descriptions": [{"lang": "en", "type": "CWE", "cweId": "CWE-200", "description": "CWE-200: Exposure of Sensitive Information to an Unauthorized Actor"}]}],
      "affected": [{"vendor": "Apache Software Foundation", "product": "Apache Airflow", "versions": [{"version": "0", "versionType": "semver", "lessThan": "2.10.4", "status": "affected"}]}],
      "credits": [{"lang": "en", "value": "Jan Lewandowski", "type": "finder"}],
      "references": [
        {"url": "https://github.com/apache/airflow/pull/48812", "tags": ["patch"]},
        {"url": "https://lists.apache.org/thread/q8k2m4n6p0r1s3t5v7x9z1b3d5f7h9j1", "tags": ["vendor-advisory"]}
      ]
    }
  },
  "CNA_private": {"state": "PUBLIC"}
}
```

Provenance: the reporter wrote to `security@` under his real name and
asked to be credited. Not a follow-up to any earlier CVE.

Adapter session probe (`vulnogram-api-check`): `valid`.
`vulnogram-api-record-update`: exit 0 at 2026-10-03T15:40:51Z.
