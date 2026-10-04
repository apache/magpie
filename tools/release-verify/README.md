<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`release-verify`](#release-verify)
  - [Prerequisites](#prerequisites)
  - [How to use](#how-to-use)
    - [Output](#output)
  - [Wiring](#wiring)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# `release-verify`

**Capability:** substrate:release

**Harness:** agnostic

Deterministic, read-only checks of a staged release candidate, one subcommand per mechanical step of the [`release-verify-rc`](../../plugins/magpie-release-management/skills/verify-rc/SKILL.md) skill.
Each prints one JSON object; the skill reads it and reports.
The rules are the skill's, implemented once in code so the model does not re-derive them from prose on every run.
Judgement stays with the reader: whether a NOTICE / LICENSE diff is material, and whether the project's own source-tree validators passed, come back as status `REVIEW`.

Guarantees: nothing is written outside a throwaway `GNUPGHOME`; the user's keyring is never read or changed; nothing is signed; a `KEYS` file containing private-key material is refused; nothing touches the network — the caller downloads the staged files and `KEYS` first.

## Prerequisites

- **Runtime:** Python 3.11+ (stdlib only); run via `uv run --project tools/release-verify` or as a plain `python3 <framework>/tools/release-verify/src/release_verify/__init__.py`.
- **CLIs:** `gpg` (GnuPG 2.2+) on `PATH` for `signatures` and `all`; every other subcommand works on local files alone. No `gpg-agent` is needed — verification uses public keys only.
- **Credentials / auth:** None.
- **Network:** None — runs fully offline on a local copy of the staging directory, the `KEYS` file and the unpacked source artefact.

## How to use

From the framework root (`<framework>` is `.apache-magpie/` in an adopting project, `.` in the framework checkout).
`<staging>` is a local copy of the staged RC directory (e.g. `svn export <staging-url> <staging>`), `KEYS` a local copy of the project `KEYS` file, `<tree>` the unpacked source artefact.
Patterns and paths come from the adopter's `release-build.md` and `release-management-config.md`.

```bash
RV="uv run --project <framework>/tools/release-verify release-verify"

$RV inventory  --dir <staging> --expect '<pattern>'... [--expect-optional '<pattern>']... --digest sha512 [--digest sha256]
$RV signatures --dir <staging> --expect '<pattern>'... [--expect-optional '<pattern>']... --keys KEYS --keys-url <keys-url> [--extra-key <signer.pub>]
$RV checksums  --dir <staging> --expect '<pattern>'... [--expect-optional '<pattern>']... --digest sha512 [--digest sha256]
$RV notice-license --tree <tree> [--previous <dir with the previous release's NOTICE and LICENSE>]
$RV binaries   --tree <tree> [--prohibit '<glob>']... [--accept '<glob>']...
$RV symlinks   --tree <tree> [--validator '<command>']...
$RV version    --tree <tree> --rc-tag <version>-rcN --manifest <path>[=<regex>]...
$RV verdict    <step.json>... [--status <step>=PASS|WARN|FAIL|SKIP]...
$RV all        --dir <staging> --tree <tree> <the options above> [--status <step>=<status>]...
```

`--expect` takes each artefact `release-build.md § Expected artefact list` marks `required` (the default), `--expect-optional` each one it marks `optional`; `signatures` and `checksums` check every staged artefact of either kind.
`inventory` also takes `--listing` (a file of names, e.g. `svn ls <staging-url>` output) in place of `--dir`. `--keys-url` is only printed in the voter's `paste_recipe`.
Exit status is `0` whenever a JSON result is printed, whatever the verdict; `2` with `{"error": …}` for unusable input.

### Output

Every step object carries `step`, `status` and the step's fields as the skill's hand-back schema names them, plus a few extra diagnostic fields (marked † below).

| Subcommand | `step` | `status` | Fields |
|---|---|---|---|
| `inventory` | `inventory` | `FAIL` a required pattern unmatched · `WARN` an optional pattern unmatched, or an unexpected entry · else `PASS` | `found`, `missing` (required patterns), `missing_optional`†, `unexpected`, `source`† |
| `signatures` | `signatures` | `PASS` only when every artefact is `PASS`, else `FAIL` | `results[]` (`file`, `sig_file`, `classification` `PASS` / `KEY-NOT-IN-KEYS` / `FAIL`, `fingerprint`, `key_in_keys`, `detail`†), `keys_fingerprints`†, `paste_recipe` |
| `checksums` | `checksums` | `FAIL` a sha512 `MISSING-DIGEST`, or a `MISMATCH` on any digest but md5 · `WARN` a `.md5` file is present (matching or not) · else `PASS` | `results[].digests[]` (`type`, `classification`, `detail`†), `deprecated_md5_present`, `paste_recipe` |
| `notice-license` | `notice-license` | `FAIL` either file absent from the RC artefact · `PASS` no previous release, or both diffs empty · else `REVIEW` | `notice_present`, `license_present`, `notice_diff_lines`, `license_diff_lines`, `notice_diff`†, `license_diff`†, `previous`†, `detail`† (on `FAIL`: which file the current RC artefact lacks) |
| `binaries` | `binary-exclusion` | `FAIL` when `prohibited_found` is non-empty | `prohibited_found`, `expected_binaries`, `paste_recipe` |
| `symlinks` | `source-tree-integrity` | `FAIL` a symlink that dangles or resolves outside the archive · `REVIEW` validators declared (run them) · `PASS` symlinks, all resolve inside · `SKIP` no symlinks, no validators | `dangling_symlinks`, `outside_symlinks`†, `symlinks_present`†, `validator_failures` (always `[]`), `validators_to_run`†, `paste_recipe` |
| `version` | `version-consistency` | `FAIL` any `extracted` is `null` or differs from the expected version | `expected_version`, `results[]` (`file`, `extracted`, `match`, `detail`†) |
| `verdict` | `verdict` | — | `overall` (`FAIL` > `PASS-WITH-WARNINGS` > `PASS`; `null` while a step is unresolved), `step_summary`, `fail_steps`, `warn_steps`, `skip_steps`, `unresolved`, `ignored_overrides`† |

Rules the subcommands apply:

- **Signatures.** The `KEYS` file is imported into a temporary `GNUPGHOME` with no agent, keyboxd or key retrieval. `PASS` when `gpg --verify` exits 0 and the signing key (primary or subkey fingerprint) is in `KEYS`. `KEY-NOT-IN-KEYS` when the signature is good but the key is not in `KEYS`; telling that apart needs the signer's public key, passed with `--extra-key` (never a trust anchor). Without it such a signature cannot be checked and is `FAIL` with `detail` naming the missing key. A missing `.asc` is `FAIL`.
- **Inventory.** A missing required artefact is `FAIL`; a missing optional one is `WARN` (listed in `missing_optional`), never `FAIL`.
- **Checksums.** Only `sha512` is required: a missing `.sha512` is `MISSING-DIGEST`, a `FAIL`. Every other digest (`sha256`, whether or not passed as `--digest`) is optional — checked when its file is staged, absent otherwise without effect — and a `MISMATCH` on one still `FAIL`s. md5 never fails alone: a `.md5` file, matching or mismatched, is listed and makes the step `WARN`. Digest files in `sha512sum`, BSD-tag (`SHA512 (f) = …`) and `gpg --print-md` layouts are read; an unparsable one is a `MISMATCH` with `detail`.
- **Binaries.** Fixed baseline `*.class`, `*.jar`, `*.so`, `*.dylib`, `*.dll`, `*.exe`, `*.pyc` (files) and `__pycache__` (directories), plus every `--prohibit` glob. A hit matching an `--accept` glob is `expected_binaries`, any other is `prohibited_found`; `.pyc` and `__pycache__` are always prohibited. A glob without `/` matches the file name (`find -name`), one with `/` the path inside the tree (`find -path`, `**` = `*`).
- **Notice / licence.** On `FAIL`, `detail` names the file the current RC artefact lacks; the diff counts are `null` because there is nothing to diff, not because a previous release is missing.
- **Symlinks.** Every symlink must resolve to an existing path inside the unpacked archive. One whose target does not exist is dangling; one that resolves outside the archive (`..` past the root, an absolute path, or a chain through either) is listed in `outside_symlinks` and also `FAIL`s, even when the target exists. `paste_recipe` repeats both checks with `realpath`. Validators are printed in `paste_recipe`, never run.
- **Version.** `--rc-tag` drops the `-rcN` suffix. Built-in extraction for `setup.cfg` (`[metadata] version`), `pyproject.toml` (`[project]` or `[tool.poetry]`), `*.py` (`__version__ = "…"`; `version="…"` in `setup.py`), `pom.xml` (`<project><version>`), `package.json`, `Cargo.toml`, `*.properties`, `build.gradle(.kts)`, `Chart.yaml`, `VERSION` / `version.txt`. Anything else needs `PATH=REGEX` (first group). Dynamic versions (`attr:`, `dynamic = ["version"]`) are `null`.
- **Verdict.** A status the tool computed is final; `--status` only fills a step it did not run (`rat-license-headers`, `reproducibility`) or resolves a `REVIEW`. `SKIP` neither passes nor warns, and `skip_steps` lists every skipped step so the report names it.

## Wiring

- `release-verify-rc` Steps 1–3 and 5–8 run the matching subcommand, and Step 10 runs `verdict` (or the skill runs `all` once). Step 4 (Apache RAT) is build-system specific and Step 9 uses [`reproducible-archive`](../reproducible-archive/README.md); both report their status into `verdict` with `--status`.
- The workspace pre-commit hooks (`ruff`, `mypy`, `pytest`) pick the project up from the root `pyproject.toml` `[tool.uv.workspace] members` list.

## Tests

```bash
uv run --project tools/release-verify python -m pytest
```

Every subcommand is exercised on its pass case and on each failure class the skill names.
The signature tests use static fixtures in `tests/fixtures/gpg/` — public keys and detached signatures only, written by `generate.py` without `gpg-agent` — so they need `gpg` but run in a sandbox; they skip cleanly when `gpg` is absent.
One further test generates a throwaway key in a temporary `GNUPGHOME` and skips where no agent can start.
