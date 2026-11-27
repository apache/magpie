<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You need to post a long, multi-line Markdown comment on a PR with `gh`.

A. `gh pr comment <N> --body "$(cat comment.md)"`
B. Write the text to a file in the scratch directory, then `gh pr comment <N> --body-file <file>`.
C. `cat comment.md | gh pr comment <N> --body-file -`
