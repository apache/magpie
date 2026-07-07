<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Planning issue: apache/airflow#47000 (open, labelled `release-planning`,
title "Release Apache Airflow 2.12.0")
Planning issue body excerpt:
  Prep PR: apache/airflow#46990 — OPEN (still under review; label
  `prep-pr-open` still present on the planning issue)

RC tag check: gh api repos/apache/airflow/git/refs/tags/2.12.0-rc1 → 404 (does not exist)

release-build.md:
  build_command: python -m build --sdist
  expected_artefacts: apache_airflow-2.12.0.tar.gz
  digest_set: sha512

release-management-config.md:
  release_dist_backend: svnpubsub
  release_dist_url_template: https://dist.apache.org/repos/dist/dev/airflow/<version>-<rcN>/
  rm_key_fingerprint: ABCD1234EF5678901234ABCD1234EF5678901234
