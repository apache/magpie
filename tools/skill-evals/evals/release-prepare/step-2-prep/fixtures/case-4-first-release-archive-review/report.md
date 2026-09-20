<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight passed. Sub-command: prep. Version: 1.0.0 — the project's FIRST release.
Planning issue: apache/foo#12 (labelled release-planning, title "Release Apache Foo 1.0.0")
PR set: 40 PRs (from planning issue body).
Previous tag: (none — first release). Release branch base: main.

version_manifest_files: pyproject.toml
  pyproject.toml current version: 1.0.0.dev0
Target version: 1.0.0

category_x_dependencies: (empty list — no Category-X check needed)
NOTICE: new file, standard ASF text. LICENSE: Apache-2.0, no bundled deps.
Changelog: 40 PRs, all categorised. Coverage: 100%.

release-build.md § Source archive:
  source_archive_method: git-archive, source_archive_format: tar.gz,
  source_archive_prefix: apache-foo-1.0.0
  export_ignore_reviewed: (unset)  → the full source-archive contents review is due.
Root .gitattributes: absent.

Local clone at main. Top-level tracked entries and the RM's answers in the
guided review (each entry confirmed individually):
  LICENSE, NOTICE, README.md, pyproject.toml, uv.lock, src/, docs/, tests/  → ship
  .rat-excludes            → ship (input to the RAT check voters run)
  .asf.yaml                → ship (ASF project metadata; RM's call)
  .gitignore               → ship (dev-environment config; RM's call)
  .gitattributes           → exclude (VCS metadata)
  .pre-commit-config.yaml  → exclude (dev tooling)
  .github/workflows/       → exclude (CI); .github/ISSUE_TEMPLATE/ ships — docs/CONTRIBUTING.md links to it (git grep hit)
  .idea/                   → exclude (editor state)
  .ruff.toml, .yamllint    → exclude (lint config not needed to build)
No committed symlinks. Before/after listing diff: 6 paths removed, all in
the excluded set; no shipped file references a removed path.

Draft the prep PR. Propose it to the RM — do not open the PR yet.
