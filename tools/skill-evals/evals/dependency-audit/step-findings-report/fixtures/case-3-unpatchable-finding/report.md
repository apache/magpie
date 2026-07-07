<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Scope: apache/flink (Python tooling, pip-audit)
Command: `pip-audit --format json --output /tmp/dep-audit-pip.json`

pip-audit output (JSON):
```json
[
  {
    "name": "requests",
    "version": "2.20.0",
    "vulns": [
      {
        "id": "CVE-2023-32681",
        "fix_versions": ["2.31.0"],
        "description": "Requests forwards proxy-authorization headers to destination servers when following a redirect to a different host."
      }
    ]
  },
  {
    "name": "legacy-internal-lib",
    "version": "0.3.1",
    "vulns": [
      {
        "id": "PYSEC-2021-9999",
        "fix_versions": [],
        "description": "Deserialization of untrusted data in legacy-internal-lib. No fixed version available from the upstream maintainer."
      }
    ]
  }
]
```

Severity: CVE-2023-32681 → medium (patchable), PYSEC-2021-9999 → high (no fix available).
