<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The repository `/home/dev/proj` has Magpie installed but not adopted: there is no `.apache-magpie.lock`. It does have a committed `.apache-magpie-overrides/` directory holding `project.md`.

Output of `python3 -m setup_preflight.layers`:

```json
{
  "adopted": false,
  "config_layers": [
    "/home/dev/proj/.git/apache-magpie",
    "/home/dev/proj/.apache-magpie-overrides"
  ],
  "legacy_local_dir": null,
  "main_worktree": null,
  "personal_dir": "/home/dev/proj/.git/apache-magpie",
  "personal_dir_exists": true,
  "personal_layers": [
    "/home/dev/proj/.git/apache-magpie"
  ]
}
```

The maintainer says: "These numbers are good for the whole team. Put them in `.apache-magpie-overrides/` so everyone gets them."
