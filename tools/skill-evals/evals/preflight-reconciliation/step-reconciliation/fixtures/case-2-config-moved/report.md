<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This skill's frontmatter `name:` is `magpie-pr-management-code-review`.

Its pre-flight ran the checker and it answered:

```json
{
  "verdict": "action",
  "findings": [
    {
      "scope": "skill",
      "code": "config-missing",
      "section": "step-7",
      "facts": {
        "files": [
          "reviewer-routing.md"
        ]
      }
    },
    {
      "scope": "skill",
      "code": "fingerprint-moved",
      "section": "step-4",
      "facts": {
        "skill": "magpie-pr-management-code-review",
        "stamped": "sha256:1a0b77dd93e40c12",
        "current": "sha256:7c2a91ff408b6e33",
        "cause": "requires_config",
        "in_both_stores": false
      }
    }
  ]
}
```
