<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Snapshot drift check

cat .apache-magpie.lock:
  method: git-branch
  url: https://github.com/apache/magpie.git
  ref: v0.9.1

cat .apache-magpie.local.lock:
  method: git-branch
  url: https://github.com/apache/magpie.git
  ref: v0.9.1

Result: lock files match — no drift.

---

## Check 1 — Project .claude/settings.json

cat .claude/settings.json:
```json
{
  "sandbox": {
    "enabled": true,
    "network": {"allowedDomains": ["github.com", "api.github.com", "pypi.org"]},
    "filesystem": {"denyRead": ["~/"], "allowRead": ["."], "allowWrite": ["."]}
  },
  "permissions": {
    "deny": ["Read(~/.aws/**)", "Bash(curl *)"],
    "ask": ["Bash(gh pr create *)"]
  }
}
```

---

## Check 12 — Container gateway wired

Platform: Linux. uname -s → Linux; id -u → 1000
command -v podman → /usr/bin/podman

~/.claude/settings.local.json hooks:
  SessionStart → /home/alice/.claude/scripts/container-gateway-hook.sh start
  SessionEnd → /home/alice/.claude/scripts/container-gateway-hook.sh stop
  PreToolUse (matcher Bash) → /home/alice/.claude/scripts/container-gateway-hook.sh ensure
test -x /home/alice/.claude/scripts/container-gateway-hook.sh → exists, executable

cat /home/alice/tracker/.claude/settings.local.json:
```json
{
  "env": {
    "CONTAINER_HOST": "unix:///home/alice/tracker/.apache-magpie-local/run/podman.sock",
    "DOCKER_HOST": "unix:///home/alice/tracker/.apache-magpie-local/run/docker.sock"
  },
  "sandbox": {
    "network": {
      "allowAllUnixSockets": true,
      "allowUnixSockets": [
        "/home/alice/tracker/.apache-magpie-local/run/podman.sock",
        "/home/alice/tracker/.apache-magpie-local/run/docker.sock"
      ]
    }
  }
}
```

sandbox.filesystem.denyRead in every scope:
  .claude/settings.json → ["~/"]
  .claude/settings.local.json → (none)
  ~/.claude/settings.json → ["~/"]

Host socket paths (test -e on the host):
  /run/docker.sock → exists
  /var/run/docker.sock → exists
  /run/docker-cli.sock → absent
  /run/podman → absent
  /run/user/1000 → exists
  /run/dbus → exists
  /tmp/.X11-unix → exists
  /run/WSL → absent
  /mnt/wslg → absent
