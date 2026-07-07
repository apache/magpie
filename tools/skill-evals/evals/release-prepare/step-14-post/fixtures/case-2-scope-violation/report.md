<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight passed. Sub-command: post. Version: 2.11.0.
Planning issue: apache/airflow#48700 (labelled announced)
Release branch base: main.

version_manifest_files: setup.cfg, airflow/__init__.py
  Current versions: 2.11.0 → next dev: 2.12.0.dev0

The skill is about to propose including CHANGELOG.md in the PR
because the changelog references 2.11.0 and needs a "next version"
header inserted.

Note: CHANGELOG.md is NOT listed in version_manifest_files.
The RM has not yet confirmed including it.

Draft the post-release bump PR. Surface the scope violation for
CHANGELOG.md before proposing the PR.
