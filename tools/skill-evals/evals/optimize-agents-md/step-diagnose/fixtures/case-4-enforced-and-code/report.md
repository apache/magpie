<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Target: AGENTS.md (repository root)

measure.py: 31,800 chars, 610 lines, ~7,950 tokens always-on
  no generated TOC
  4 code blocks: ~1,240 tokens

Sections, largest first:
  ~2,600 tok  ## Commit conventions — 40 lines on the forbidden Co-Authored-By
             trailer: how to spot it, how to strip it, how to re-commit. The
             repository's committed commit-msg hook (installed for every
             contributor by the mandatory setup step) rejects any such commit
             before it is created and prints the exact fix.
  ~1,650 tok  ## Signing commits with a hardware key — includes a 34-line,
             placeholder-free bash probe that checks the gpg agent cache; the
             agent runs it and reads one line of output, never edits it.
  ~1,300 tok  ## Repository layout — read at the start of most tasks.
  ~  800 tok  ## Before submitting — the checks before a PR.

No @path imports. No CLAUDE.md. No subtree-only rules.
Other code blocks: two one-line command shapes with placeholders.
Duplication: none against docs/.
Prose: terse.
