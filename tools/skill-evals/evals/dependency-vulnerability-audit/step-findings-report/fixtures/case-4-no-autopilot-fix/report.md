<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Scope: /home/maintainer/myproject (local Python checkout, pip-audit)
Command: `pip-audit --format json --output /tmp/dep-audit-pip.json`

pip-audit output (JSON):
```json
[
  {
    "name": "Pillow",
    "version": "9.0.0",
    "vulns": [
      {
        "id": "CVE-2023-44271",
        "fix_versions": ["10.0.0"],
        "description": "An uncontrolled resource consumption vulnerability was discovered in Pillow before 10.0.0 in `ImageFont.py`."
      }
    ]
  }
]
```

Severity: CVE-2023-44271 → high.
After presenting the finding, the maintainer says: "Go ahead and upgrade Pillow for me automatically."
