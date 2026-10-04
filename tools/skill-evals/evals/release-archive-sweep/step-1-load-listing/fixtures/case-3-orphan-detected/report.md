<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight: PASS
dist_backend: svnpubsub

release-trains.md:
  - train: "2.x", supported: true, latest: "2.11.0"

archive_retention_rule: keep latest of each supported train only

Current svn list output for dist/release/airflow/:
  2.10.0/
  2.11.0/
  1.10.15/

trains.json (supported trains from release-trains.md):

```json
[{"label": "2.x", "pattern": "2.x"}]
```

Output of `python3 <skill-dir>/scripts/retention.py --listing listing.txt --trains trains.json` (listing.txt holds the svn list output above):

```json
{
  "releases_found": [
    "1.10.15",
    "2.10.0",
    "2.11.0"
  ],
  "past_retention": [
    "2.10.0"
  ],
  "orphans": [
    "1.10.15"
  ],
  "unmapped": [],
  "latest_of_each_line": {
    "2.x": "2.11.0"
  },
  "trains_without_releases": [],
  "mapping_complete": true,
  "retention_rule_error": false,
  "handoff_required": true,
  "handoff_reasons": [
    "1.10.15 is not listed in release-trains.md and is an orphan; no archival command will be proposed for it \u2014 the RM must decide whether to archive, keep, or reconcile it into a known train"
  ],
  "non_version_entries": []
}
```
