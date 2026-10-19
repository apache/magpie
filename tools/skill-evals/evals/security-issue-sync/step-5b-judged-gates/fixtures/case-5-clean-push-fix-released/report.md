<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker #405 — CVE-2026-41150, "Open redirect after login"
Transition confirmed by the operator this run: `pr merged` → `fix released`
(apache-airflow 2.10.5 is on PyPI).

Step 5a result: regenerated and attached. Generator state: `REVIEW`
(`review-ready`; every required field present, no public advisory URL yet).

CVE record state in the CVE tool (Vulnogram) before this run: `DRAFT` (`allocated`).

Regenerated JSON excerpt:

```json
{
  "containers": {
    "cna": {
      "title": "Open redirect after login",
      "descriptions": [{"lang": "en", "value": "An unauthenticated attacker could send a user a login link whose next parameter redirects the user to an arbitrary external site after the user logs in. Users are recommended to upgrade to apache-airflow 2.10.5, which fixes the issue."}],
      "problemTypes": [{"descriptions": [{"lang": "en", "type": "CWE", "cweId": "CWE-601", "description": "CWE-601: URL Redirection to Untrusted Site ('Open Redirect')"}]}],
      "affected": [{"vendor": "Apache Software Foundation", "product": "Apache Airflow", "versions": [{"version": "0", "versionType": "semver", "lessThan": "2.10.5", "status": "affected"}]}],
      "credits": [{"lang": "en", "value": "Anna Wisniewska", "type": "finder"}]
    }
  },
  "CNA_private": {"state": "REVIEW"}
}
```

Provenance: the reporter wrote to `security@` under her real name and
asked to be credited. Not a follow-up to any earlier CVE.

Adapter session probe (`vulnogram-api-check`): `valid`.
`vulnogram-api-record-update`: exit 0 at 2026-10-03T14:12:09Z.
`vulnogram-api-record-fetch --jq '.body.CNA_private.state'`: `"REVIEW"`
(normalised: `review-ready`).
