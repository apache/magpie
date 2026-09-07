<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Cluster: `(widget-core/parser, use-after-free reported by three different
fuzzing harnesses, attacker controls the input document)`

Occurrences: 3 trackers over 5 months, all closed INVALID.

Stated reasons:
- #250 "Reporter never sent a reproducer. Closing."
- #271 "No proof-of-concept attached, and we couldn't reproduce from
  the description. Closing."
- #299 "Scanner output only; reachability not demonstrated. Closing."

Proposed match conditions: "fuzzer-reported use-after-free in the parser
where no reproducer is attached".

The model has no claim about parser memory-safety in either direction.
