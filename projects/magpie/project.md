<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie — project configuration](#apache-magpie--project-configuration)
  - [Identity](#identity)
  - [Repositories](#repositories)
  - [Mailing lists](#mailing-lists)
  - [CNA](#cna)
  - [Project board](#project-board)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie — project configuration

Magpie's own `project.md`. Magpie self-adopts the framework, so this is the
live config the skills read, not a scaffold. The adopter template lives at
[`projects/_template/project.md`](../_template/project.md).

Values here are the ones derivable from this repository and its `.asf.yaml`.
Keys that belong to the **private security tracker** and the **CNA queue** are
left as explicit `TODO`s rather than guessed: a wrong value there would point a
security skill at the wrong place, which is worse than a skill refusing to run.

## Identity

| Key | Value |
|---|---|
| `organization` | `ASF` ([`organizations/ASF/`](../../organizations/ASF/)) |
| `project_name` | `Apache Magpie` |
| `vendor` | `Apache Software Foundation` |
| `short_name` | `Magpie` |
| `product_family_url` | `https://magpie.apache.org/` |

## Repositories

| Key | Value | Notes |
|---|---|---|
| `tracker_repo` | *TODO — the private security tracker, as `owner/name`* | Not derivable from this repo; see the note above |
| `tracker_repo_url` | *TODO* | |
| `tracker_default_branch` | `main` | |
| `tracker_project_board_url` | *TODO* | Security board, if any |
| `upstream_repo` | `apache/magpie` | Public codebase — this repository |
| `upstream_repo_url` | `https://github.com/apache/magpie` | |
| `upstream_default_branch` | `main` | What `<default-branch>` resolves to |
| `upstream_agents_md_url` | `https://github.com/apache/magpie/blob/main/AGENTS.md` | |
| `upstream_contributing_docs_url` | `https://github.com/apache/magpie/blob/main/CONTRIBUTING.md` | |
| `upstream_genai_disclosure_anchor` | `https://github.com/apache/magpie/blob/main/CONTRIBUTING.md#opening-a-pull-request` | |
| `upstream_security_policy_url` | `https://github.com/apache/magpie/security/policy` | |

## Mailing lists

| Key | Value | Notes |
|---|---|---|
| `security_list` | `security@magpie.apache.org` | Inbound reports; not publicly archived |
| `private_list` | `private@magpie.apache.org` | PMC escalation; not publicly archived |
| `users_list` | `users@magpie.apache.org` | Publicly archived |
| `dev_list` | `dev@magpie.apache.org` | Release `[VOTE]` / `[RESULT]` threads; publicly archived |
| `announce_list` | `announce@apache.org` | Cross-project announcements |
| `commits_list` | `commits@magpie.apache.org` | Publicly archived |

`dev_list` and `announce_list` match
[`release-management-config.md`](release-management-config.md), which is the
authority for the release flow.

## CNA

| Key | Value |
|---|---|
| `asf_org_id` | *TODO — the project's CNA org UUID* |
| `cna_private_owner` | *TODO* |
| `cna_private_projecturl` | `https://magpie.apache.org/` |
| `cna_private_userslist` | `users@magpie.apache.org` |

## Project board

| Key | Value |
|---|---|
| `project_board_url` | *TODO* |
| `project_board_number` | *TODO* |
| `project_board_node_id` | *TODO* |
| `status_field_node_id` | *TODO* |
