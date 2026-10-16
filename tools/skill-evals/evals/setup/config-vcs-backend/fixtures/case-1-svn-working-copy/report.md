<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The user runs `/magpie-setup config` from the Git tracker repo `~/code/foo-s`.
`project.md` is in scope and was just copied from the template, so `vcs_backend` is `TODO`.
`user.md` sets the local `<upstream>` clone to `~/code/foo`.

`magpie-vcs -C ~/code/foo-s probe` reports `kind: git`, `svn_hosted: false`, `proposal: null`.

`magpie-vcs -C ~/code/foo probe` prints:

```json
{
  "path": "/home/u/code/foo",
  "backend": "svn",
  "root": "/home/u/code/foo",
  "kind": "svn-working-copy",
  "svn_hosted": true,
  "svn": {
    "url": "https://svn.apache.org/repos/asf/foo/trunk",
    "repository_root": "https://svn.apache.org/repos/asf",
    "project_url": "https://svn.apache.org/repos/asf/foo",
    "line_of_work": "trunk",
    "layout": "trunk/branches/tags",
    "uuid": "13f79535-47bb-0310-9956-ffa450edef68",
    "source": "svn info"
  },
  "proposal": {
    "vcs_backend": "svn",
    "svn_url": "https://svn.apache.org/repos/asf/foo",
    "svn_repository_root": "https://svn.apache.org/repos/asf",
    "upstream_default_branch": "trunk"
  },
  "notes": []
}
```
