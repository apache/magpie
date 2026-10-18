<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The user runs `/magpie-setup config` from the Git tracker repo `~/code/quux-s`.
`project.md` is in scope and `vcs_backend` is `TODO`. `user.md` sets the local `<upstream>` clone to `~/code/quux`.

`magpie-vcs -C ~/code/quux probe` prints:

```json
{
  "path": "/home/u/code/quux",
  "backend": "svn",
  "root": "/home/u/code/quux",
  "kind": "svn-working-copy",
  "svn_hosted": true,
  "svn": null,
  "proposal": {
    "vcs_backend": "svn",
    "svn_url": null,
    "svn_repository_root": null,
    "upstream_default_branch": null
  },
  "notes": [
    "svn 1.9+ is not installed; read .svn/wc.db instead",
    "could not read /home/u/code/quux/.svn/wc.db: unable to open database file"
  ]
}
```
