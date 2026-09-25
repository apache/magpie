<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Commit attribution — which trailer an agent-assisted commit carries](#commit-attribution--which-trailer-an-agent-assisted-commit-carries)
  - [The conventions](#the-conventions)
  - [Where it is set](#where-it-is-set)
  - [How the convention is resolved](#how-the-convention-is-resolved)
  - [How the trailer is added](#how-the-trailer-is-added)
  - [What the guard does with it](#what-the-guard-does-with-it)
  - [Adopting projects and skills](#adopting-projects-and-skills)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Commit attribution — which trailer an agent-assisted commit carries

Projects disagree on how a commit records that an agent helped write it.
The ASF convention is a `Generated-by:` trailer; other projects use `Assisted-by:`, GitHub's `Co-authored-by:`, or no trailer at all.
Magpie does not pick one for everybody.
The project chooses when it adopts Magpie, and a contributor chooses only where the project leaves the choice open.
Every skill that commits, and the agent-guard `commit-trailer` guard, resolve the convention the same way, described here.

## The conventions

| `convention` | Trailer the agent adds | Used by |
|---|---|---|
| `generated-by` | `Generated-by: {agent} ({model})` | The ASF ([Generative Tooling guidance](https://www.apache.org/legal/generative-tooling.html)); the default |
| `assisted-by` | `Assisted-by: {agent}:{model}` | Projects that name the tool without implying generation |
| `co-authored-by` | `Co-authored-by: {agent} <{email}>` | GitHub's co-author form; several agent harnesses' own default |
| `none` | no trailer | Projects that record agent use elsewhere, or not at all |
| `custom` | the `template` value | Anything else |

`{agent}` is the agent harness and `{model}` the model actually running, e.g. `Claude Code` and `Claude Opus 4.8`.
`{email}` is the address the harness uses for itself as a co-author.
Only `co-authored-by` needs it.
A `template` value overrides the default wording of any convention, and `custom` requires one.

## Where it is set

One small TOML file per layer:

| Layer | File | Committed? |
|---|---|---|
| Project | `.apache-magpie-overrides/commit-attribution.toml` | Yes — set by `setup adopt` |
| Contributor | `.apache-magpie-local/commit-attribution.toml` | No — set by `setup config` |

```toml
# generated-by | assisted-by | co-authored-by | none | custom
# The project file may also say contributor-choice.
convention = "generated-by"

# Optional; required when convention = "custom".
# template = "Generated-by: {agent} ({model})"
```

`projects/_template/commit-attribution.toml` is the scaffold both layers start from.

## How the convention is resolved

This is the one configuration file where **the project wins**, not the contributor's local copy (the general rule in [agentic overrides](agentic-overrides.md) is local-wins, per file).
Attribution is a project policy first: a project that requires `Generated-by:` must be able to rely on it.

1. If the project file sets a `convention` other than `contributor-choice`, that is the convention.
2. Otherwise — the project file is absent, has no `convention` key, or says `contributor-choice` — the contributor file's `convention` applies.
3. Otherwise the convention is `generated-by`.

Fail closed: a file that cannot be read or parsed, or a value that is not one of the conventions above, resolves to `generated-by`.
`contributor-choice` in the contributor's own file is not a convention and resolves the same way.

## How the trailer is added

Always with `git commit --trailer`, never by typing it into the message body or the `-F <file>`:

```bash
git commit -F "$TMPDIR/commit-msg.txt" --trailer "Generated-by: Claude Code (Claude Opus 4.8)"
```

`--trailer` puts the line in the trailer block with the separating blank line git expects.
It also keeps it on the command line, where the agent-guard and any other hook that inspects the command can see it, even when the body travels in a file.
For `none`, pass no `--trailer`.

## What the guard does with it

The agent-guard `commit-trailer` guard blocks a `git commit` that carries `Co-Authored-By:` (in the message, a `-F <file>`, or a `--trailer`) unless the resolved convention for the repository being committed to is `co-authored-by`.
It follows `git -C <dir>` to that repository.
The per-command override `MAGPIE_ALLOW_COAUTHOR=1` still works.

This is a policy aid, not a security boundary.
A contributor can relax the guard with their own gitignored file whenever the project leaves the choice open.
It reads a `-F <file>` message only if the file exists when the command starts, so a file written earlier in the same command line is not checked.

## Adopting projects and skills

- `setup adopt` asks the maintainer which convention the project uses, including `contributor-choice`, and writes the project file.
- `setup config` asks a contributor for their preference only when the project leaves it open.
- Skills that commit resolve the convention as above and add the trailer with `--trailer`.
  Skills that review someone else's commits check them against the same resolved convention.
- The framework repository itself sets `generated-by` in its own `.apache-magpie-overrides/commit-attribution.toml`, so contributions to Magpie follow the ASF convention whatever a contributor prefers elsewhere.
