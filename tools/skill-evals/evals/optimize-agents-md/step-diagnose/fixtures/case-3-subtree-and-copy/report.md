<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Target: AGENTS.md (repository root), plus CLAUDE.md

measure.py: 24,300 chars, 470 lines, ~6,075 tokens always-on
  CLAUDE.md: 24,300 chars, a regular file whose text is identical to AGENTS.md
  no generated TOC
  2 code blocks: ~60 tokens

Sections, largest first:
  ~2,050 tok  ## Writing Python tools under tools/ — pyproject layout, the uv
             workspace entry, test layout, the tool README contract. Applies only
             to work inside tools/.
  ~1,400 tok  ## Commit conventions — needed in most sessions.
  ~1,200 tok  ## Repository layout — read at the start of most tasks.
  ~  900 tok  ## Before submitting — the checks before a PR.

The project's supported harnesses all load a nested AGENTS.md when the agent
works on files below it. No @path imports.
Code blocks: two command shapes with placeholders.
Duplication: none against docs/. Hooks: none enforce these rules.
Prose: terse.
