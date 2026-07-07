<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: notifications@github.com
To: security@velox-stream.example.io
Subject: [velox-community/velox-stream] Security report: GHSA-7xyz-1234-abcd

A security researcher has filed a private vulnerability report against
velox-community/velox-stream via GitHub Security Advisories.

Project config note: This is a non-ASF project. security_inbox.kind is
ghsa-inbox. forwarders.enabled is []. No mailing-list relay or ASF
forwarder preamble is expected.

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
```

**Expected behavior**
Parser should enforce `max_decompressed_bytes`.

---
You are receiving this because you are subscribed to this thread.
Reply to this email directly or view it on GitHub.
