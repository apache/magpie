<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Where this skill came from

Adapted from **`skill-creator`** in
[`JuliusBrussee/awesome-claude-skills`](https://github.com/JuliusBrussee/awesome-claude-skills)
(Apache-2.0), at commit
[`5380239`](https://github.com/JuliusBrussee/awesome-claude-skills/tree/5380239b724883543db9e9e2de56c4dd8796090d/skill-creator).

Read this when you need to know why the flow differs from upstream, or
when you adapt another third-party skill and want the precedent. Nothing
here is needed to write a skill.

The workflow shape is recognisable to anyone who knows `skill-creator`.
What changed:

- **Renamed** to `write-skill`, matching the framework's verb-first
  naming. `when_to_use` still lists both names as triggers.
- **Frontmatter** follows the framework schema: `license: Apache-2.0`
  rather than free-form licence text, `when_to_use` alongside
  `description`, and an SPDX plus placeholder-convention comment after
  the frontmatter.
- **Step 3** runs the framework's own
  [`scripts/init_skill.py`](scripts/init_skill.py), which scaffolds the
  structure this framework expects.
- **Upstream's packaging step is gone.** Skills ship through the
  snapshot and marketplace models, not as zip artefacts, so
  `package_skill.py` is not included. Validation is
  [`tools/skill-and-tool-validator`](../../../../tools/skill-and-tool-validator/),
  a superset of upstream's `quick_validate.py`.
- **A security checklist replaced it.** Any skill that reads external
  content walks the prompt-injection patterns in
  [`security-checklist.md`](security-checklist.md), drawn from the
  [2026-05 audit](https://gist.github.com/andrew/0bc8bdaac6902656ccf3b1400ad160f0).
  This is the load-bearing change: a new skill inherits those lessons
  instead of rediscovering them in the next audit.

Adapting third-party content means adding a "Third-party content" entry
to the root [`NOTICE`](../../../../NOTICE), per the
[ASF licensing howto](https://infra.apache.org/licensing-howto.html).
