<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #87

Title: Show a clear message when a search returns no results

Body:
When a search finds nothing, the tool currently prints an empty line, which
leaves users unsure whether the search actually ran. It should instead print a
short, explicit message telling the user that nothing matched their query.

Definition of done:
- An empty result set prints a clear "No results found." message.
- A non-empty result set is displayed exactly as it is today.
- A test covers both the empty and non-empty cases.

Estimated effort: ~1 hour.

Labels: enhancement, good-first-contribution
