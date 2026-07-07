<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #113

Title: Improve logging in the pipeline module

Body:
The pipeline module doesn't log enough information when things go wrong.
We should improve logging so that operators can diagnose failures more
easily.

This is generally about making the log output more useful — better
messages, more context, maybe structured fields. We'll know it's good
when operators stop complaining about debugging.

Labels: enhancement
