<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Snapshot lock file state

cat .apache-magpie.lock:
  method: svn-zip
  url: https://dist.apache.org/repos/dist/dev/airflow/magpie-0.9.2.tar.gz
  ref: v0.9.2
  sha512: 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08d2e7a12f7c9e81237abc456789...

cat .apache-magpie.local.lock:
  method: svn-zip
  url: https://dist.apache.org/repos/dist/dev/airflow/magpie-0.9.2.tar.gz
  ref: v0.9.2
  sha512: deadbeef0000111122223333444455556666777788889999aaaabbbbccccddddeeee...

Result: method, URL, and ref all match. However, the SHA-512 in the local lock
(deadbeef...) does not match the committed anchor (9f86d081...).
