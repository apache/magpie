<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: pinned snapshot, updated in this run to the new framework version.
Resolved project.md: `organization: ASF`.
`<project-config>/skill-sources.md` lists two sources.

`python3 -P -m setup_preflight.skill_sources pins --project-root . --trust-list .apache-magpie-overrides/skill-sources.md --catalogue .apache-magpie/organizations/ASF/skill-sources.md`:

```json
[
  {
    "id": "apache-incubator-releasecheck",
    "state": "declined",
    "ref": "releasecheck-0.5.1",
    "commit": "876cf205",
    "curated_ref": "releasecheck-0.6.0",
    "curated_commit": "a1b2c3d4"
  },
  {
    "id": "acme-skills",
    "state": "not-curated",
    "ref": "v2.1.0",
    "commit": "0f0f0f0f",
    "curated_ref": null,
    "curated_commit": null
  }
]
```
