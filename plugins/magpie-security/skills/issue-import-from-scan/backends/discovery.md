<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-scan — recursive folder discovery

From *Inputs — sources*.

**Recursive folder discovery.** When a folder source does not itself
look like a scan folder, treat it as a parent and **recursively discover
every descendant scan folder** and process each. For a GitHub tree-URL
on `<scan-repo>`, enumerate via the git tree API, e.g.
`gh api "repos/<owner>/<repo>/git/trees/<ref>?recursive=1" --jq '.tree[] | select(.path | test("<adapter index/evidence glob>")) | .path'`
and dedup to the containing directories. Echo the resolved scan list back
to the operator (count + paths) before triaging.
