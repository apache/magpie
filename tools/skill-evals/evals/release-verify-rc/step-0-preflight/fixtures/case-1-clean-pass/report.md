<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

RC tag: 2.11.0-rc1
--post-to: not supplied

release-config preflight output
(`uv run --project <framework>/tools/release-config release-config preflight --skill verify-rc 2.11.0-rc1`):

```json
{
  "ok": true,
  "skill": "verify-rc",
  "blockers": [],
  "warnings": [],
  "values": {
    "rc_tag": "2.11.0-rc1",
    "staging_url": "https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/",
    "keyserver": "keys.openpgp.org",
    "post_to": null
  }
}
```

Staging URL fetch: https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/ → HTTP 200 (directory listing).
