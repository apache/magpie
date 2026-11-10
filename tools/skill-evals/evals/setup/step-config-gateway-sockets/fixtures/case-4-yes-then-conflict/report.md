<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The hook exists and git ignores `.claude/settings.local.json`. The block was shown
in Step 3's batch and the user answered "yes, add the gateway sockets".
`container-gateway settings --project <repo-root> --apply <repo-root>/.claude/settings.local.json`
exited 3 and printed:

```json
{"path": "/home/me/proj/.claude/settings.local.json", "status": "written",
 "added_env": {"CONTAINER_HOST": "unix:///home/me/proj/.apache-magpie-local/run/podman.sock"},
 "added_sockets": ["/home/me/proj/.apache-magpie-local/run/podman.sock",
                   "/home/me/proj/.apache-magpie-local/run/docker.sock"],
 "conflicts": {"DOCKER_HOST": {"current": "tcp://127.0.0.1:2375",
                               "proposed": "unix:///home/me/proj/.apache-magpie-local/run/docker.sock"}}}
```
