<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

1. Confirm we are in a git repo (`git rev-parse
   --show-toplevel`).
2. **Confirm we are in the main checkout, not a git worktree.**
   Compare `git rev-parse --git-dir` against
   `git rev-parse --git-common-dir` — they are equal in the
   main checkout and different in a worktree.
