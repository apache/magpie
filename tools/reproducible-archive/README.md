<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`reproducible-archive`](#reproducible-archive)
  - [The rules it implements](#the-rules-it-implements)
  - [Prerequisites](#prerequisites)
  - [How to use](#how-to-use)
    - [`build` — a source archive that is a function of the tag alone](#build--a-source-archive-that-is-a-function-of-the-tag-alone)
    - [`check` — lint an archive against the checklist](#check--lint-an-archive-against-the-checklist)
    - [`compare` — did the voter get the same bytes?](#compare--did-the-voter-get-the-same-bytes)
    - [`recipe` — the same steps with GNU tar / Info-ZIP](#recipe--the-same-steps-with-gnu-tar--info-zip)
    - [`epoch` — the `SOURCE_DATE_EPOCH` of a ref](#epoch--the-source_date_epoch-of-a-ref)
  - [Embedding the script](#embedding-the-script)
  - [Wiring](#wiring)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `reproducible-archive`

**Capability:** substrate:release

**Harness:** agnostic

Builds, lints and compares **reproducible source archives**.
The archive is always derived from `git archive <ref>`, so only tracked files at the tag are packed and the repository's `.gitattributes` `export-ignore` rules decide what stays out.
On top of that stream the tool applies every rule from [reproducible-builds.org § Archive metadata](https://reproducible-builds.org/docs/archives/), so a Release Manager and a voter on different machines, with different `git`, `tar`, `zip` and `gzip` versions, get **byte-identical** output from the same tag.

This is what `release-rc-cut` emits for the source artefact, what `release-verify-rc`'s reproducibility step rebuilds and compares against the staged RC, and what an ASF adopter needs before it can request [automated release signing](https://infra.apache.org/release-signing.html#automated-release-signing) (which requires artefacts that "can be built reproducibly" and are re-validated "bit-by-bit identical" on trusted hardware).
See [`docs/release-management/reproducibility.md`](../../docs/release-management/reproducibility.md) for how the pieces fit.

## The rules it implements

| # | reproducible-builds.org rule | Standard-tool equivalent | What the module does |
|---|---|---|---|
| 1 | File modification times | `tar --mtime="@${SOURCE_DATE_EPOCH}"`, `touch --date="@${SOURCE_DATE_EPOCH}"` | Every member gets one mtime: `SOURCE_DATE_EPOCH`, defaulting to the committer timestamp of the ref (`git log -1 --format=%ct`), the one value every builder of the same tag agrees on. |
| 2 | File ordering | `tar --sort=name`, or `find … \| LC_ALL=C sort -z` | Members are emitted in per-directory byte order, independent of the packer's locale and filesystem. |
| 3 | Ownership | `--owner=0 --group=0 --numeric-owner` | uid/gid `0`, empty user and group names. |
| 4 | Permissions / umask | `--mode=a=rX,u+w` | Files `0644`, executables and directories `0755`, setuid/setgid/sticky dropped. |
| 5 | PAX headers | `--pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime` | No `atime` / `ctime` headers; `check` also catches the PID-bearing `PaxHeaders.<pid>` names GNU tar emits under `POSIXLY_CORRECT`. |
| 6 | gzip | `gzip -n` | gzip header mtime `0`, no embedded filename, no extra field, no comment. |
| 7 | zip extra attributes | `zip -X`, unzip with `TZ=UTC` | No "extra field" per member, no comments, DOS timestamps computed in UTC from `SOURCE_DATE_EPOCH`, Unix create-system so the normalised modes round-trip. |

`ar` deterministic mode (`ARFLAGS=Dcvr`, `ranlib -D`) and `cpio` are the same page's rules for *binary* artefacts; they belong in the adopter's build command, not here — `release-build.md § Reproducibility checks` records how the project applies them.

## Prerequisites

- **Runtime:** Python 3.11+ (stdlib only, no third-party dependencies); run via `uv run --project tools/reproducible-archive` or as a plain `python3 <file>`.
- **CLIs:** `git` on `PATH` for `build` and `epoch`; `check`, `compare` and `recipe` work on archive files alone.
- **Credentials / auth:** None.
- **Network:** None — runs fully offline on the local clone and local archive files.

## How to use

From the framework root (`<framework>` is `.apache-magpie/` in an adopting project, `.` in the framework checkout):

```bash
uv run --project <framework>/tools/reproducible-archive repro-archive --help
```

or, with no `uv` at all:

```bash
python3 <framework>/tools/reproducible-archive/src/reproducible_archive/__init__.py --help
```

### `build` — a source archive that is a function of the tag alone

```bash
repro-archive build --ref 2.11.0-rc1 --format tar.gz \
    --prefix apache-foo-2.11.0 -o apache-foo-2.11.0-source.tar.gz
# wrote apache-foo-2.11.0-source.tar.gz
# commit 1890a13d…
# SOURCE_DATE_EPOCH 1758326400
# sha512 …
```

`--format zip` produces the ZIP equivalent. `--epoch N` overrides `SOURCE_DATE_EPOCH` (the environment variable is honoured too); the default is the committer timestamp of `--ref`. The command refuses to run outside a git repository, refuses a ref it cannot resolve, and refuses a ZIP for an epoch before 1980 (the DOS timestamp cannot encode it).

Record the printed `commit`, `SOURCE_DATE_EPOCH` and `sha512` in the planning issue: a voter needs the first two to rebuild and the third to compare.

### `check` — lint an archive against the checklist

```bash
repro-archive check apache-foo-2.11.0-source.tar.gz --epoch 1758326400
# PASS gzip-header          mtime 0, no filename (gzip -n)
# PASS file-ordering        members are in per-directory byte order
# PASS modification-times   single mtime 1758326400
# PASS ownership            uid/gid 0, no user/group names
# PASS permissions          every mode is a=rX,u+w
# PASS pax-headers          no atime/ctime/PID headers
# SKIP zip-extra-fields     not a zip
```

Exit code `1` on any `FAIL`. `--json` prints the same table as a list of `{name, status, detail}`. `--epoch` additionally asserts the single mtime *is* the expected `SOURCE_DATE_EPOCH`; without it the check only requires that every member share one mtime. It works on any `.tar`, `.tar.gz` or `.zip`, not only ones this tool built, so it doubles as a lint for an archive produced by a project's own build.

### `compare` — did the voter get the same bytes?

```bash
repro-archive compare staged/apache-foo-2.11.0-source.tar.gz rebuilt.tar.gz --require-identical
```

Three verdicts, in decreasing strength:

| Verdict | Meaning | Exit code |
|---|---|---|
| `identical` | Byte-for-byte the same file. The bar ASF automated release signing sets for validation on trusted hardware. | `0` |
| `content-identical` | Every member's bytes, type, normalised mode and link target match; only archive metadata differs (timestamps, owners, ordering, extra fields, compression). What a voter gets from a plain `git archive` with a different `git` version. The metadata differences are listed. | `0`, or `1` with `--require-identical` |
| `differs` | Members were added, removed or changed; each is listed. The artefact does not match the tag. | `2` |

`--json` prints the `Comparison` record.

### `recipe` — the same steps with GNU tar / Info-ZIP

```bash
repro-archive recipe --ref 2.11.0-rc1 --format tar.gz --prefix apache-foo-2.11.0 -o apache-foo-2.11.0-source.tar.gz
```

Prints the shell recipe from reproducible-builds.org (GNU tar ≥ 1.28 and `gzip -n`, or `LC_ALL=C sort` + `zip -X` under `TZ=UTC`) adapted to a `git archive` input, for a Release Manager who prefers to run the standard tools. It ends with the `check` invocation that verifies the result. The Python path and the shell path apply the same rules; only the Python path is guaranteed byte-identical across tool versions.

### `epoch` — the `SOURCE_DATE_EPOCH` of a ref

```bash
SOURCE_DATE_EPOCH="$(repro-archive epoch --ref 2.11.0-rc1)"
```

Use it to feed the same timestamp into a binary build (`SOURCE_DATE_EPOCH` is honoured by most build tools that embed dates) so the binary reproducibility check in `release-verify-rc` has a fixed reference.

## Embedding the script

`src/reproducible_archive/__init__.py` is a single stdlib-only file with a `__main__` guard. Copy it verbatim into a CI workflow, a release script, or a project that does not adopt the rest of Magpie:

```bash
python3 reproducible_archive.py build --ref "$GITHUB_REF_NAME" --prefix "apache-foo-${VERSION}" \
    --format tar.gz -o "apache-foo-${VERSION}-source.tar.gz"
```

The ASF automated-release-signing workflow template in [`projects/_template/workflows/release-candidate.yml`](../../projects/_template/workflows/release-candidate.yml) does exactly that.

## Wiring

- `release-rc-cut` Step 2 emits `repro-archive build` as the source-artefact build command whenever `release-build.md § Source archive` sets `source_archive_method: git-archive` (the default), and Step 2b emits the optional `check` + rebuild-and-`compare` self-check.
- `release-verify-rc` Step 9 rebuilds from the tag with `build` and runs `compare` against the staged artefact; `--require-identical` when the adopter has `automated_release_signing: enabled`.
- The workspace pre-commit hooks (`ruff`, `mypy`, `pytest`) pick the project up from the root `pyproject.toml` `[tool.uv.workspace] members` list.

## Tests

```bash
uv run --project tools/reproducible-archive python -m pytest
```

Every rule has a positive case (the builder applies it) and a negative case (`check` catches an archive that violates it); `compare` is exercised on all three verdicts; and `build` is shown to be a function of the tag alone: two builds at different wall-clock times under a different umask are byte-identical.
