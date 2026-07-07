<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

cat .apache-magpie.lock:
  method: svn-zip
  url: https://dist.apache.org/repos/dist/release/magpie/magpie-0.9.4-source.tar.gz
  ref: v0.9.4

cat .apache-magpie.local.lock:
  method: git-branch
  url: https://github.com/apache/magpie.git
  ref: v0.9.4

Result: method mismatch — committed lock specifies svn-zip but local snapshot
was fetched via git-branch. URL also differs. A full re-install is needed.
