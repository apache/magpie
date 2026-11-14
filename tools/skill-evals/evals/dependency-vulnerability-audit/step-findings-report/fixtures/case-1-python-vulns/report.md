<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Scope: apache/airflow (Python, pip-audit)
Command: `pip-audit --format json --output /tmp/dep-audit-pip.json`

pip-audit output (JSON):
```json
[
  {
    "name": "cryptography",
    "version": "38.0.3",
    "vulns": [
      {
        "id": "CVE-2023-49083",
        "fix_versions": ["41.0.6"],
        "description": "cryptography is a package designed to expose cryptographic primitives. Calling `load_pem_pkcs7_certificates` or `load_der_pkcs7_certificates` could lead to a NULL-pointer dereference and segfault. Versions 41.0.6 and later are not vulnerable to this issue."
      },
      {
        "id": "CVE-2024-26130",
        "fix_versions": ["42.0.4"],
        "description": "If pkcs12.serialize_key_and_certificates is called with a certificate whose public key does not match the provided private key and an encryption_algorithm with hmac_hash set (such as PrivateFormat.PKCS12.encryption_builder().hmac_hash(...)), an assertion is triggered resulting in a fatal Python crash."
      }
    ]
  },
  {
    "name": "aiohttp",
    "version": "3.8.1",
    "vulns": [
      {
        "id": "CVE-2024-23334",
        "fix_versions": ["3.9.2"],
        "description": "aiohttp is an asynchronous HTTP client/server framework for asyncio. A path traversal vulnerability exists in the static file serving in aiohttp."
      }
    ]
  }
]
```

Severity (mapped from CVSSv3): CVE-2023-49083 → medium, CVE-2024-26130 → high, CVE-2024-23334 → high.
All findings are patchable.
