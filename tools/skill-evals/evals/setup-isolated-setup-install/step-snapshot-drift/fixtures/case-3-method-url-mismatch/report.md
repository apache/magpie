<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Snapshot lock file state

cat .apache-magpie.lock:
  method: git-branch
  url: https://github.com/apache/magpie.git
  ref: v0.9.2

cat .apache-magpie.local.lock:
  method: svn-zip
  url: https://dist.apache.org/repos/dist/dev/airflow/magpie-0.9.1.tar.gz
  ref: v0.9.1
  sha512: abcdef1234567890...

Result: method and URL both differ — committed lock uses git-branch but local
snapshot was fetched via svn-zip from a different URL. This indicates a full
re-install against the correct method is required.
