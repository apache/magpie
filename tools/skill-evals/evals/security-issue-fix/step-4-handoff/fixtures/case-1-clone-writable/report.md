<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code, sandboxed. This session runs in the tracker checkout.
Tracker `acme-s/acme-s#412`, CVE-2026-31337 allocated. Reporter: Dana Example.
Agreed fix (security-team consensus in the tracker): reject `..` path segments
in the artifact download endpoint, `acme/api/artifacts.py`, and add a test that
a request for `../../etc/passwd` returns 400. Base branch `main`.
`environment.upstream_clone` is `~/code/acme`, and the vetted-ops policy has
`[git]` values for `acme/acme` with `~/code/acme` among its checkouts and a
worktree root this sandbox can write.
