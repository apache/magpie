<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2e — the source-archive contents review

Loaded from [`prep.md`](prep.md) § 2e when `prepare archive-mode` printed `mode: "full"` or `"drift"`.

With `source_archive_method: git-archive` (the default in `release-build.md § Source archive`)
the source artefact is an export of the tagged tree that honours `.gitattributes` `export-ignore`.
The attributes are read from the tree being archived, so they have to be committed **before** the RC tag —
which is why this review lands in the prep PR and why `release-rc-cut` blocks while it is outstanding.
Full rationale and the classification buckets:
[`docs/release-management/reproducibility.md` § The first-release `.gitattributes` review](../../../../docs/release-management/reproducibility.md#the-first-release-gitattributes-review).

**When the full review runs:** `export_ignore_reviewed` is unset in `release-build.md`, or `--review-archive` was passed,
or `source_archive_method` is `git-archive` and the file has no `§ Source archive` at all (`mode: "full"`).
**Otherwise** run only the drift check (`mode: "drift"`, below).

This is an **education step**: the operator ends up knowing why every top-level path ships or does not.
Do not guess; show, classify, explain, and ask.

1. **List what would ship today** from the local clone at the release branch tip, and what is tracked:
   run the `commands` `archive-mode` printed there (read-only `git` listings into `$TMPDIR`).
   With no local clone (`user.md` names none), stop 2e and ask the RM to set the clone path or clone and rerun `prep`.

2. **Classify every top-level entry** into one bucket and say which:

   ```bash
   prepare archive-review --tracked "$TMPDIR/tracked.txt" --gitattributes <clone>/.gitattributes \
     --symlinks "$TMPDIR/symlinks.txt" --load <scratch>/prepare-load.json [--voter-input <path> ...]
   ```

   `entries` is the bucket table: *ship* (source, docs, build descriptors, lock files, `README*`),
   *ship, never excludable* (`LICENSE`, `NOTICE`, `DISCLAIMER`, `licenses/`), *ship, input to voter checks* (RAT excludes, in-tree validators),
   *project's call* (`.asf.yaml`, `doap_*.rdf`, `.gitignore`), the *exclude* buckets (VCS metadata, CI / bot config, editor / IDE,
   lint config not needed to build, release-tooling scratch), and the *agent-view dirs* (`.claude/`, `.agents/`, `.kiro/`, `.cursor/`).
   `.github/` and the agent-view dirs are classified one level down (`inside`):
   part of a directory may ship (issue templates a shipped skill links to) while the rest is excluded,
   and an agent-view relay dir (its symlinks chain through another symlink) is excluded while a single-hop canonical view stays when shipped files link into it.
   Every `needs_rm` entry — *project's call*, large assets, anything `unclassified` — is the RM's decision: explain the trade-off and ask.

3. **Check references before proposing any exclusion**: run the printed `refs_command` (one `git grep -l -F` per proposed entry over tracked files)
   and rerun `archive-review` with `--refs "$TMPDIR/refs.txt"`.
   `refs_unchecked` lists every proposed path the refs file does not cover (one added later with `--exclude`, say);
   while it is non-empty, `gitattributes_block` stays empty and `refs_command` checks exactly those paths, appending to the same refs file: run it and rerun with that file.
   A path that a shipped file links to must not be excluded, or `release-verify-rc` Step 7 fails the RC on a dangling reference:
   `refused` names the referrers; offer the alternative (keep it, or repoint the reference).
   A reference from a file that is itself excluded does not count, unless that file's own exclusion is refused.
   `stripped_symlink_targets` is every committed symlink whose target would be stripped,
   and `symlink_chains` every shipped symlink that points at another symlink (safe extractors reject chains); flag each.

4. **Propose the entries** — `gitattributes_block` holds them root-anchored (`/.pre-commit-config.yaml`) for root-only files,
   directory form (`.idea/`) for directories, one rationale comment per entry (`--reason <path>=<why>` replaces it) —
   and show the before/after listing diff with `before_after_commands` (`removed` = exactly what the review strips).
   Walk the RM through each proposed entry; each one is confirmed or dropped individually,
   and the final render takes the RM's answers as `--exclude <path>` (added) and `--keep <path>` (dropped).
   Never exclude `LICENSE`, `NOTICE`, `DISCLAIMER`, a build descriptor, the RAT excludes, or a referenced path, even if asked — say why and keep it
   (`refused` already holds them, and any glob pattern: name each path instead).
   `violations` lists every entry the committed `.gitattributes` already has that strips one of those files (`matches` names them):
   the review is not clean while one remains.
   Show each to the RM, remove the line from `.gitattributes` in the prep PR,
   and record it as `--archive-review proposed` with `--archive-entry "<entry>=removed: <why>"`.

5. **Record the decision.** `.gitattributes` joins the prep PR file set (2f),
   and the prep PR sets `export_ignore_reviewed: <version>` in `release-build.md § Source archive` so the full review does not repeat:
   pass `--archive-review proposed` and one `--archive-entry "<entry>=<reason>"` per confirmed entry to `prep-pr`.
   If the RM confirms an existing `.gitattributes` unchanged, still set the marker (`archive_review: "confirmed-existing"`).

**Drift check (later releases).** Run the `commands` `archive-mode` printed
(`git diff --name-only <previous-tag> HEAD` into `$TMPDIR/changed.txt`, plus `tracked.txt` and `symlinks.txt`),
then `archive-review` with `--changed "$TMPDIR/changed.txt"` and the same inputs.
A `violations` entry blocks the skip in the drift check too.
Top-level entries added since the last reviewed tag that fall in an *exclude* bucket are surfaced as candidates with the same confirm-each flow;
nothing new → `archive_review: "skipped"` with the note *"no new top-level paths since `<previous-tag>`"*.
