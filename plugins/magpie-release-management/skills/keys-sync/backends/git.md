<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# KEYS backend — `git` (`github.com`) and other non-ASF URLs

For a non-ASF adopter whose `keys_file_url` points to a GitHub repository (URL contains `github.com`),
`svn_command_sequence` holds the equivalent `git` commands: clone the repository, branch from the file's branch,
leave the append to the RM, commit, push, and open a PR in the browser for review (the RM runs the last line too; the skill never opens it).
The RM pushes to their fork instead when they lack write access to the repository.

The URL is `https://github.com/<owner>/<repo>/blob/<branch>/<path>` (`raw/` and `raw.githubusercontent.com`, with or without `refs/heads/`, read the same).
The branch is the first segment after `blob/` and the path is the rest, so KEYS may sit in a sub-directory (`dist/KEYS`); the file must be named `KEYS`.
A branch that itself contains `/` (`release/1.x`) is named by `keys_file_branch` in `release-management-config.md`:
the URL must then start with that branch, and the render refuses, naming both, when it does not.
Without `keys_file_branch`, a path in a sub-directory comes with a warning saying which segment was taken as the branch: surface it.
The derived branch and path are what the checkout, `git add` and PR base use.

For any other URL scheme the render prints generic instructions (fetch the KEYS file with the project's own workflow, append, publish with the given message);
tailor them to the URL in `keys_file_url` when presenting them, without running anything.
