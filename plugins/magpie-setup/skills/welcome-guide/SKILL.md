---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: welcome-guide
family: setup
mode: Meta
description: >-
  Show a Magpie welcome guide on demand: the general one with no
  argument, or a skill family's by name. Also turns a guide back on
  after it was dismissed or hidden. Read-only apart from that.
when_to_use: >-
  When the user asks to "show the welcome guide", "show the security
  guide", "how do I start with Magpie", or wants a dismissed guide
  back ("show the security welcome again", "turn the Magpie guide back on").
argument-hint: "[family]"
capability: capability:platform
surface_hash: sha256:3dafaec43fc7bd00
license: Apache-2.0
measured_tokens: 1317
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- Placeholder convention (see ../../AGENTS.md#placeholder-convention-used-in-skill-files):
     <family> → a guide name: `general`, or a skill family that ships a guide -->

# setup-welcome-guide

Every Magpie skill's pre-flight shows a short welcome guide the first time it is due:
the general guide on the first Magpie skill a user runs, and a family's guide on the first run of that family.
This skill shows any of them on request, and brings back one the user dismissed or hid.
The guides live in the pre-flight checker,
[`setup_preflight/guides/`](../setup/setup_preflight/guides/), one Markdown file each;
this skill adds no logic of its own and only runs the checker's `welcome` command.

## Adopter overrides

<!-- BEGIN MAGPIE BLOCK: adopter-overrides — generated from tools/dev/blocks/adopter-overrides.md -->

Before running its default behaviour, this skill consults
`setup-welcome-guide.md` in the personal layer
(`.apache-magpie-local/` when the project adopted Magpie, falling back to the main checkout's in a linked worktree,
or `<git-common-dir>/apache-magpie/` when Magpie is only installed; applied first, wins on conflict) and
[`.apache-magpie-overrides/setup-welcome-guide.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo, if present, and applies any agent-readable overrides it finds.
See [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md) for the contract.

**Hard rule**: agents NEVER modify the snapshot under `<adopter-repo>/.apache-magpie/`.
Local modifications go in the override file; framework changes go via PR to `apache/magpie`.

<!-- END MAGPIE BLOCK: adopter-overrides -->

## Inputs

| Argument | Guide |
|---|---|
| (none) | `general` — getting started, staying current, asking, making Magpie yours. |
| `<family>` | That family's guide, for example `security`. |

## Step 1 — Show the guide

Resolve `<family>` first: no argument means `general`, and the user's words map onto a name —
*"show the security guide"* is `security`;
*"how do I start with Magpie"* or *"show the welcome guide"* is `general`.
Pass any other name through as given and let the command say whether it exists.

Every command uses the personal layer's copy of the checker, as the pre-flight does:

```bash
PYTHONPATH=".apache-magpie-local:$(git rev-parse --git-common-dir)/../.apache-magpie-local:$(git rev-parse --git-common-dir)/apache-magpie" \
  python3 -m setup_preflight.welcome show --family <family>
```

- **Exit 0** → show the output to the user **verbatim**, as Markdown.
  Do not summarise, reword or trim it, and substitute nothing in its placeholders.
- **Exit 2, no such guide** → say there is no guide by that name and list the ones that ship,
  from `python3 -m setup_preflight.welcome list` with the same `PYTHONPATH`.
  Never invent a guide.
- **No such module** → the checker is not installed in the personal layer yet.
  Say so, and propose [`/magpie-setup:setup config`](../setup/config.md), which installs it.

Then offer the coloured version in one line:
the agent's reply cannot carry colour, so the user runs it themselves with the `!` prefix,
the same command with `--color=always` added (`NO_COLOR` turns the colour off).

## Step 2 — Turn it back on, when asked

Only when the user asked to have a guide back
(*"show the security welcome again"*, *"turn the Magpie guide back on"*),
clear its recorded choice so the pre-flight shows it again:

```bash
PYTHONPATH=".apache-magpie-local:$(git rev-parse --git-common-dir)/../.apache-magpie-local:$(git rev-parse --git-common-dir)/apache-magpie" \
  python3 -m setup_preflight.welcome enable --family <family>
```

It merges into the personal layer's `reconciled.json`, removing only `welcome.<family>`.
Never edit that file by hand, and never run `enable` for a request that only asked to see the guide.
Report in one line what changed, for example *"The security guide will show on your next security skill."*

## Hard rules

- Show the guide exactly as the command printed it.
- This skill writes nothing except through `welcome enable`, and only on the user's request.
- The setup skill's `welcome` sub-action is this skill; run this one rather than repeating its steps there.

## References

- [`setup_preflight/welcome.py`](../setup/setup_preflight/welcome.py) — when a guide is due, and the `show`, `list`, `record` and `enable` commands.
- [`tools/setup-preflight/README.md`](../../../../tools/setup-preflight/README.md) — the `welcome` finding and its state.
