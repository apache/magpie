<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight passed. Sub-command: post. Version: 2.11.0.
Planning issue: apache/airflow#48700 (labelled announced)
Release branch base: main.

version_manifest_files: setup.cfg, airflow/__init__.py
  setup.cfg current version: 2.11.0 (released, already bumped by prep PR)
  airflow/__init__.py: __version__ = "2.11.0"

Project uses setup.cfg / Python packaging style.
Next development version convention: bump minor, append .dev0
  → next dev version: 2.12.0.dev0

category_x_dependencies: (empty — not relevant to post-bump)
NOTICE/LICENSE: must NOT be touched in Step 14.

Draft the post-release bump PR. Propose it to the RM — do not open it yet.
