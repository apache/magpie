<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**

- [GitLab Tool Adapter](#gitlab-tool-adapter)
  - [Operations catalogue](#operations-catalogue)
  - [Options and flags](#options-and-flags)
  - [Confidentiality](#confidentiality)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# GitLab Tool Adapter

Operations catalogue mapping for GitLab tracker, source control, and merge requests.

## Operations catalogue

| Operation | GitLab command |
| --- | --- |
| Read repository metadata | `magpie-gitlab repo get <project>` |
| Read issue body | `magpie-gitlab issue get <project> <issue_iid>` |
| List issues | `magpie-gitlab issue list <project>` |
| Read MR | `magpie-gitlab mr get <project> <mr_iid>` |
| MR Diff | `magpie-gitlab mr diff <project> <mr_iid>` |
| MR Commits | `magpie-gitlab mr commits <project> <mr_iid>` |
| List MR Pipelines | `magpie-gitlab mr pipelines <project> <mr_iid>` |
| CI Pipeline Status | `magpie-gitlab pipeline status <project> <pipeline_id>` |

## Options and flags

- `--limit <int>`: Cap the total number of items returned for paginated endpoints (`issue list`, `mr list`, `mr diff`, `mr commits`, `mr pipelines`). Automatically calculates and requests only the required number of pages (`ceil(limit / 100)`).
- `--state <choice>`: Filter items by state:
  - For `issue list`: `opened` (default), `closed`, `all`.
  - For `mr list`: `opened` (default), `closed`, `locked`, `merged`, `all`.

## Confidentiality

*Confidentiality Note*: Never log personal access tokens. All payload
bodies are handled purely in memory and output in JSON format.
