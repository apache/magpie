<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# KEYS backend — `git` (`github.com`) and other non-ASF URLs

For a non-ASF adopter whose `keys_file_url` points to a GitHub repository (URL contains `github.com`),
`svn_command_sequence` holds the equivalent `git` commands: clone the repository, branch from the file's branch,
leave the append to the RM, commit, push, and open a PR in the browser for review (the RM runs the last line too; the skill never opens it).
The RM pushes to their fork instead when they lack write access to the repository.

For any other URL scheme the render prints generic instructions (fetch the KEYS file with the project's own workflow, append, publish with the given message);
tailor them to the URL in `keys_file_url` when presenting them, without running anything.
