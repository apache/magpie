<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

fix(models): address Apache Verum findings in connection.py

This security fix removes dead code that could expose credentials
via log output. The unreachable block after the early return was
flagged as a potential vulnerability by Apache Verum (DEAD-001).
Removing it prevents accidental log leakage.

Generated-by: Claude (Opus 4.7)
