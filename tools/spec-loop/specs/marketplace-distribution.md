<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Marketplace distribution (plugin manifests and versioning)
status: experimental
kind: feature
mode: infra
source: >
  docs/setup/marketplaces.md. The manifest set at .claude-plugin/,
  .codex-plugin/, .agents/plugins/, plugins/magpie-*/, and the repo-root
  plugin.json / marketplace.json / apm.yml / gemini-extension.json.
  Enforced by tools/dev/check-family-plugins.py.
acceptance:
  - Every ecosystem manifest mirrors pyproject.toml's project.version
    verbatim, including the .devN suffix.
  - Every skill family has a plugins/magpie-<family>/ plugin whose skills/
    directory contains exactly that family's skills as single-hop symlinks.
  - Manifests are generated from pyproject.toml and the all-in-one manifest,
    never hand-edited; the generator is idempotent and CI fails on drift.
---

# Marketplace distribution

## What it does

Publishes the framework as installable plugins across several agent
ecosystems, so an adopter who does not want the
[`/magpie-setup` snapshot install](adoption-and-setup.md) can take the skills
through their client's own plugin mechanism instead.

This is the *distribution* surface. It changes nothing about how a skill
behaves — the same `skills/<name>/SKILL.md` tree is what every install method
delivers.

## Where it lives

Two manifest families, because the ecosystems have not converged:

- **Agent Plugins 1.0** — the vendor-neutral root `plugin.json`, pinned to
  `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`. Its schema is
  **closed**: exactly ten permitted fields, so a client-specific component path
  cannot leak in. The spec requires it at the repository root, so its location
  is not a choice.
- **Client-specific** — `.claude-plugin/plugin.json` + `marketplace.json`
  (Claude Code, the only family that carries `hooks` and per-family plugins),
  `.codex-plugin/plugin.json` with `.agents/plugins/marketplace.json` (Codex),
  the root `marketplace.json` (Copilot / VS Code legacy catalog),
  `gemini-extension.json`, and `apm.yml` (`microsoft/apm`, schema v0.1).

Plus `plugins/magpie-<family>/` — ten Claude-Code-only plugins, one per skill
family, each a manifest and a `skills/` directory of single-hop symlinks into
the shared `skills/<skill>` tree.

`tools/dev/check-family-plugins.py` is both the generator (`--fix`) and the
CI gate. `docs/setup/marketplaces.md` is the adopter-facing page.

## Behaviour & contract

- **`pyproject.toml` `project.version` is the single authority.** Every
  ecosystem manifest mirrors it verbatim, `.devN` suffix included. Nothing is
  hand-edited: `project.version` feeds the ecosystem manifests, and
  `.claude-plugin/plugin.json` in turn feeds the ten per-family manifests and
  the marketplace entries, which also inherit `author`, `homepage`,
  `repository`, and `license`.

- **Between releases the version carries a moving dev suffix, and it is
  load-bearing.** The manifests read `0.2.0.dev<YYYYMMDDHHMM>`, never a bare
  `0.2.0` — a bare version would advertise a release that does not exist. The
  marketplace is served straight from the `main` branch, so adopters *do*
  install dev versions; that is the normal case. `claude plugin update`
  compares **version strings, not commit SHAs**, so while the suffix stays
  frozen an adopter is told they are "already at the latest version" however
  far behind `main` their copy has fallen, and the only recovery is
  `claude plugin marketplace update` plus a full uninstall and reinstall of
  every plugin — which nobody discovers unaided. The stamp is minute-resolution
  **UTC** so bumps from contributors in different timezones sort in the order
  they were made.

- **Bump when the work needs to reach installed copies**, not per PR — a
  per-PR bump puts every contributor in conflict with every other over one
  line. Before pointing anyone at `claude plugin update`, before announcing a
  change adopters should take, or when merged work has piled up behind a stale
  stamp.

- **Family membership comes from `family:` frontmatter, never from a skill's
  name prefix.** A family plugin's `skills/` directory must contain exactly the
  skills declaring that family — several do not carry the family's name
  (`pr-stale-sweep`, `pre-first-pr-check` and `reviewer-routing` are all
  `family: pr-management`).

- **The per-family plugins are Claude Code only.** The Codex and Copilot
  catalogs list the all-in-one plugin and nothing else; advertising a family
  plugin there would offer those clients something they cannot install.

- **The same skill is invoked by a different name per install method**, and all
  three are correct: `/magpie-<name>` under the portable snapshot install
  (where the `magpie-` prefix *is* the namespace), `/magpie:<name>` under the
  all-in-one marketplace plugin, and `/magpie-<family>:<name>` under a family
  plugin (where `plugin:skill` supplies the namespace).

- **Placeholder syntax in a skill `description` is conformant, not a
  portability risk.** 45 of the 74 descriptions contain `<tracker>`,
  `<upstream>` and friends. The Agent Skills specification constrains
  `description` on length only (1–1024 characters, non-empty); its
  character-class rules apply to `name`, which every skill satisfies.

## Out of scope

- The snapshot install and its lock/override model — that is
  [`adoption-and-setup.md`](adoption-and-setup.md).
- Publishing to any vendor's hosted registry. Every catalog here is served
  from this repository; nothing is pushed anywhere.
- The ASF source release. None of these manifests change how the release
  artefact is built or signed.

## Acceptance criteria

1. `check-family-plugins.py` passes: version parity across every ecosystem
   manifest, AP1 conformance for the root `plugin.json` (pinned `$schema`,
   name pattern, closed ten-field set), one well-formed plugin per declared
   family, and symlink sets matching `family:` frontmatter exactly.
2. `--fix` regenerates every manifest from `pyproject.toml` and is idempotent —
   a second run is a no-op.
3. A version bump is a one-line edit to `pyproject.toml` plus a regeneration.
4. The Codex and Copilot catalogs list only the all-in-one plugin.

## Validation

```bash
python3 tools/dev/check-family-plugins.py
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

For the Claude Code family, `claude plugin validate . --strict`.

## Known gaps

- **Only the Claude Code manifests are verified against a live install.** The
  rest — AP1 root `plugin.json`, the Codex pair, the Copilot catalog,
  `gemini-extension.json`, `apm.yml` — conform to their vendors' published
  documentation but have not been exercised end-to-end. Re-check each against
  current vendor docs before a marketplace publish.
- **`apm.yml` targets `microsoft/apm` schema v0.1**, pre-1.0 and the most
  likely of the set to churn.
- **Gemini has no migration path off `gemini-extension.json`.** Google has
  joined the AP1 TSC but published nothing, so both files stay.
- **Nothing checks the dev-suffix stamp is fresher than the last release**, so
  a bump that is forgotten fails silently in the one way that matters: adopters
  keep being told they are up to date. The staleness is only visible by reading
  the timestamp.
