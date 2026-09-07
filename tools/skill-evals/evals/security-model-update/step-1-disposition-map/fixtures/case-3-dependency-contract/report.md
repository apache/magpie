<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Cluster: `(widget-core/tls-wrapper, certificate hostname mismatch
accepted, network attacker)`

Occurrences: 3 trackers, all closed INVALID.

Stated reasons:
- #244 "Root cause is in libtls 3.1 — its verify callback returns
  success on a mismatch. We call it per its documented contract.
  Reported upstream."
- #266 "Same libtls bug. Upstream's."
- #291 "libtls again; our usage is conformant."
