<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 6c output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "step": "nexus-staging",
  "status": "PASS" | "WARN" | "FAIL" | "SKIP",
  "staging_repos": [
    {"id": "<repository id>", "state": "closed" | "open" | "unverified", "matches_rc": true}
  ],
  "nexus_findings": ["<one line per hard finding or warning>"],
  "paste_recipe": "<multi-line shell commands>"
}
```

Grading rules:
- A hard finding — repository not reachable at the id given for this
  RC, repository `open`, snapshots repository targeted, coordinates
  or version mismatch, a `.jar`/`.pom` with no sibling `.asc`, a main
  jar with an incomplete companion set — is a hard `"FAIL"`, never a
  warning.
- `open` and not-reachable are distinct findings and must not be
  conflated: `open` says "something editable there", not-reachable
  says "nothing there".
- `STATE-UNVERIFIED` (no Nexus credentials, so the authoritative
  state could not be read on the anonymous path) and stale sibling
  repositories are `"WARN"`s, never `"FAIL"`s — a voter with no
  Nexus account hitting `STATE-UNVERIFIED` is the expected shape of
  the anonymous path.
- `staging_repos` lists every staging repository surfaced — one entry
  when only the anonymous path ran, one per sibling when the
  authenticated profile listing ran; `state` is the authoritative
  value when it was read, `unverified` when it was not;
  `matches_rc` reflects whether the repository's inventory
  corresponds to the RC's declared version (the plain version, no
  `-rcN` suffix — that lives in the dist path).
- `nexus_findings` carries only hard findings and warnings, one line
  each naming the repository or artefact and what is wrong; an empty
  list means nothing to report.
- `paste_recipe` must be a non-empty string with the existence check
  against `https://repository.apache.org/content/repositories/<id>/`
  using the concrete repository id, the authenticated state check
  only when the case says credentials are available, and the
  inventory crawl; it must contain no write verbs.
- No extra keys are permitted in the response.
