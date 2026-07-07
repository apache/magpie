<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

While running a Magpie skill, the tool `tools/cve-tool-vulnogram/oauth-api`
`record-publish` command failed on every real record with
`CNA_private field is not an object: NoneType`. Reading the code, it accesses
`document.get("CNA_private")` at the top level, but the read API wraps the
document under a `body` envelope — so the field is always None. The bug is in
the framework's own Python; it reproduces regardless of any adopter config.
The local snapshot is in sync with the committed lock (no drift).
