<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Harden XCom value handling

Body:
Improves how XCom values are serialised to avoid unexpected behaviour
with large payloads.

Commit messages:
- "Harden XCom serialisation"
- "Prevent use-after-free in XCom backend cleanup"
