<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/dev/`](#toolsdev)
  - [The shared dev toolchain](#the-shared-dev-toolchain)
  - [The scripts](#the-scripts)
  - [Prerequisites](#prerequisites)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/dev/`

**Capability:** substrate:framework-dev

**Harness:** agnostic

Framework dev-loop helpers (placeholder check, agent pre-commit hook). Invoked by prek and CI; not consumed by any skill directly. See the individual scripts in this directory for usage.

## The shared dev toolchain

`tools/dev` is also the workspace's **toolchain project**, `magpie-dev`. It
declares ruff, mypy, and pytest as its dependencies, and every other workspace
member names `magpie-dev` in its own `[dependency-groups] dev` instead of
repeating the pins. Bump a version here and the whole workspace moves together.

Each member's environment stays self-contained — the checks still run
`uv run --directory <member> --project . python -m <tool>`, so no member depends
on tools leaking in from the root environment. Only the *declaration* is shared.

Why it changed: the pins used to be repeated in every member with an instruction
to keep them in lockstep. They had drifted into three different mypy floors, two
pytest floors, and two ruff floors, one member had no dev group at all, and
nothing detected any of it — the duplication was the bug, and the instruction to
keep it consistent was the workaround.

The project builds as a metadata-only wheel: it ships no importable module,
because the scripts are hyphenated and invoked by path, but it has to be
installable for other members to depend on it.

## The scripts

| Script | What it does |
|---|---|
| [`check-doc-sync.py`](check-doc-sync.py) | Guards the documentation claims that track the tree and rot silently: spec-index completeness (every `tools/spec-loop/specs/*.md` listed in **both** `overview.md` and `README.md`), the per-family skill counts in the root `README.md`, the per-mode counts in `docs/modes.md`'s *Modes at a glance* table, the bare catalogue totals in `docs/setup/marketplaces.md`, the per-family *plugin* counts in the marketplace tables of `docs/setup/marketplaces.md` and `docs/quick-start.md` (bare integers in a table column, which the other count checks do not match), the "one plugin, N skills" claim in each family README's *Install & first runs* section (keyed on the install command, not the directory name), that no doc invokes a family skill by a name repeating its family (`/magpie-<family>:<family>-…`, which the plugin does not advertise), that the published always-on token figures match `estimate-skill-tokens.py`, that a doc showing the portable single-token form (`/magpie-<skill>`) says which install it means — `/magpie-setup` is exempt as the name of the install mechanism, and filesystem paths are not invocations — and that every script here is named in this file. |
| [`capture-screenshot.sh`](capture-screenshot.sh) | Captures one quick-start screenshot straight into the path the docs already reference (`assets/quickstart/<harness>-install.png` or `assets/quickstart/families/<family>-install.png`), resized to the 1700px the other `assets/` captures use and EXIF-stripped. Prints what to frame — and the no-secrets check — *before* opening the crosshair. Family names come from the live `family:` frontmatter, so a typo fails loudly instead of writing a file nothing references. macOS only; run it from your own terminal, since Screen Recording permission is per calling application. |
| [`check-skill-preflight.py`](check-skill-preflight.py) | Keeps the shared setup pre-flight block identical in every `skills/*/SKILL.md`, generated from the single source at [`preflight-block.md`](preflight-block.md). The check has to live in each skill body: no code runs on plugin install/upgrade on most harnesses, and a shared include would escape the family plugin root that AP1 forbids leaving — so one source, many generated copies, with `--fix` propagating and the hook preventing drift. The `setup` family is exempt (those skills *are* the setup). |
| [`estimate-skill-tokens.py`](estimate-skill-tokens.py) | Estimates each marketplace plugin's **always-on** token cost — the frontmatter `name` + `description` every installed skill advertises on every turn, at ~4 chars/token — and prints it per family. `--check` compares the figures published in `docs/setup/marketplaces.md` and `docs/quick-start.md` against the live frontmatter; `check-doc-sync.py` calls it, so an edited description that moves a published number fails the build. The `SKILL.md` body is excluded: it costs nothing until the skill is invoked. |
| [`check-family-plugins.py`](check-family-plugins.py) | Validates the marketplace plugins against the skills' `family:` frontmatter — version parity across every ecosystem manifest, Agent Plugins 1.0 conformance, and one well-formed per-family plugin whose `skills/` symlinks match the family exactly. `--fix` regenerates them, which is how the prek hook runs it. |
| [`check-placeholders.sh`](check-placeholders.sh) | Fails the build on hardcoded project references in skill and tool docs, which must use `<PROJECT>` / `<project>` / `<tracker>` / `<upstream>` instead. Carries both casings and matches spaced variants. |
| [`check-workspace-members.py`](check-workspace-members.py) | Catches a new `tools/<name>/pyproject.toml` that was never added to `[tool.uv.workspace] members` — an omission that silently drops the tool from both the pre-commit hooks and the CI pytest matrix. Also verifies each member's tests actually run: both surfaces key off `[tool.pytest.ini_options]`, so a project can carry a full `tests/` directory and be executed by nothing. Reports tests-without-config, config-without-tests, and neither; `[tool.magpie.checks] skip = ["pytest"]` is the declared exemption. |
| [`run-workspace-check.sh`](run-workspace-check.sh) | Runs one static-check or test command across every workspace member, auto-discovering which members a given check applies to. The four `workspace-*` hooks call it, so adding a tool needs no edit to the pre-commit config. |
| [`add-license-headers.py`](add-license-headers.py) | Stamps the SPDX licence header into Markdown files that lack one. |
| [`agent-pre-commit.sh`](agent-pre-commit.sh) | Wrapper for `prek run --all-files`, for agent use. An agent running `pytest` / `ruff` / `mypy` individually still misses the rest of the CI gate (doctoc, markdownlint, typos, the checks above); this runs what CI runs. |

Each `check-doc-sync.py` check was added after the drift it catches had been
found by hand. None of them break anything when wrong, which is precisely why
they need a machine rather than a reviewer: they are numbers and index entries
a human has to remember to update while thinking about something else.

## Prerequisites

- **Runtime:** Bash + coreutils; `check-workspace-members.py`, `check-family-plugins.py`, `check-doc-sync.py`, `check-skill-preflight.py`, and `add-license-headers.py` run under `python3` (standard library only).
- **CLIs:** `uv` (the workspace checks run `uv run`), `git`, and `prek` (or `pre-commit`) — these scripts wire up the framework's hooks.
- **Credentials / auth:** None.
- **Network:** Local checks; `uv` may resolve workspace dependencies from PyPI (`pypi.org`, `files.pythonhosted.org`) on first sync.
