<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 9 — Reproducibility checks (optional)

Confirm the staged artefacts are a function of the tag alone.
Read `release-build.md § Source archive` and `§ Reproducibility checks`,
and the reproducibility record `release-rc-cut` left on the planning issue (source commit, `SOURCE_DATE_EPOCH`, sha512, format, prefix).
Background and the rule-by-rule mapping:
[`docs/release-management/reproducibility.md`](../../../../docs/release-management/reproducibility.md).

**When it runs.** `reproducibility_source: on` (the default with `source_archive_method: git-archive`) or `reproducibility_binaries` not `off`.
`--skip-repro` skips it and the report says so.
🪶 ASF-specific: when `release-management-config.md` sets `automated_release_signing: enabled` (only meaningful under `organization: ASF`)
the step is **mandatory** and `--skip-repro` is ignored —
this run *is* the validation on trusted hardware that
[Infra § Automated release signing](https://infra.apache.org/release-signing.html#automated-release-signing)
requires before publication, and the bar is byte-identical.

**Source.** Emit the paste-ready recipe
(`<framework>` is `.apache-magpie` in an adopting project, `.` in the framework checkout;
`python3 <framework>/tools/reproducible-archive/src/reproducible_archive/__init__.py` works without `uv`):

```bash
# 1. The tag resolves to the commit recorded on the planning issue
git -C <upstream-clone> fetch --tags <remote>
git -C <upstream-clone> rev-parse "<rc-tag>^{commit}"          # expect: <recorded commit>
git -C <upstream-clone> tag -v "<rc-tag>"                       # signed tag verifies against KEYS

# 2. The staged archive satisfies every reproducible-builds.org rule, and its
#    content is the recorded tree (the swh:1:dir: on the planning issue — and,
#    under ATR, the SWHID the candidate page shows)
uv run --project <framework>/tools/reproducible-archive repro-archive check \
  "<staged-source-artefact>" --epoch "<recorded SOURCE_DATE_EPOCH>" \
  --swhid "<recorded swh:1:dir:…>"

# 3. Rebuild from the tag with the recorded epoch, prefix and format, then compare
uv run --project <framework>/tools/reproducible-archive repro-archive build \
  --repo <upstream-clone> --ref "<rc-tag>" --format <source_archive_format> \
  --prefix "<source_archive_prefix>" --epoch "<recorded SOURCE_DATE_EPOCH>" \
  -o rebuilt/<source-artefact-filename>
uv run --project <framework>/tools/reproducible-archive repro-archive compare \
  "<staged-source-artefact>" rebuilt/<source-artefact-filename>   # add --require-identical under automated signing
```

With `source_archive_method: custom`, step 3 re-runs the adopter's `build_command` at the tag under the recorded `SOURCE_DATE_EPOCH`
and compares its output the same way.

Classify the source result:

| `compare` verdict | RM-key mode | `automated_release_signing: enabled` |
|---|---|---|
| `identical` | `PASS` | `PASS` |
| `content-identical` (same members and bytes, archive metadata differs) | `WARN` — the RM did not build with `repro-archive build`; note the metadata differences | `FAIL` — the policy requires bit-by-bit identity |
| `differs` (members added / removed / changed) | `FAIL` — the artefact is not the tagged tree | `FAIL` |
| tag commit ≠ recorded commit | `FAIL` — the tag moved | `FAIL` |
| content `swh:1:dir:` ≠ recorded (or ≠ ATR's) | `FAIL` — the staged tree is not the recorded one, whatever the bytes | `FAIL` |
| `check` reports another rule `FAIL` | `WARN`, listed | `FAIL` |

**Convenience artefacts.** Read `convenience_artefacts` from `release-build.md § Convenience artefacts`
(project-specific; an empty list means `SKIP`, stated explicitly).
For a voter this is the check that decides whether a convenience artefact is *good*:
a binary cannot be reviewed, so the only way to establish that it is what the voted source produces is to rebuild it from the tag and compare.
Per artefact, using its own `reproducibility` mode (default `reproducibility_binaries`):

- `byte-identical` — rebuild with the entry's `build_command` under the recorded `SOURCE_DATE_EPOCH`, compare with `cmp`;
  any difference is `FAIL`.
- `documented-divergence` — rebuild, run the entry's `verification_command` (for example `diffoscope`);
  differences that match its `known_divergences` are `WARN` and listed, any other difference is `FAIL`.
- `off` — `SKIP` for that artefact, stated explicitly with the note that it is being published on trust.

```bash
export SOURCE_DATE_EPOCH="<recorded SOURCE_DATE_EPOCH>"
git -C <upstream-clone> checkout "<rc-tag>"
# one block per convenience artefact, its build_command verbatim:
( cd <upstream-clone> && <artefact.build_command> )
cmp "<staged-dir>/<artefact.name>" "<upstream-clone>/<build-output>/<artefact.name>" \
  && echo "identical: <artefact.name>" || echo "DIFFERS: <artefact.name>"
# documented-divergence entries instead:
<artefact.verification_command> "<staged-dir>/<artefact.name>" "<upstream-clone>/<build-output>/<artefact.name>"
```

Container images and other registry-staged kinds (`staging: registry-staging`) are pulled by digest from the staging registry
and compared the same way against the local rebuild; say which digest was pulled.

Do not post-filter any output; the voter sees every difference.
Never report a verdict the commands did not produce.

Return ONLY valid JSON with this structure:

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

`status` is `"FAIL"` per the table above, `"WARN"` when only warnings occurred,
`"SKIP"` when nothing was enabled or `--skip-repro` applied, else `"PASS"`.
`mandatory` is `true` only under `automated_release_signing: enabled`.
`trusted_hardware_asserted` mirrors `--trusted-hardware`; the skill never sets it on its own.
`binaries.mode` is the mode applied (when entries differ, the strictest one in use);
`binaries.differs` names every convenience artefact that did not reproduce —
`release-promote` reads this list and withholds the publish command for each of them.
`swhid_matches` is `true` when the staged archive's `swh:1:dir:` equals the recorded one (qualifiers ignored),
`false` when it does not (a `FAIL`),
`null` when the planning issue recorded no SWHID — then the report states the computed value so the RM can add it.
