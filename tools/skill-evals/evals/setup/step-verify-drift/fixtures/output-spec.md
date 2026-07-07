<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "status": "clean" | "sync-needed" | "reinstall-needed" | "security-flagged" | "local-lock-missing",
  "severity": "ok" | "warning" | "error",
  "remediation": "none" | "/magpie-setup upgrade" | "investigate"
}
```

- `"clean"` — all fields match; for `git-branch` method the local commit
  is at the upstream tip. `severity: "ok"`, `remediation: "none"`.
- `"sync-needed"` — ref differs (tag bumped, or `git-branch` local is
  behind upstream tip), but method and URL match. `severity: "warning"`,
  `remediation: "/magpie-setup upgrade"`.
- `"reinstall-needed"` — method or URL differs between committed and
  local lock. `severity: "error"`, `remediation: "/magpie-setup upgrade"`.
- `"security-flagged"` — `svn-zip` method and the SHA-512 in the
  committed lock does not match what is on disk / last fetched.
  `severity: "error"`, `remediation: "investigate"`.
- `"local-lock-missing"` — `.apache-magpie.local.lock` is absent or
  unparsable. `severity: "warning"`,
  `remediation: "/magpie-setup upgrade"`.
- Do not include any text outside the JSON object.
