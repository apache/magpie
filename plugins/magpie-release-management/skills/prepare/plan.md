<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 1 — Draft the planning issue (sub-command: `plan`)

## 1a — Determine the merged-PR set

Query the merged-PR set since the previous release tag:

```bash
gh pr list --repo <upstream> \
  --state merged \
  --base <release-branch-base> \
  --search "merged:>=<previous-tag-date>" \
  --json number,title,url,labels,mergedAt \
  --limit 500
```

If `--previous-tag <tag>` was passed, use it directly; otherwise:

```bash
git ls-remote --tags https://github.com/<upstream>.git > <tags.txt>
python3 <skill-dir>/scripts/prev_tag.py --tags <tags.txt> --version <version> --train <train-pattern>
```

`<train-pattern>` comes from `release-trains.md` (e.g. `2.x`); add `--tag-prefix <ns>/` for namespaced tags.
`previous_tag` is the highest final release tag below `<version>` in the train (the same major when no train is given),
skipping release candidates and other pre-releases; when `null`, ask the RM.

**Empty-set hand-off.** If the merged-PR set is empty and `--skip-empty-check` was not passed, return:

```json
{
  "empty_pr_set": true,
  "previous_tag": "<tag>",
  "handoff_reason": "No PRs merged since <previous-tag>. RM must decide whether to skip or proceed."
}
```

Do not proceed to the planning issue draft when `empty_pr_set` is `true`.

## 1b — Draft the planning issue body

Compose the planning issue body using:

- `release_planning_issue_template` from config (path under `<project-config>/`), if present; otherwise the default template below.
- The version, release train, release branch, previous tag, and the merged-PR set.

Default planning issue template:

```markdown
## Release: <Product Name> <version>

**Release Manager:** <from release-trains.md or user.md>
**Release train:** <train name>
**Base branch:** <release-branch-base>
**Previous release:** <previous-tag>

## In scope

<Numbered list of PRs merged since previous-tag, grouped by label
(e.g. `kind/bug-fix`, `kind/feature`). Each entry: `#N <title> (<url>)`>

## Steps

- [ ] Step 1: Planning issue open ← this issue
- [ ] Step 2: Prep PR open (`release-prepare prep <version>`)
- [ ] Step 3: KEYS reconciliation (`release-keys-sync`)
- [ ] Step 4–5: RC cut + stage (`release-rc-cut <version> rc1`)
- [ ] Step 6: Pre-flight verify (`release-verify-rc <version>-rc1`)
- [ ] Step 7: `[VOTE]` thread (`release-vote-draft <version>-rc1`)
- [ ] Step 8: Voting window
- [ ] Step 9: Tally (`release-vote-tally <version>-rc1`)
- [ ] Step 10: Promote (`release-promote <version>-rc1`)
- [ ] Step 11: Announce + site bump (`release-announce-draft <version>`)
- [ ] Step 12: Archive sweep (`release-archive-sweep`)
- [ ] Step 13: Audit log (`release-audit-report <version>`)
- [ ] Step 14: Post-release bump (`release-prepare post <version>`)

## Artefacts

<!-- release-rc-cut fills this in after Step 4–5 -->
- Staging URL: (TBD)
- Tag URL: (TBD)
- RC artefact list: (TBD)

## Timestamps

<!-- Skills fill these in as the lifecycle progresses -->
- Planning issue opened: <ISO-8601>
- Prep PR opened: (TBD)
- RC staged: (TBD)
- Vote opened: (TBD)
- Vote closed: (TBD)
- Promote commit: (TBD)
- [ANNOUNCE] sent: (TBD)
```

Present the draft issue title and body to the RM.
Ask for confirmation before creating the issue.

Proposed issue title: `Release <Product Name> <version>`

If the RM confirms, write the approved body to `<scratch>/planning-issue-body-<version>.md` with the Write tool
(`<scratch>` is the session scratch directory as an absolute path) and create the issue with a plain `gh` call:

```bash
gh issue create \
  --repo <upstream> \
  --title "Release <Product Name> <version>" \
  --body-file <scratch>/planning-issue-body-<version>.md \
  --label "release-planning"
```

Return ONLY valid JSON with this structure:

```json
{
  "issue_title": "<proposed issue title>",
  "issue_body": "<proposed issue body>",
  "pr_set_size": <integer count of merged PRs>,
  "previous_tag": "<tag>",
  "empty_pr_set": false,
  "proposed": true
}
```

`proposed` is always `true` at the point this JSON is returned — the issue has not yet been created.
Creation happens only after the RM's explicit confirmation in the conversation.
