<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Category B failed — commit message shape

The three rules, under the project's commit-attribution convention ([`commit-attribution.md`](../../../../../docs/setup/commit-attribution.md); default `generated-by`):

1. **Imperative subject** ("Add X", not "Added" / "Adds" / "Adding"); a conventional-commits prefix is fine.
2. **No `Co-Authored-By:` for an AI agent**, unless the convention is `co-authored-by` — a human co-author is fine. See [`AGENTS.md` § Commit and PR conventions](../../../../../AGENTS.md#commit-and-pr-conventions).
3. **The convention's trailer when AI-assisted** (`Generated-by: <agent> (<model>)` by default; none under `none`), added with `git commit --trailer`.

To fix a pushed history: `git rebase -i <base>` and reword, or squash into one well-formed commit.
