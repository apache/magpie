<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Marketplace distribution (plugin manifests and versioning)
status: experimental
kind: feature
mode: infra
source: >
  docs/setup/marketplace.md. The manifest set at .claude-plugin/,
  .codex-plugin/, .agents/plugins/, plugins/magpie-*/, and the repo-root
  plugin.json / marketplace.json / apm.yml.
  Hook wiring in plugins/magpie-setup/hooks/ and
  plugins/magpie-agent-guard/hooks/.
  Enforced by tools/dev/check-family-plugins.py.
acceptance:
  - Every ecosystem manifest mirrors pyproject.toml's project.version
    verbatim, including the .devN suffix.
  - Every skill family has a plugins/magpie-<family>/ plugin whose skills/
    directory contains exactly that family's skills as real directories, which
    the flat skills/ tree mirrors back with single-hop symlinks.
  - Manifests are generated from pyproject.toml and the root metadata anchor,
    never hand-edited; the generator is idempotent and CI fails on drift.
  - A marketplace-installed project gets the identical reconciliation
    guarantee a pinned-snapshot install gets — the same generated
    `surface_hash:` fingerprint, the same `reconciled:` stamp shape, the
    same pre-flight comparison — reached through the plugin cache's
    version-bearing path instead of a local lock file; see
    [`adoption-and-setup.md`](adoption-and-setup.md) for the mechanism.
  - Every version comparison this surface performs — floor check,
    installed-vs-stamped fingerprint gate, and `verify`'s
    installed-vs-marketplace-clone check — is PEP 440 with the `.devN`
    segment included; nothing strips or rounds it.
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
  and `apm.yml` (`microsoft/apm`, schema v0.1).
  Antigravity CLI reads the AP1 root `plugin.json` and the root `skills/` tree
  (`agy plugin install https://github.com/apache/magpie`); it needs no file of its own.
  Pi reads the root `package.json`, whose `pi` key names the `skills/` tree and the Magpie extension
  (`pi install git:github.com/apache/magpie`, once per user); the manifest is private — Magpie is not published to npm —
  and carries the extension's single pinned runtime dependency, which Pi installs itself.
  Goose reads `.goose-plugin/plugin.json` first, which lists the family `plugins/*/skills` directories
  (Goose's installer does not copy the root `skills/` symlinks), and the root `hooks/hooks.json` for its
  guard hook; `goose plugin install https://github.com/apache/magpie` installs it per user.
  The root `marketplace.json` names each plugin's `source` as a bare
  relative path (`"./plugins/magpie-<family>"`), not a `{"source": "local",
  "path": …}` object, which is not a source type Claude Code documents
  (#1622).
  The Codex catalogue lists the ten families plus the `magpie-agent-guard`
  and `magpie-vetted-ops` substrates (`codex plugin add
  <plugin>@apache-magpie`, #1556). `magpie-setup` and `magpie-vetted-ops` are
  `INSTALLED_BY_DEFAULT`; every other entry is `AVAILABLE`.

`.codex-plugin/plugin.json` is **not** the manifest Codex reads for a root that
also has an AP1 `plugin.json`. Codex takes the root `plugin.json` first when it
is a regular file carrying an `agent-plugins.org` `$schema`, and merges
`.codex-plugin/plugin.json` over it as an overlay; only when the root manifest
is absent does it fall back through `.codex-plugin/plugin.json`,
`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`. A root `plugin.json`
that is a symlink yields no manifest at all, with no fallback. See
`docs/setup/marketplace.md` (*Which manifest Codex reads*).

Plus `plugins/magpie-<family>/` — ten per-family plugins, one per skill family,
each a manifest and a `skills/` directory holding that family's skills as real
directories (`plugins/magpie-<family>/skills/<alias>/SKILL.md`); the flat
`skills/<dir>` tree mirrors each one back with a single-hop symlink. Their
manifest is Claude Code's `.claude-plugin/plugin.json`, but they are not
Claude-Code-only: Codex installs them by falling through to that same file.

`magpie-setup` also carries two non-skill payloads as real files inside its
plugin root, because `setup config` installs them from the plugin on a
marketplace install: the `setup_preflight` package at
`plugins/magpie-setup/skills/setup/setup_preflight/` (#1409) and the project
templates at `plugins/magpie-setup/templates/` (#1410). Both mirrors point
inward — `tools/setup-preflight/src/setup_preflight` and `projects/_template`
are symlinks into the plugin — since `magpie-setup` is listed by the Codex and
Copilot catalogs, and Agent Plugins 1.0 §4.1 forbids a link out of such a
plugin root.

`magpie-setup` also carries hooks in `hooks/hooks.json` rather than inline in
its manifest (#1552): the `SessionStart` `check-upgrade.sh` command hook and a
`modules` list naming `drift-check.ts`, a Claude Code mod that checks the
committed lock against the installed plugin or snapshot at session start, with
no model tokens, and shows a drift banner above the prompt.
The command hook is wired as `/bin/bash -p "${CLAUDE_PLUGIN_ROOT}/hooks/check-upgrade.sh"`,
because it runs outside the sandbox and the session environment must not
choose the shell (#1794); on a version change it points at
`/magpie-setup:complete-upgrade` (#1813), and the interpreter rules are in
[`adoption-and-setup.md`](adoption-and-setup.md).
`tools/setup-preflight/tests/test_session_hook.py` asserts that wiring;
`check-family-plugins.py` checks only that `hooks.json` references
`check-upgrade.sh`, and its `--fix` fallback writes the same `/bin/bash -p`
command when `hooks.json` is missing (#1829).
Its manifest declares `"types": "./hooks/types.d.ts"`, and
`check-family-plugins.py` fails when `hooks.json` lacks `modules` or the
`check-upgrade.sh` hook, or when the manifest also declares inline `hooks`,
which Claude Code would load twice.

`tools/dev/check-family-plugins.py` is both the generator (`--fix`) and the
CI gate — the prek hook runs it in `--fix` mode, so the gate corrects drift
rather than only reporting it. `docs/setup/marketplace.md` is the
adopter-facing page.

## Behaviour & contract

- **`pyproject.toml` `project.version` is the single authority.** Every
  ecosystem manifest mirrors it verbatim, `.devN` suffix included. Nothing is
  hand-edited: `project.version` feeds the ecosystem manifests, and
  `.claude-plugin/plugin.json` in turn feeds the ten per-family manifests and
  the marketplace entries, which also inherit `author`, `homepage`,
  `repository`, and `license`.

- **Between releases the version carries a moving dev suffix, and it is
  load-bearing.** The manifests read `0.9.0.dev<YYYYMMDDHHMM>` (the base moved
  from `0.2.0` to `0.9.0` in #1389), never a bare `0.9.0` — a bare version
  would advertise a release that does not exist. The
  marketplace is served straight from the `main` branch, so adopters *do*
  install dev versions; that is the normal case. `claude plugin update`
  compares **version strings, not commit SHAs**, so while the suffix stays
  frozen an adopter is told they are "already at the latest version" however
  far behind `main` their copy has fallen, and the only recovery is
  `claude plugin marketplace update` plus a full uninstall and reinstall of
  every plugin — which nobody discovers unaided. The stamp is minute-resolution
  **UTC** so bumps from contributors in different timezones sort in the order
  they were made.

- **A plugin update replaces plugin files and nothing else.** Neither
  `claude plugin update` nor auto-update runs anything in the adopter's
  repo; each skill's pre-flight self-checks against the last reconciliation
  on its first run after an upgrade, and `/magpie-setup:setup reconcile`
  forces the full pass (`docs/setup/marketplace.md`, #1392). On machines
  using the isolated setup, the same pre-flight also proposes
  `setup-isolated-setup-update` when the upgrade moved the secure-setup
  fingerprint (see [`adoption-and-setup.md`](adoption-and-setup.md),
  criterion 27).

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

- **Per-family works on every client, and there is no all-in-one.** A family
  plugin owns its skills as real directories, so a client that drops symlinks
  still installs them intact — measured on Codex, which used to install such a
  plugin with zero skills and no error. Every catalogue lists all ten families.

- **Substrate plugins publish a tool, not a family.** Beside the ten
  families, the Claude Code catalogue carries four substrate plugins —
  `magpie-agent-guard`, `magpie-vetted-ops`, `magpie-adversarial-review`
  (#1368) and `magpie-security-tools` (#1787) — declared in `SUBSTRATE_PLUGINS` in `check-family-plugins.py`.
  Each inherits the shared manifest metadata, declares no `skills`, exposes
  its `tools/<name>` through a symlink whose entry point must resolve, and
  declares hook wiring only where it has a hook.
  `magpie-security-tools` carries the tools the security skills run
  (tracker field and rollup edits, CVE JSON, the privacy gate, the scan
  importer), so a marketplace install needs no framework checkout.
  Its `SessionStart` hook (`tools/security-management/hooks/link-framework-path.sh`)
  copies the plugin's `tools/` under `~/.cache/apache-magpie/framework/`
  once per plugin version and points the `current` symlink at it; that is
  `<framework>` on a marketplace install, writable so `uv run --project`
  works, and the hook only ever replaces a symlink at `current`.
  `magpie-agent-guard` is the exception to the symlink (#1516): it carries
  a byte-identical copy of `tools/agent-guard/src/agent_guard` as real
  files, because a marketplace client may drop a link whose target leaves
  the plugin root, and `check-family-plugins.py` fails when the copy drifts
  from the source; its `PreToolUse` wiring lives in `hooks/hooks.json`, not
  the manifest, with the engine resolved through
  `${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}` so Claude Code and Grok Build
  share one registration.
  With no framework tree above it in the plugin cache, the engine discovers
  skill-owned guards in the sibling family plugins cached as
  `<marketplace>/<plugin>/<version>/`, preferring each one's copy at the
  engine's own version, else its most recently installed one.
  The others are the `SessionStart` hooks of vetted-ops (`tools/vetted-ops/hooks/link-stable-path.sh`,
  #1406) and adversarial-review (`tools/adversarial-review/hooks/link-stable-path.sh`),
  which point the fixed paths `~/.claude/magpie/vetted-ops` and
  `~/.claude/magpie/adversarial-review` at the installed version each session
  so permission rules and sandbox exclusions never name a versioned
  plugin-cache glob. `magpie-adversarial-review` additionally publishes a
  `commands/adversarial-review.md` link to the command file generated into
  `tools/adversarial-review/commands/`, which Claude Code exposes as
  `/magpie-adversarial-review:adversarial-review` (#1371); that file too must
  resolve. They exist to run the tool from the installed plugin tree:
  the code a sandbox exclusion or a hook executes must sit where the agent
  calling it cannot rewrite it. A tool shipped this way must resolve
  outside the workspace, so it declares no workspace-only `dev` dependency
  group (#1357).

- **The same skill is invoked by a different name per install method**, and
  both are correct: `/magpie-<name>` under the portable snapshot install (where
  the `magpie-` prefix on the install directory *is* the namespace), and
  `/magpie-<family>:<alias>` under a family plugin (where `plugin:skill`
  supplies the namespace). Each skill's frontmatter `name:` is its alias — the
  family-plugin directory name, unique across all families — because Claude
  Code and Codex invoke plugin skills by `name:` and the Agent Skills
  specification requires it to match the directory.

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
   family, skill sets matching `family:` frontmatter exactly, every
   substrate plugin's links and hook entry points resolving, and
   `magpie-setup` carrying `setup_preflight` and the templates as real files
   with their inward mirror links intact.
   `magpie-agent-guard`'s copied runtime matches `tools/agent-guard`
   byte for byte and its hook wiring sits only in `hooks/hooks.json`
   (#1516); `magpie-setup`'s `hooks/hooks.json` declares `modules` and the
   `check-upgrade.sh` hook, with no inline `hooks` in its manifest (#1552).
2. `--fix` regenerates every manifest from `pyproject.toml` and is idempotent —
   a second run is a no-op.
3. A version bump is a one-line edit to `pyproject.toml` plus a regeneration.
4. Every catalogue lists all ten family plugins and no all-in-one, and the
   root `marketplace.json` gives each plugin's `source` as a relative path
   string (#1622).
5. A skill invoked through a family plugin resolves its own
   `surface_hash:` from its shipped frontmatter and its reconciliation
   stamp from the committed lock or the personal layer's `reconciled.json`
   (`<git-common-dir>/apache-magpie/` when only installed) exactly as a
   snapshot-installed skill does — no marketplace-specific branch in the
   check — closing the gap named in
   [`adoption-and-setup.md`](adoption-and-setup.md#what-it-does).
6. Every version compared anywhere in this surface — a plugin's installed
   version against the floor, against the reconciliation stamp, or
   against the marketplace clone — is PEP 440, dev segment included:
   `0.2.0.dev202609211315` is newer than `0.2.0.dev202609180100`, and a
   dev build is never rounded to its release segment or treated as a
   non-event.

## Validation

```bash
python3 tools/dev/check-family-plugins.py
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

For the Claude Code family, `claude plugin validate . --strict`.

## Known gaps

- **Only the Claude Code manifests are verified against a live install.** The
  rest — AP1 root `plugin.json`, the Codex pair, the Copilot catalog,
  `apm.yml` — conform to their vendors' published
  documentation but have not been exercised end-to-end. Re-check each against
  current vendor docs before a marketplace publish.
- **`apm.yml` targets `microsoft/apm` schema v0.1**, pre-1.0 and the most
  likely of the set to churn.
- **Antigravity is checked only with `agy plugin validate .`** (1.3.6 reports the
  root's skills); an end-to-end `agy plugin install` has not been exercised.
- **Pi was exercised with `pi install git:` from a branch** (Pi 1.4.0, macOS): the package installed its
  dependency and loaded the extension; Linux and Windows are unverified.
- **Codex never runs the upgrade-detection hook.**
  `plugins/magpie-setup/` has no `.codex-plugin/plugin.json`, so Codex reads
  its default `hooks/hooks.json`, whose top-level `$schema` and `modules`
  keys its strict hooks-file schema rejects: no hook loads.
  The root `.codex-plugin/plugin.json` hook #1829 re-pointed is written as
  `{"SessionStart": …}` without the inner `hooks` wrapper Codex's inline
  form needs, so it is ignored too, and the Codex catalogue never installs
  the root plugin anyway; `check-family-plugins.py`'s `CODEX_HOOKS` pins
  that shape.
- **Nothing checks the dev-suffix stamp is fresher than the last release**, so
  a bump that is forgotten fails silently in the one way that matters: adopters
  keep being told they are up to date. The staleness is only visible by reading
  the timestamp.
