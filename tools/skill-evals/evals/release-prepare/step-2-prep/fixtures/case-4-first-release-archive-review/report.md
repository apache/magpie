<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pre-flight passed. Sub-command: prep. Version: 1.0.0 — the project's FIRST release.
Planning issue: apache/foo#12 (labelled release-planning, title "Release Apache Foo 1.0.0")
PR set: 40 PRs (from planning issue body).
Previous tag: (none — first release). Release branch base: main.

version_manifest_files: pyproject.toml
  pyproject.toml current version: 1.0.0.dev0
Target version: 1.0.0

category_x_dependencies: (empty list — no Category-X check needed)
NOTICE: new file, standard ASF text. LICENSE: Apache-2.0, no bundled deps.
Changelog: 40 PRs, all categorised. Coverage: 100%.

release-build.md § Source archive:
  source_archive_method: git-archive, source_archive_format: tar.gz,
  source_archive_prefix: apache-foo-1.0.0
  export_ignore_reviewed: (unset)  → the full source-archive contents review is due.
Root .gitattributes: absent.

Local clone at main. Top-level tracked entries and the RM's answers in the
guided review (each entry confirmed individually):
  LICENSE, NOTICE, README.md, pyproject.toml, uv.lock, src/, docs/, tests/  → ship
  .rat-excludes            → ship (input to the RAT check voters run)
  .asf.yaml                → ship (ASF project metadata; RM's call)
  .gitignore               → ship (dev-environment config; RM's call)
  .gitattributes           → exclude (VCS metadata)
  .pre-commit-config.yaml  → exclude (dev tooling)
  .github/workflows/       → exclude (CI); .github/ISSUE_TEMPLATE/ ships — docs/CONTRIBUTING.md links to it (git grep hit)
  .idea/                   → exclude (editor state)
  .ruff.toml, .yamllint    → exclude (lint config not needed to build)
No committed symlinks. Before/after listing diff: 6 paths removed, all in
the excluded set; no shipped file references a removed path.

Draft the prep PR. Propose it to the RM — do not open the PR yet.

Output of `release-management prepare archive-mode --load <scratch>/prepare-load.json`:

```json
{
  "mode": "full",
  "reason": "export_ignore_reviewed is unset in release-build.md",
  "export_ignore_reviewed": null,
  "commands": "git archive --format=tar HEAD | tar -tf - | sort > \"$TMPDIR/would-ship.txt\"\ngit ls-files > \"$TMPDIR/tracked.txt\"\ngit ls-files -s | awk -F'\\t' '$1 ~ /^120000 / {print $2}' | while IFS= read -r p; do printf '%s -> %s\\n' \"$p\" \"$(readlink \"$p\")\"; done > \"$TMPDIR/symlinks.txt\""
}
```

Output of the final `release-management prepare archive-review --tracked "$TMPDIR/tracked.txt" --gitattributes <clone>/.gitattributes --symlinks "$TMPDIR/symlinks.txt" --refs "$TMPDIR/refs.txt" --load <scratch>/prepare-load.json --exclude .ruff.toml --keep .asf.yaml --keep .gitignore --reason .ruff.toml="lint config not needed to build"` (after the RM's answers):

```json
{
  "mode": "full",
  "entries": [
    {
      "path": ".asf.yaml",
      "bucket": "project's call",
      "directory": false,
      "already_excluded": false
    },
    {
      "path": ".github",
      "bucket": "split: look inside",
      "directory": true,
      "inside": [
        {
          "path": ".github/ISSUE_TEMPLATE",
          "bucket": "ship",
          "directory": true,
          "already_excluded": false
        },
        {
          "path": ".github/workflows",
          "bucket": "exclude: CI / bot config",
          "directory": true,
          "already_excluded": false
        }
      ],
      "already_excluded": false
    },
    {
      "path": ".gitignore",
      "bucket": "project's call",
      "directory": false,
      "already_excluded": false
    },
    {
      "path": ".idea",
      "bucket": "exclude: editor / IDE",
      "directory": true,
      "already_excluded": false
    },
    {
      "path": ".pre-commit-config.yaml",
      "bucket": "exclude: CI / bot config",
      "directory": false,
      "already_excluded": false
    },
    {
      "path": ".rat-excludes",
      "bucket": "ship, input to voter checks",
      "directory": false,
      "already_excluded": false
    },
    {
      "path": ".ruff.toml",
      "bucket": "unclassified",
      "directory": false,
      "already_excluded": false
    },
    {
      "path": ".yamllint",
      "bucket": "exclude: lint config not needed to build",
      "directory": false,
      "already_excluded": false
    },
    {
      "path": "LICENSE",
      "bucket": "ship, never excludable",
      "directory": false,
      "already_excluded": false
    },
    {
      "path": "NOTICE",
      "bucket": "ship, never excludable",
      "directory": false,
      "already_excluded": false
    },
    {
      "path": "README.md",
      "bucket": "ship",
      "directory": false,
      "already_excluded": false
    },
    {
      "path": "docs",
      "bucket": "ship",
      "directory": true,
      "already_excluded": false
    },
    {
      "path": "pyproject.toml",
      "bucket": "ship",
      "directory": false,
      "already_excluded": false
    },
    {
      "path": "src",
      "bucket": "ship",
      "directory": true,
      "already_excluded": false
    },
    {
      "path": "tests",
      "bucket": "ship",
      "directory": true,
      "already_excluded": false
    },
    {
      "path": "uv.lock",
      "bucket": "ship",
      "directory": false,
      "already_excluded": false
    }
  ],
  "existing_export_ignore": [],
  "needs_rm": [],
  "proposed": [
    {
      "path": ".gitattributes",
      "entry": "/.gitattributes",
      "bucket": "exclude: VCS metadata",
      "comment": "VCS metadata"
    },
    {
      "path": ".github/workflows",
      "entry": ".github/workflows/",
      "bucket": "exclude: CI / bot config",
      "comment": "CI / bot config"
    },
    {
      "path": ".idea",
      "entry": ".idea/",
      "bucket": "exclude: editor / IDE",
      "comment": "editor / IDE"
    },
    {
      "path": ".pre-commit-config.yaml",
      "entry": "/.pre-commit-config.yaml",
      "bucket": "exclude: CI / bot config",
      "comment": "CI / bot config"
    },
    {
      "path": ".yamllint",
      "entry": "/.yamllint",
      "bucket": "exclude: lint config not needed to build",
      "comment": "lint config not needed to build"
    },
    {
      "path": ".ruff.toml",
      "entry": "/.ruff.toml",
      "bucket": "unclassified",
      "rm_choice": true,
      "comment": "lint config not needed to build"
    }
  ],
  "refused": [],
  "symlink_chains": [],
  "stripped_symlink_targets": [],
  "gitattributes_block": "# VCS metadata\n/.gitattributes export-ignore\n# CI / bot config\n.github/workflows/ export-ignore\n# editor / IDE\n.idea/ export-ignore\n# CI / bot config\n/.pre-commit-config.yaml export-ignore\n# lint config not needed to build\n/.yamllint export-ignore\n# lint config not needed to build\n/.ruff.toml export-ignore",
  "refs_command": "",
  "before_after_commands": "# \"before\": the attributes committed at HEAD\nuv run --project <framework>/tools/reproducible-archive repro-archive build \\\n  --ref HEAD --prefix p --format tar.gz -o \"$TMPDIR/before.tar.gz\"\n# \"after\": the proposed .gitattributes as edited in the working tree\nuv run --project <framework>/tools/reproducible-archive repro-archive build \\\n  --ref HEAD --prefix p --format tar.gz --worktree-attributes -o \"$TMPDIR/after.tar.gz\"\nuv run --project <framework>/tools/reproducible-archive repro-archive compare \\\n  \"$TMPDIR/before.tar.gz\" \"$TMPDIR/after.tar.gz\"   # 'removed' = exactly what the review strips"
}
```

Output of `release-management prepare prep-pr --load <scratch>/prepare-load.json --version 1.0.0 --product-name "Apache Foo" --versions <scratch>/versions.json --changelog <scratch>/changelog.json --archive-review proposed --archive-entry … (one per confirmed entry)`:

```json
{
  "pr_title": "chore: prepare 1.0.0 release",
  "pr_body": "Release prep for Apache Foo 1.0.0.\n\n## Changes\n\n### Version bump\nFiles updated:\n- pyproject.toml\n`1.0.0.dev0` → `1.0.0`\n\n### Changelog\nEntry added for 1.0.0 covering 40 merged PRs.\n\n### NOTICE/LICENSE\nNo changes required.\n\n### Source archive contents\n- `/.gitattributes` — VCS metadata\n- `.github/workflows/` — CI / bot config\n- `.idea/` — editor / IDE\n- `/.pre-commit-config.yaml` — dev tooling (CI / bot config)\n- `/.yamllint` — lint config not needed to build\n- `/.ruff.toml` — lint config not needed to build\n- release-build.md: export_ignore_reviewed set to 1.0.0\n\n## Checklist (RM)\n- [ ] Version bump is correct in all manifest files\n- [ ] Changelog entry covers the intended scope\n- [ ] NOTICE attribution changes are justified\n- [ ] No Category-X dependency appears in the diff\n- [ ] (first release) every `export-ignore` entry was reviewed; LICENSE / NOTICE / build inputs still ship\n\nGenerated by `release-prepare` (magpie-release-prepare).",
  "files_in_scope": [
    "pyproject.toml",
    ".gitattributes",
    "<project-config>/release-build.md"
  ],
  "scope_violations": [],
  "category_x_hit": false,
  "notice_removal_unjustified": false,
  "changelog_coverage_pct": 100,
  "archive_review": "proposed",
  "proposed": true,
  "confirmed_out_of_scope": [],
  "read": []
}
```
