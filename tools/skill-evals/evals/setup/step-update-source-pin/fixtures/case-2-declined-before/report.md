<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: pinned snapshot, updated in this run to the new framework version.
Resolved project.md: `organization: ASF`.
`<project-config>/skill-sources.md` lists two sources.

`PYTHONPATH=<trusted-installed-setup-package-parent> python3 -P -m setup_preflight.skill_sources pins --project-root . --trust-list .apache-magpie-overrides/skill-sources.md --catalogue .apache-magpie/organizations/ASF/skill-sources.md`:

```json
[
  {
    "id": "apache-incubator-releasecheck",
    "state": "declined",
    "ref": "releasecheck-0.5.1",
    "anchor_key": "commit",
    "anchor": "876cf205",
    "curated_ref": "releasecheck-0.6.0",
    "curated_anchor": "a1b2c3d4"
  },
  {
    "id": "acme-skills",
    "state": "not-curated",
    "ref": "v2.1.0",
    "anchor_key": "commit",
    "anchor": "0f0f0f0f",
    "curated_ref": null,
    "curated_anchor": null
  }
]
```
