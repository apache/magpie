<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker #391 — CVE-2026-41020
Change confirmed by the operator this run: field correction to *CWE*
(triggers a regen). Tracker label stays `cve allocated`.

Step 5a result: regenerated and attached. Generator state: `DRAFT` (`allocated`).

CVE record state in the CVE tool (Vulnogram): `DRAFT` (`allocated`).

*Security mailing list thread* body field: points at a thread where a
partner forwarded findings from their internal **Mythos** scan run; the
individual analyst who ran it, Piotr Zielinski, is named in that
forward. The finding never went through `security@` from the analyst,
and no public report exists anywhere.

`<project-config>/scanner-products.md` declares `Mythos` as a private
scanner product with **no** public credit name.

Regenerated JSON excerpt:

```json
{
  "containers": {
    "cna": {
      "title": "SQL injection in the variable search endpoint",
      "descriptions": [{"lang": "en", "value": "An authenticated user with read access to variables could run arbitrary SQL against the metadata database by sending a crafted search query to the variable search endpoint. Users are recommended to upgrade to apache-airflow 2.10.6, which fixes the issue."}],
      "problemTypes": [{"descriptions": [{"lang": "en", "type": "CWE", "cweId": "CWE-89", "description": "CWE-89: Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')"}]}],
      "affected": [{"vendor": "Apache Software Foundation", "product": "Apache Airflow", "versions": [{"version": "0", "versionType": "semver", "lessThan": "2.10.6", "status": "affected"}]}],
      "credits": [{"lang": "en", "value": "Piotr Zielinski", "type": "finder"}]
    }
  },
  "CNA_private": {"state": "DRAFT"}
}
```

Not a follow-up to any earlier CVE.

Adapter session probe (`vulnogram-api-check`): `valid`.
