<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Step 2 emitted. Source artefact built with:
  uv run --project .apache-magpie/tools/reproducible-archive repro-archive build \
    --ref "1.0.0-rc1" --format tar.gz --prefix "apache-foo-1.0.0" \
    -o "apache-foo-1.0.0-source.tar.gz"
  → commit 1890a13d…, SOURCE_DATE_EPOCH 1758326400

Loaded configuration:
  version: 1.0.0, rc: rc1
  expected_artefacts: apache-foo-1.0.0-source.tar.gz (no convenience binaries)
  source_archive_method: git-archive
  source_archive_format: tar.gz
  source_archive_prefix: apache-foo-1.0.0
  reproducibility_source: on
  reproducibility_binaries: off
  signing_mode: rm-key
  --skip-repro-check: not passed
