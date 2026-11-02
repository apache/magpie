<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## step-14 — the container gateway's hooks are not loaded

**`container-gateway-hooks-not-loaded`** — this project points the container
CLIs at its gateway (`sockets`), the gateway is not running, and no settings
file Claude Code loads registers the `SessionStart` hook running
`container-gateway-hook.sh start`. Every `docker` / `podman` command here will
fail with a missing socket until that is fixed.

Tell the user in two or three lines, naming the case that applies:

- **`registered_in_unloaded_file` is a path** — the hooks are in
  `~/.claude/settings.local.json`. Claude Code does not load that file (only a
  project's `.claude/settings.local.json`), so they never run.
- **`user_settings_readable` is `false`** — `~/.claude/settings.json` cannot be
  read from inside the sandbox, so the hooks may be registered there. Say so,
  and that a gateway started earlier in this session and since exited would
  also look like this.
- **`hook_is_symlink` is a path** — the hooks are registered through the
  managed-settings dispatcher, but `~/.claude/scripts/container-gateway-hook.sh`
  is a symlink (a sync-repo layout), which the dispatcher refuses. The remedy
  is a plain copy: `rm` the link, then copy the framework's
  `tools/agent-isolation/container-gateway-hook.sh` there (a `cp` onto the link
  would write through it into the sync repo). No `sudo` is needed for this one.
- **otherwise** — the hooks are not registered in any loaded file.

The remedy is the managed-settings drop-in from the setup guide's
[Fixing your other machines](../../../../../../docs/setup/secure-agent-setup.md#container-gateway):
`managed-settings.d/50-magpie-container-gateway.json` under
`/Library/Application Support/ClaudeCode/` (macOS) or `/etc/claude-code/`
(Linux), running the root-owned dispatcher `<managed-settings dir>/magpie/container-gateway-dispatch`,
then a new session. Where an MDM or server-managed Claude Code policy outranks
file-based managed settings, the drop-in is ignored; say so if the user mentions one.
The dispatcher refuses a hook that anyone but its owner can write, so the
remedy also includes `chmod go-w ~ ~/.claude ~/.claude/scripts
~/.claude/scripts/container-gateway-hook.sh`. Installing the dispatcher and
drop-in needs `sudo`: print the guide's commands
for the user to run as `! <command>`, never run it yourself, and point at
`setup-isolated-setup-verify` (check 12a) to confirm afterwards.

Do not block on it: report it once and carry on with the work the user asked
for, unless that work needs containers.
