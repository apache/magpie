<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Cluster: `(widget-core/decoder, integer overflow on the length field,
attacker controls the archive, no privileged capability required)`

Route: `BY-DESIGN: property-disclaimed`. Occurrences: 4 trackers over 14
months, each citing §1.12-D2.

Model claim §1.12-D2 reads: "The decoder provides no memory-safety
guarantee for archives declaring a length above 4 GiB. Applies to
widget-core/decoder and widget-core/streaming-decoder."

Proposed match conditions: component `widget-core/decoder`; sink
`header_length_parse`; symptom integer overflow leading to an
undersized allocation; precondition that the declared length exceeds
4 GiB.
