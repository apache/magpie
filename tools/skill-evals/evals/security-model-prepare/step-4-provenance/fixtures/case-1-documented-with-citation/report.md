<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Draft claim: "The decoder imposes a 4 GiB limit on the declared archive
length and rejects anything above it."

Evidence: `docs/limits.md`, committed by the project, states "Archives
declaring a length above 4 GiB are rejected at header parse; this limit
is not configurable." The draft cites that file and line.
