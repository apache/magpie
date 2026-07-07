<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Reviewer: justinmclean
## PRs reviewed in window: 1

### PR #42

Review submission:
- author.login: justinmclean
- state: COMMENTED
- body: ""  (empty)
- comments.totalCount: 10

Inline comments (sample):
1. "This import is unused — remove it."
2. "Naming: `tmp` is unclear, use `pending_tasks`."
3. "This loop should use `enumerate` rather than a manual counter."
4. "Missing type annotation on return value."
5. "This exception is too broad — catch `ValueError` specifically."
6. "The constant should live in `constants.py`, not inline here."
7. "This condition is always true when `x` is validated upstream — simplify."
8. "Add a blank line before this block for readability."
9. "Consider extracting this into a helper function."
10. "Docstring missing on public method."
