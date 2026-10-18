<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The user runs `/magpie-setup config` in `~/code/bar`, a Git clone of `acme/bar` on GitHub.
`project.md` is in scope and `vcs_backend` is `TODO`. `user.md` names no separate `<upstream>` clone.

`magpie-vcs -C ~/code/bar probe` prints:

```json
{
  "path": "/home/u/code/bar",
  "backend": "git",
  "root": "/home/u/code/bar",
  "kind": "git",
  "svn_hosted": false,
  "svn": null,
  "proposal": null,
  "notes": []
}
```
