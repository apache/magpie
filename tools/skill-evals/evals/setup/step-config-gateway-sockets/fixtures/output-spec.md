<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "run": true | false,
  "skip_reason": "no-gateway" | "not-ignored" | null,
  "propose": true | false,
  "apply_now": true | false,
  "overwrite_env": false,
  "add_daemon_socket": false,
  "write_allow_all_unix_sockets": false,
  "outcome": "written" | "unchanged" | "conflict" | "error" | null
}
```

- `run` — `true` when Step 3h applies: the container-gateway hook is installed and git ignores `.claude/settings.local.json`. `false` otherwise.
- `skip_reason` — why the step did not run: `no-gateway` when the hook is not installed, `not-ignored` when git would commit the settings file. `null` when `run` is `true`.
- `propose` — `true` when the block is shown to the user as an item in Step 3's batch. `false` when `run` is `false`.
- `apply_now` — `true` only when the user has said yes to the shown block in this run, so the `--apply` command runs now. `false` when the user has not answered, declined, or `run` is `false`.
- `overwrite_env` — `true` if the run would replace an `env` value the file already holds. Always `false` under the step.
- `add_daemon_socket` — `true` if the run would add a real container daemon socket (for example `/var/run/docker.sock`) to `allowUnixSockets`. Always `false` under the step.
- `write_allow_all_unix_sockets` — `true` if the run would set `sandbox.network.allowAllUnixSockets`. Always `false` under the step.
- `outcome` — what the `--apply` result reported, when one is given: `written`, `unchanged` (`status: unchanged`), `conflict` (exit `3`), `error` (exit `2`). `null` when nothing was applied.
