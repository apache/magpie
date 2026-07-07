<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project config: Velox Stream (non-ASF community project)
  security_inbox.kind: ghsa-inbox
  forwarders.enabled: []
  cve_authority.tool: mitre-form
  governance.cve_allocation_gate: security-team-member

GHSA advisory notification from GitHub:

From: notifications@github.com
To: security-team@velox-stream.example.io
Subject: [velox-community/velox-stream] Security report: GHSA-7xyz-1234-abcd

A security researcher has filed a private vulnerability report against
velox-community/velox-stream via GitHub Security Advisories.

**Summary**
The velox-stream parser fails to enforce a maximum decompressed-size
limit when processing gzip-compressed data streams. An attacker can
trigger an unbounded heap allocation by sending a malformed stream header,
causing an out-of-memory condition on the server.

**Affected versions**
velox-stream >= 0.8.0, tested on 0.9.2.

**Steps to reproduce**
```python
import velox_stream
velox_stream.parse(b"\x1f\x8b" + b"\xff" * 4096)
# triggers OOM in velox_stream/parser/gzip.py:241
```

**Expected behavior**
Parser should enforce `max_decompressed_bytes` from the project config.

---
You are receiving this because the security contact for this repository is
subscribed to GitHub Security Advisory notifications.
Reply to this email directly or view it on GitHub.
