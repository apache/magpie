<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Archive backend — `svnpubsub` (ASF default)

**Listing.** `svn list <dist-release-url>` — each directory entry is a version or a version-suffix directory.
`listing` renders the URL from `release_dist_url_template` (`release` bucket, cut at `<version>`).

**Archive.** One `svn mv` per past-retention version, in ascending version order (oldest first), with the commit message inline:

```text
svn mv \
  https://dist.apache.org/repos/dist/release/<project>/<ver> \
  https://archive.apache.org/dist/<project>/<ver> \
  -m "Archive <project> <ver> per retention policy"
```

The destination is `archive_url_template` (default `https://archive.apache.org/dist/<project>/`), with `<version>` substituted or `<ver>` appended.
The RM runs each `svn mv` under their own credentials; this skill never does.
