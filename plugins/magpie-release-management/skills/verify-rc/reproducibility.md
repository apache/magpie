<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 9 — Reproducibility checks (optional)

Confirm the staged artefacts are a function of the tag alone.
Read the reproducibility record `release-rc-cut` left on the planning issue (source commit, `SOURCE_DATE_EPOCH`, sha512, format, prefix, and the `swh:1:dir:`).
Background and the rule-by-rule mapping:
[`docs/release-management/reproducibility.md`](../../../../docs/release-management/reproducibility.md).

**When it runs.** `reproducibility_source: on` (the default with `source_archive_method: git-archive`) or `reproducibility_binaries` not `off`.
`--skip-repro` skips it and the report says so.
🪶 ASF-specific: when `release-management-config.md` sets `automated_release_signing: enabled` (only meaningful under `organization: ASF`)
the step is **mandatory** and `--skip-repro` is ignored —
this run *is* the validation on trusted hardware that
[Infra § Automated release signing](https://infra.apache.org/release-signing.html#automated-release-signing)
requires before publication, and the bar is byte-identical.

**Run.** One command decides whether the step runs, renders the recipe, and rolls the results up
(`<verify-rc>` as in SKILL.md):

```bash
<verify-rc> repro [--skip-repro] [--trusted-hardware] --upstream-clone <upstream-clone> --remote <remote> --staged-dir <staged-dir>
```

Its `paste_recipe` resolves every placeholder but the recorded values:
the tag check (`git rev-parse "<rc-tag>^{commit}"`, `git tag -v`), `repro-archive check --json` against the recorded epoch and `swh:1:dir:`,
the rebuild (`repro-archive build` at the tag with the recorded epoch, prefix and format, or the adopter's `build_command` under `source_archive_method: custom`,
run inside the clone and copied from `<build-output>` — the directory the build writes the source artefact to, which the voter fills in — to `rebuilt/` so the comparison reads it),
`repro-archive compare --json` (`--require-identical` under automated signing),
and one rebuild-and-compare per convenience artefact by its own `reproducibility` mode
(`release-build.md § Convenience artefacts`, project-specific: a registry-staged image is pulled by digest — say which digest was pulled).
Run it on the voter's own machine, save each JSON, and re-run the command with the results:

```bash
<verify-rc> repro … --recorded-commit <sha> --tag-commit <rev-parse output> --epoch <recorded SOURCE_DATE_EPOCH> \
  [--recorded-swhid <swh:1:dir:…>] [--atr-swhid <swh:1:dir:…>] --check <check.json> --compare <compare.json> \
  [--binary <artefact>=identical|differs|known:<the known_divergences pattern it hit>]…
```

The rules it applies:

| Source result | RM-key mode | `automated_release_signing: enabled` |
|---|---|---|
| `identical` | `PASS` | `PASS` |
| `content-identical` (same members and bytes, archive metadata differs) | `WARN` — the RM did not build with `repro-archive build` | `FAIL` — the policy requires bit-by-bit identity |
| `differs` (members added / removed / changed) | `FAIL` — the artefact is not the tagged tree | `FAIL` |
| tag commit ≠ recorded commit (`verdict: tag-moved`) | `FAIL` — the tag moved | `FAIL` |
| content `swh:1:dir:` ≠ recorded (or ≠ ATR's), qualifiers ignored | `FAIL` — the staged tree is not the recorded one, whatever the bytes | `FAIL` |
| `check` reports another rule `FAIL` | `WARN`, listed | `FAIL` |

Per convenience artefact, by its own mode: `byte-identical` — any difference is `FAIL`;
`documented-divergence` — a difference matching its `known_divergences` is `WARN` and listed, any other is `FAIL`;
`off` — `SKIP` for that artefact, stated with the note that it is being published on trust.
For a voter this is the check that decides whether a convenience artefact is *good*: a binary cannot be reviewed, only rebuilt from the tag and compared.

Do not post-filter any output; the voter sees every difference.
Never report a verdict the commands did not produce: until every result is in, `status` is `null` and `pending` names what is missing.
`mandatory` is `true` only under `automated_release_signing: enabled`; `binaries.mode` is the strictest mode in use.
`trusted_hardware_asserted` mirrors `--trusted-hardware`; the skill never sets it on its own.
`binaries.differs` names every convenience artefact that did not reproduce —
`release-promote` reads this list and withholds the publish command for each of them.
`swhid_matches` is `null` when the planning issue recorded no SWHID — then the report states the computed value (in `notes`) so the RM can add it.

Return ONLY valid JSON with this structure (the command's output without `findings`, `notes` and `pending`):

```json
{
  "step": "reproducibility",
  "status": "PASS" | "WARN" | "FAIL" | "SKIP",
  "mandatory": true | false,
  "source": {
    "enabled": true | false,
    "verdict": "identical" | "content-identical" | "differs" | "tag-moved" | null,
    "recorded_commit": "<sha or null>",
    "source_date_epoch": <integer or null>,
    "swhid_dir": "<swh:1:dir:… computed from the staged archive, or null>",
    "swhid_matches": true | false | null,
    "rule_failures": ["<check name>"],
    "metadata_differences": ["<string>"],
    "content_differences": ["<added/removed/changed path>"]
  },
  "binaries": {
    "mode": "off" | "byte-identical" | "documented-divergence",
    "identical": ["<artefact>"],
    "differs": ["<artefact>"],
    "known_divergences_hit": ["<artefact>: <pattern>"]
  },
  "trusted_hardware_asserted": true | false,
  "paste_recipe": "<multi-line shell commands>"
}
```
