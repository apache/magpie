<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project: Apache Quokka (fictional). `<project-config>/project.md` → *Tools enabled → Source control*: `asf-svn`.

The user pointed at `/home/dev/quokka-mirror`. The command

`uv run --project <framework>/tools/vcs magpie-vcs -C /home/dev/quokka-mirror fix-flow --declared asf-svn`

exited 2 with:

```text
magpie-vcs: the manifest declares 'asf-svn' (svn) but the working copy is git; fix the manifest or point at the right working copy
```
