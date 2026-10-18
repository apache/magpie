<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# A render refused

`release-management rc-cut render` exits `2` with `{"ok": false, "refused": "<why>"}` instead of printing a block.
Surface `refused` as written and stop; never compose the block by hand.

| `refused` names | Likely cause | Remediation |
|---|---|---|
| `dist/release/` denylist | `release_dist_url_template` renders a `dist/release/` staging URL (`release_dist_backend = svnpubsub`) | Correct the template; the staging target must be `dist/dev/`. Promotion is `release-promote`'s responsibility |
| prohibited digest | `digest_set` lists `md5` or `sha1` | Remove it from `release-build.md` (Golden rule 3) |
| `release_publish_command_template` | `self-hosted` backend without the template | Set the template in `release-management-config.md` |
| unknown `release_dist_backend` | Typo or unsupported backend | Use `svnpubsub`, `atr`, `github-releases`, `s3` or `self-hosted` |
| `--asf-id` | Step 3 under `svnpubsub` without the RM's ASF id | Rerun Step 3 with `--asf-id <the RM's ASF id>` (from `user.md`, or ask the RM) |
| `--framework` | The tool does not run from a framework checkout, so the `repro-archive` path is unknown | Rerun the render with `--framework <path to the framework root>` |
| Step 3 under `ci-automated` | CI stages in that mode | Skip Step 3; Step 2c recorded the run |
