<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Skill name: skill-scaffolder
Purpose: Generates a new SKILL.md scaffold from a YAML configuration file that
the developer provides in the repository.

Data sources:
- A YAML config file at `.claude/skills/<skill-name>/config.yaml` inside the
  developer's own repository (committed, developer-controlled)
- No external API calls; no reading of GitHub issues, PRs, or emails

Writes:
- Creates `.claude/skills/<skill-name>/SKILL.md` using the config values as
  frontmatter fields
