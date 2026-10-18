<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-verify-rc — prerequisites

- **`<project-config>/release-management-config.md` readable** —
  `keys_file_url`, `release_dist_url_template`, `version_manifest_files`;
  `keyserver` is optional (default `keys.openpgp.org`).
- **`<project-config>/release-build.md` readable** —
  expected artefact list, digest set, binary-exclude list, RAT configuration path;
  `§ Source archive` and `§ Reproducibility checks` for Step 9
  (both optional — absent keys mean the defaults `git-archive` / `reproducibility_source: on` / `reproducibility_binaries: off`).
- **Network reachable** — the staging URL and the `KEYS` file URL must be fetchable.
  If either is unreachable, the skill stops at the inventory step and reports `FAIL` with the URL that failed.
- **`gpg` and Python 3.11+** — Steps 1–3, 5–8 and 10 run
  [`tools/release-verify`](../../../../tools/release-verify/README.md)
  (stdlib only; without `uv`, run
  `python3 <framework>/tools/release-verify/src/release_verify/__init__.py`);
  every step's configuration, classification and report render runs
  [`tools/release-management`](../../../../tools/release-management/README.md#verify-rc)
  (`release-management verify-rc`, stdlib only, runs nothing).
- **A clone of `<upstream>` reachable** for Step 9 —
  the resolved `user.md` local clone path, or a fresh `git clone` the recipe emits.
  The rebuild happens in the voter's checkout, on the voter's machine.
