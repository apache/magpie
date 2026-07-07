<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing Step 1 — Resolve config of the
security-tracker-stats-dashboard skill from the Apache Magpie framework.

## Config resolution rules

1. Read `<project-config>/security-tracker-stats.md` to find the adopter's
   YAML config path.
   - Default path: `<adopter-repo>/.apache-magpie-overrides/security-tracker-stats.yaml`
   - The adopter may override this with a `tracker_stats_config:` key in that
     file.

2. Check whether that YAML file exists.
   - If it exists: use it as the active config; set `config_path` to its
     absolute path.
   - If it does not exist: fall back silently to the framework's built-in
     `default-config.yaml`; set `config_path` to the string `"default"`.

3. Determine bucket granularity:
   - Read from the YAML config's `buckets:` key (or `"monthly"` when using
     the default config).
   - If the user passed `quarterly` or `monthly` as an argument: that arg
     overrides the config value.

4. Resolve the output path:
   - Use `output_path:` from `security-tracker-stats.md` if present.
   - Otherwise default to `/tmp/tracker-stats.html`.
   - If the user passed an explicit filesystem path as an argument: use that
     path instead.

Always surface the resolved `config_path` and `buckets` to the user as
the first line of output (golden rule 4).

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "config_path": "<absolute path to the YAML file, or the string 'default'>",
  "buckets": "monthly | quarterly",
  "output_path": "<resolved absolute HTML output path>"
}
```

`config_path` is the string `"default"` when the adopter YAML file does
not exist.  Do not include any text outside the JSON object.
