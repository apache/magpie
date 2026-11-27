<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code, sandboxed. This session runs in the tracker checkout.
Tracker `acme-s/acme-s#412`, CVE-2026-31337 allocated. Reporter: Dana Example.
Agreed fix (security-team consensus in the tracker): reject `..` path segments
in the artifact download endpoint, `acme/api/artifacts.py`, and add a test that
a request for `../../etc/passwd` returns 400. Base branch `trunk`.
The project declares *Source control* `asf-svn`, and `fix-flow` returned
`"flow": "patch-then-commit"`. The user's working copy is `~/svn/acme`,
which this sandbox cannot read. `ListAgents` shows a live, interactive
session `acme-svn` working in `~/svn/acme`; its row says `idle`.
