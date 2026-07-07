<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

cat .apache-magpie.lock:
  method: svn-zip
  url: https://dist.apache.org/repos/dist/release/magpie/magpie-0.9.4-source.tar.gz
  ref: v0.9.4
  sha512: a3f8c2e1d4b09f7e2c6a1d8b3f5e7c9a2d4b6f8e0c2a4d6b8f0e2c4a6d8b0f2e4c6a8d0b2f4e6c8a0d2b4f6e8c0a2d4b6f8e0c2a4d6b8f0e2c4a6d8b0f2e4c6

cat .apache-magpie.local.lock:
  method: svn-zip
  url: https://dist.apache.org/repos/dist/release/magpie/magpie-0.9.4-source.tar.gz
  ref: v0.9.4
  sha512: 9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e7

Result: SHA-512 mismatch — committed anchor differs from the hash of the
locally-fetched archive. The method, URL, and ref are identical; only the
hash diverges. Security-flagged: investigate the archive source before
proceeding.
