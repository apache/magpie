<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The user runs `/magpie-setup config` in `~/code/baz`, a clone of the GitHub repository `apache/baz` (its `origin` remote).
`project.md` is in scope and `vcs_backend` is `TODO`. `user.md` names no separate `<upstream>` clone.

`magpie-vcs -C ~/code/baz probe` prints:

```json
{
  "path": "/home/u/code/baz",
  "backend": "git",
  "root": "/home/u/code/baz",
  "kind": "git-svn-mirror",
  "svn_hosted": true,
  "svn": {
    "url": "https://svn.apache.org/repos/asf/baz/trunk",
    "repository_root": null,
    "project_url": "https://svn.apache.org/repos/asf/baz",
    "line_of_work": "trunk",
    "layout": "trunk/branches/tags",
    "uuid": "13f79535-47bb-0310-9956-ffa450edef68",
    "source": "git-svn-id"
  },
  "proposal": {
    "vcs_backend": "svn",
    "svn_url": "https://svn.apache.org/repos/asf/baz",
    "svn_repository_root": null,
    "upstream_default_branch": "trunk"
  },
  "notes": [
    "HEAD carries a git-svn-id trailer but there is no svn-remote: a read-only mirror of Subversion; its repository root is not knowable offline",
    "this checkout is Git: magpie-vcs drives it with the git backend, which cannot commit to Subversion; the svn backend needs an `svn checkout` of the project"
  ]
}
```
