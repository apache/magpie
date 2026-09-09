<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The collector emitted this dashboard:

```markdown
## apache-magpie adoption — myproject

**mode:** git-branch · **pinned:** main · **verdict:** ✅ healthy

### Agent targets

| Target | Dir | Kind | Skills | Status |
|---|---|---|---|---|
| universal | `.agents/skills` | canonical-snapshot | 12 | ✅ wired |
| claude-code | `.claude/skills` | relay | 12 | ✅ wired |

**serves** (which agents read each target dir):

- `universal` — Codex, Cursor, Gemini CLI, GitHub Copilot, OpenCode, Cline, Zed, Warp, Amp, …
- `claude-code` — Claude Code

### Skill families

| Family | Type | Installed |
|---|---|---|
| security | opt-in | ✅ 12 |
| pr-management | opt-in | — none |

### Drift & integrity

- **drift:** ✅ in sync · **snapshot:** present
- **shared overrides** (`.apache-magpie-overrides/`): present (1 skill(s)) · **personal overrides** (`.apache-magpie-local/`): —
- **hook:** installed
- → deep check (integrity, permissions, worktrees): `setup verify`
```
