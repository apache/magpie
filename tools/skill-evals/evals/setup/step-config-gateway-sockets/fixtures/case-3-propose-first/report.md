<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`~/.claude/scripts/container-gateway-hook.sh` exists and
`git check-ignore -q .claude/settings.local.json` exits 0. The project adopted Magpie.
`container-gateway settings --project <repo-root>` printed:

```json
{"proposal": {"run_dir": "/home/me/proj/.apache-magpie-local/run",
  "env": {"CONTAINER_HOST": "unix:///home/me/proj/.apache-magpie-local/run/podman.sock",
          "DOCKER_HOST": "unix:///home/me/proj/.apache-magpie-local/run/docker.sock"},
  "sandbox": {"network": {"allowUnixSockets": ["/home/me/proj/.apache-magpie-local/run/podman.sock",
                                               "/home/me/proj/.apache-magpie-local/run/docker.sock"]}}}}
```

The user has not yet been asked about it in this run.
