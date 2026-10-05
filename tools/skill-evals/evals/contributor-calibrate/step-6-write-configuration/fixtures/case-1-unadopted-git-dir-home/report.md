<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The repository `/home/dev/proj` has Magpie installed but not adopted: there is no `.apache-magpie.lock`.

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
  "personal_dir_exists": false,
  "personal_layers": [
    "/home/dev/proj/.git/apache-magpie"
  ]
}
```

The maintainer has reviewed the proposed floors and says: "Looks right, write it."
