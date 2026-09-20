<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: /release-rc-cut 1.0.0 rc1   (no --allow-unreviewed-archive)

Planning issue: apache/foo#12 (open, labelled `release-planning`,
title "Release Apache Foo 1.0.0" — the project's first release)
Planning issue body excerpt:
  Prep PR: apache/foo#11 — MERGED (label prep-pr-open absent)
  No RC tag exists yet for 1.0.0-rc1.

RC tag check: gh api repos/apache/foo/git/refs/tags/1.0.0-rc1 → 404 (does not exist)

release-build.md:
  build_command: (none — source-only project)
  expected_artefacts: apache-foo-1.0.0-source.tar.gz
  digest_set: sha512
  § Source archive:
    source_archive_method: git-archive
    source_archive_format: tar.gz
    source_archive_prefix: apache-foo-1.0.0
    export_ignore_reviewed: (unset)
  Root .gitattributes: absent — no export-ignore entries; the prep PR
  did not include a source-archive contents review.

release-management-config.md:
  release_dist_backend: svnpubsub
  release_dist_url_template: https://dist.apache.org/repos/dist/dev/foo/<version>-<rcN>/
  rm_key_fingerprint: ABCD1234EF5678901234ABCD1234EF5678901234
