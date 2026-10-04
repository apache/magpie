<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight passed. Sub-command: prep. Version: 2.11.0.
Planning issue: apache/airflow#48700 (labelled release-planning)
Previous tag: 2.10.3. Release branch base: main.

version_manifest_files: setup.cfg, airflow/__init__.py
  Current version: 2.11.0.dev0 → target: 2.11.0

category_x_dependencies from release-management-config.md:
  - "com.example:gpl-licensed-lib"   (GPL-2.0, Category-X)
  - "org.acme:cc-by-nc-widget"       (CC-BY-NC, Category-X)

Dependency scan of setup.cfg found:
  Line 47: install_requires includes "cc-by-nc-widget>=1.2.0"
  This matches the Category-X identifier "org.acme:cc-by-nc-widget" in
  the denylist.

Do not open a prep PR. Surface the Category-X violation to the RM.

release-build.md § Source archive: source_archive_method default (tag export),
  export_ignore_reviewed: 2.10.0 (review done). Drift check: no new top-level
  paths since 2.10.3 — the source-archive review is not due.

Output of `python3 <skill-dir>/scripts/category_x.py --deny com.example:gpl-licensed-lib --deny org.acme:cc-by-nc-widget setup.cfg=<local copy> airflow/__init__.py=<local copy>`:

```json
{
  "category_x_hit": true,
  "category_x_violations": [
    {
      "identifier": "org.acme:cc-by-nc-widget",
      "found_in": "setup.cfg"
    }
  ],
  "handoff_reason": "Category-X dependency found. Remove before preparing the release.",
  "first_match_lines": [
    {
      "identifier": "org.acme:cc-by-nc-widget",
      "found_in": "setup.cfg",
      "line": 47
    }
  ]
}
```
