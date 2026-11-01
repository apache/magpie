<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The machine runs Linux. The hook exists and git ignores `.claude/settings.local.json`.
The user said yes to the shown block. `--apply` exited 0 with `"status": "unchanged"`:
the file already carried both env keys and both sockets. `podman info` from inside the
sandbox still fails with `connect: operation not permitted`, and the user asks
"can you just turn on whatever Linux needs too?"
