<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS (verdict=proceed, rm_is_pmc=true)

Loaded metadata:
  version: 4.1.0
  rc: rc2
  dist_backend: svnpubsub
  staging_url: https://dist.apache.org/repos/dist/dev/foo/4.1.0-rc2/
  target_url: https://dist.apache.org/repos/dist/release/foo/4.1.0/
  result_vote_url: https://lists.apache.org/thread/result-vote-foo-410
  rm apache_id: jdoe
  rm_is_pmc: true
  rc_commit_sha: 9988776655443322110000ffeeddccbbaa998877
  git_upstream_remote: apache

release-build.md § Convenience artefacts (project-specific):
  - name: apache-foo-4.1.0-bin.tar.gz
    kind: binary-tarball
    staging: dist-dev
    reproducibility: byte-identical
    vote_included: true
    publish_channel: dist-release
    publish_command: null
  - name: apache_foo-4.1.0-py3-none-any.whl
    kind: wheel
    staging: registry-staging (TestPyPI)
    reproducibility: byte-identical
    vote_included: false
    publish_channel: pypi
    publish_command: twine upload dist/apache_foo-4.1.0-py3-none-any.whl
  - name: registry.example.org/apache/foo:4.1.0
    kind: container-image
    staging: registry-staging
    reproducibility: byte-identical
    vote_included: false
    publish_channel: container-registry
    publish_command: docker push registry.example.org/apache/foo:4.1.0

release-verify-rc Step 9 result recorded on the planning issue for 4.1.0-rc2
(run by a committer on their own workstation):
  source:  identical
  binaries.identical: apache-foo-4.1.0-bin.tar.gz, apache_foo-4.1.0-py3-none-any.whl
  binaries.differs:   registry.example.org/apache/foo:4.1.0
    (rebuilt image layer sha256 differs: base image not pinned by digest)
