<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Cluster: `(widget-core/serializer, unbounded memory growth when the object
graph is deeply nested, attacker controls the object graph)`

Route: `BY-DESIGN: property-disclaimed`. Occurrences: 3 trackers, all
closed INVALID citing §1.12-D5.

Model claim §1.12-D5 reads: "The parser imposes no recursion-depth limit
and provides no guarantee against stack exhaustion on deeply nested
input. Applies to widget-core/parser."

The serializer is a separate component family in §1.2, with its own row
in the component table. §1.12-D5 does not name it.
