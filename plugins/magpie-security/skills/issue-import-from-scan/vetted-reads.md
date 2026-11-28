<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step B reads through vetted-ops

Read from [Step B](SKILL.md#step-b--triage-every-finding-mandatory-reuse-the-existing-machinery) when its reads run through vetted-ops. They use this skill's own caller, never the caller of the skill whose step they reuse.

## The commands

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-import-from-scan --save open-trackers.json issue-list-with-bodies
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-import-from-scan issue-search "<key>"
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-import-from-scan issue-view <N>
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-import-from-scan repo-pr-search "<words>"
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-import-from-scan pr-view <PR>
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-import-from-scan pr-diff <PR>
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-import-from-scan compare <scan-commit> <merge-commit>
```

`issue-list-with-bodies` is the open-tracker list (keep the `open` entries), `issue-search` the Step 2a and Step 2.6 searches (no `:` qualifiers: filter the returned `state` and `labels`), and `issue-view` the Step 2a follow-up reads.
For the fixed-since-the-scan check, `repo-pr-search` finds candidate PRs, `pr-view` gives each one's state, files and merge commit, `pr-diff` shows whether it addresses the finding,
and `compare` with the scan's commit as base and the merge commit as head prints `ahead` when the fix landed after the scan.
