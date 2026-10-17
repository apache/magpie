<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The user runs `/magpie-setup config` from the Git tracker repo `~/code/qux-s`.
`project.md` is in scope and `vcs_backend` is `TODO`. `user.md` sets the local `<upstream>` clone to `~/code/qux-site`.

`magpie-vcs -C ~/code/qux-s probe` reports `kind: git`, `svn_hosted: false`, `proposal: null`.

`magpie-vcs -C ~/code/qux-site probe` prints:

```json
{
  "path": "/home/u/code/qux-site",
  "backend": "svn",
  "root": "/home/u/code/qux-site",
  "kind": "svn-working-copy",
  "svn_hosted": true,
  "svn": {
    "url": "https://svn.apache.org/repos/asf/qux/site",
    "repository_root": "https://svn.apache.org/repos/asf",
    "project_url": "https://svn.apache.org/repos/asf/qux/site",
    "line_of_work": null,
    "layout": "other",
    "uuid": "13f79535-47bb-0310-9956-ffa450edef68",
    "source": ".svn/wc.db"
  },
  "proposal": {
    "vcs_backend": "svn",
    "svn_url": "https://svn.apache.org/repos/asf/qux/site",
    "svn_repository_root": "https://svn.apache.org/repos/asf",
    "upstream_default_branch": null
  },
  "notes": [
    "https://svn.apache.org/repos/asf/qux/site is not under a trunk/branches/tags layout: the svn backend's new-branch and name-based switch refuse there"
  ]
}
```
