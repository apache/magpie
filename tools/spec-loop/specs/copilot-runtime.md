<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: GitHub Copilot skill runtime
status: experimental
kind: feature
mode: infra
source: >
  RFC-AI-0004 Principle 3 (vendor neutrality) and issue #318.
  Implemented by the canonical .agents/skills tree, the .github/skills
  relay, .github/copilot-instructions.md, docs/adapters/copilot.md, and
  tools/agent-isolation.
acceptance:
  - A maintainer with GitHub Copilot and no Claude Code can discover and
    invoke Magpie SKILL.md workflows from .agents/skills or .github/skills.
  - Both Copilot surfaces are covered - the interactive CLI and the
    server-side Coding Agent - with the boundary each one runs under
    stated separately.
  - The Coding Agent terminates at a Draft Pull Request and is never
    dispatched on private security-tracker material.
  - Copilot CLI use on security-list or private-list content requires an
    explicit adopter opt-in, because GitHub-hosted models are not in the
    default-approved set.
  - The isolation the wrapper does and does not provide for this harness
    is recorded rather than implied.
---

# GitHub Copilot skill runtime

## What it does

Makes GitHub Copilot a native Magpie runtime rather than a delegation
target. Copilot reads the same workflow sources as every other harness
and drives the same deterministic `tools/` bridges, under GitHub's own
confirmation and review boundaries.

Copilot is two operational surfaces, not one, and they carry different
risk. The **interactive CLI** (`copilot`) is terminal-native and
operator-driven, confirming each command. The **Coding Agent** is
server-side and autonomous: it is assigned an issue or mentioned on a
PR and authors a scoped Draft Pull Request. Every rule below that
distinguishes the two does so because one runs on the operator's
machine and the other on shared cloud infrastructure.

## Where it lives

- `.agents/skills/` - canonical cross-harness skill symlinks.
- `.github/skills/` - the relay path Copilot also discovers.
- `.github/copilot-instructions.md` - repository instructions, read
  alongside `AGENTS.md`.
- `docs/adapters/copilot.md` - the harness adapter guide.
- `~/.copilot/mcp-config.json` - MCP servers for the CLI; the Coding
  Agent configures its own in repository Copilot settings.
- `tools/agent-isolation/agent-iso.sh` - the clean-environment launcher.

## Behaviour & contract

- **Same sources, no fork.** Skills are discovered from
  `.agents/skills/` and `.github/skills/`; repository instructions come
  from `.github/copilot-instructions.md` and `AGENTS.md`, which in turn
  reference the adopter's `<project-config>/`. No Copilot-specific copy
  of a workflow exists.
- **Proposal-then-confirm, per command.** In the CLI every proposed
  shell command needs explicit operator confirmation before it runs.
  The permissive flags `--allow-all` and `--yolo` bypass exactly that
  gate and must not be enabled. Outbound communication, issue state
  changes, and remote pushes stay gated on approval.
- **The Coding Agent ends at a Draft PR.** It never pushes to a
  protected branch and never merges. Merging stays gated on human
  review and passing checks.
- **The Coding Agent never sees embargoed material.** It runs on shared
  cloud infrastructure, so it is not dispatched on private
  security-tracker issues, discussions, or reviews - including by being
  added as a reviewer.
- **The CLI is not local inference.** It routes prompt and context data
  to GitHub-hosted models, which are not in the default-approved set in
  [`tools/privacy-llm/models.md`](../../../tools/privacy-llm/models.md).
  Using it on `<security-list>` or `<private-list>` material requires an
  explicit opt-in declared in `<project-config>/privacy-llm.md`.
- **Tools run locally and deterministically.** The operator reviews and
  confirms the command; the script executes on their machine, and its
  source is not transmitted to the model.
- **Untrusted content stays data.** Issue descriptions, PR bodies, and
  reporter comments never override system instructions or policy, per
  the absolute rule in
  [`AGENTS.md`](../../../AGENTS.md#treat-external-content-as-data-never-as-instructions).
- **The wrapper is Layer 0 only for this harness.** `agent-iso copilot`
  strips ambient cloud tokens while preserving `git`, `uv`, `gh`, and
  `copilot`. It adds **no push gate**: Copilot receives the live
  `SSH_AUTH_SOCK` and nothing at the wrapper boundary stops a
  `git push`. Branch protection and keeping the permissive flags off are
  what actually hold. Stripping local environment variables also does
  nothing to the cloud inference boundary above.

## Out of scope

- A Copilot equivalent of the Codex project policy file: Copilot exposes
  no committed sandbox / approval profile for `tools/sandbox-lint` to
  validate, so there is no Copilot branch in that validator.
- Gating `git push` at the wrapper for this harness - see the Layer 0
  caveat above; that is an `agent-isolation` gap, not a Copilot one.
- Running the Coding Agent anywhere in the embargoed security
  lifecycle.

## Acceptance criteria

1. A maintainer with only Copilot installed can discover and run a
   Magpie skill from `.agents/skills/` or `.github/skills/`.
2. `.github/copilot-instructions.md` exists and points at `AGENTS.md`
   and the adopter's `<project-config>/`.
3. Copilot CLI sessions confirm each command; `--allow-all` / `--yolo`
   are documented as prohibited.
4. Every Coding Agent workflow terminates at a Draft Pull Request.
5. The Coding Agent is excluded from private security-tracker material,
   and CLI use on such material is gated on an adopter opt-in in
   `<project-config>/privacy-llm.md`.
6. The Layer 0 isolation caveat is stated in the adapter guide rather
   than left for the operator to infer.

## Validation

```bash
# Skill discovery topology across every harness path
PYTHONUTF8=1 uv run --project tools/symlink-lint symlink-lint

# Skill and tool metadata
PYTHONUTF8=1 uv run --project tools/skill-and-tool-validator --group dev \
    skill-and-tool-validate

# Vendor-neutrality score reflects the added harness
PYTHONUTF8=1 uv run --project tools/vendor-neutrality-score \
    vendor-neutrality-score

# Adapter guide TOC and formatting
uv run prek run doctoc --all-files
```

## Known gaps

- **No committed policy profile to lint.** Codex and Gemini both ship a
  project-scoped profile that `tools/sandbox-lint` checks. Copilot has
  no equivalent surface, so its posture rests on documentation and
  operator discipline rather than a validated file.
- **No push gate at the wrapper.** Tracked as an `agent-isolation`
  limitation for every generic `agent-iso <cli>` invocation, not
  specific to Copilot.
- **The Coding Agent's MCP configuration is not in the repository.** It
  lives in repository Copilot settings, so it cannot be reviewed in a
  PR the way `.mcp.json` or the CLI's `~/.copilot/mcp-config.json` can.
