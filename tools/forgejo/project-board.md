<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Forgejo / Gitea — Project boards](#forgejo--gitea--project-boards)
  - [No GraphQL (Projects V2) support](#no-graphql-projects-v2-support)
  - [REST API operations](#rest-api-operations)
  - [Per-project configuration](#per-project-configuration)
  - [When the board is a no-op](#when-the-board-is-a-no-op)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Forgejo / Gitea — Project boards

This file documents how Forgejo/Gitea boards are integrated into the Magpie framework.

> [!WARNING]
> **No GraphQL Support:** Forgejo and Gitea **DO NOT** support GitHub's GraphQL API (including `Projects V2`). Do not attempt to use `gh api graphql` or any GraphQL mutations to manage Forgejo project boards. Doing so will result in immediate failure.

## No GraphQL (Projects V2) support

Unlike GitHub, Forgejo provides built-in issue boards (projects) directly linked to repositories or organizations, and these are managed exclusively via the REST API.

## REST API operations

Because `tea` CLI support for project boards is currently limited, interactions with project boards (if configured) must be done via standard `curl` commands hitting the Forgejo REST API.

Key endpoints (assume standard `Authorization: token $TEA_TOKEN` header):

- **List projects:** `GET /api/v1/repos/<tracker>/projects`
- **List columns:** `GET /api/v1/projects/<project-id>/columns` (or similar depending on Forgejo version)
- **Assign issue to project:** Varies by Forgejo version, typically updating the issue payload or posting to a project-issue association endpoint.

*Note for agent skills:* Before attempting to move an issue across Forgejo board columns, you must read the adopting project's configuration to verify if boards are even used. If they are used, rely strictly on the `curl` + REST API approach.

## Per-project configuration

Any required IDs (like `project_board_id` and specific column IDs) will live in the adopting project's manifest (e.g. `<project-config>/*-config.md`).

## When the board is a no-op

Not every Forgejo-backed project runs a project board. A project that lists its trackers via plain issue lists or milestones can leave the board-related fields in its manifest empty; sync-style skills should treat missing board config as *"no board reconciliation to do"* and skip the board-column proposal without failing the sync.
