<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Target: AGENTS.md (repository root)

measure.py: 21,700 chars, 410 lines, ~5,425 tokens always-on
  no generated TOC
  no code blocks

nest.py suggest: [] (no section's path references all sit under one directory)

Sections, largest first:
  ~2,300 tok  ## Frontend conventions — component naming, the CSS-module rule, how
             to write the Storybook stories, the accessibility checklist. It names
             no paths, but every rule in it is about the code in the web/ directory,
             the only frontend in the repository.
  ~1,350 tok  ## Commit conventions — needed in most sessions.
  ~1,100 tok  ## Repository layout — read at the start of most tasks.
  ~  650 tok  ## Before submitting — the checks before a PR.

The project's supported harnesses load a nested AGENTS.md when the agent works on
files below it. No @path imports. CLAUDE.md is a symlink to AGENTS.md.
Duplication: none against docs/. Hooks: none enforce these rules.
Prose: terse.
