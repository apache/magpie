<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Candidate (surfaced by a backlog-grooming pass):

Proposed title: Add a --quiet flag to the `export` command
Description: The `export` subcommand prints one progress line per record
to stdout, which clutters output when the command is used in scripts. Add
a `--quiet` flag that suppresses the per-record progress lines while still
printing the final summary count at the end.
max_effort_hours: 4
Named source files:
  - src/acme/cli/export.py — defines the `export` command and its argparse options
  - tests/cli/test_export.py — where CLI option tests live
Acceptance notes: with --quiet, the per-record lines are suppressed and
only the final "Exported N records" summary prints; without the flag,
behaviour is unchanged; a test covers both paths.
Maintainer note: small, well understood, no design decisions; good for a
first-time contributor.
