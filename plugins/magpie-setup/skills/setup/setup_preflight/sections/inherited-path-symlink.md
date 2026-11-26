<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## inherited-path-symlink — a main-checkout path this worktree inherits is now a symlink

`facts.path` is in the main checkout, and this linked worktree reads it: its personal layer or one of its Claude settings files.
`sandbox-add-project-root.sh` grants a worktree a read of such a path only while it is not a symlink.
It is one now, so a read grant made earlier could reach wherever the link points.

1. **Tell the user before anything else, in one line:**

   > `<facts.path>` in the main checkout is now a symlink, so a sandbox read grant this worktree inherited could reach another place. Check the link, then refresh the grants from the main checkout.

2. **Give them the two commands to run in their own terminal**, never through the agent:

   ```bash
   ls -l <facts.path>
   ~/.claude/scripts/sandbox-add-project-root.sh
   ```

   The second, run in this worktree, drops every inherited grant that is now a symlink.
   If they did not create the link, it is worth finding out what did before replacing it with the real directory or file.

Never follow, read through, delete or recreate the link from here, and never widen any grant.
Then carry on with the user's request.
