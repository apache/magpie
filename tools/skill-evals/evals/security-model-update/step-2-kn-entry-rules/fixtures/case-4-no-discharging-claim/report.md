<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Cluster: `(widget-core/logger, sensitive values appear in debug-level log
output, local attacker with filesystem read access)`

Route: `BY-DESIGN: property-disclaimed`. Occurrences: 3 trackers over 11
months.

Stated reasons:
- #190 "Debug logging is opt-in and documented as verbose. Not a bug."
- #226 "Same — debug level is not for production."
- #281 "By design; debug output is expected to be verbose."

The model has no §1.11, §1.12, §1.7, or §1.3 claim about logging or
about debug-level output. Nothing in the document mentions the logger.
