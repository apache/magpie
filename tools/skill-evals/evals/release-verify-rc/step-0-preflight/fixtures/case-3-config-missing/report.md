<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC tag: 2.11.0-rc1
--post-to: not supplied

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill verify-rc 2.11.0-rc1`):

```json
{
  "ok": false,
  "skill": "verify-rc",
  "blockers": [
    "required key `release_dist_url_template` is missing from release-management-config.md"
  ],
  "warnings": [],
  "values": {
    "rc_tag": "2.11.0-rc1",
    "staging_url": null,
    "keyserver": "keys.openpgp.org",
    "post_to": null
  }
}
```

No staging URL was derived, so nothing was fetched.
