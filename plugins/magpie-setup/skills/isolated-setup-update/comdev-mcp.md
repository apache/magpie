<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Check 5 — comdev MCP checkouts (`ponymail`, `apache-projects`)

Read from `SKILL.md` § *What to check* when either server is registered in the user or project `mcpServers` config.

   These ASF MCP servers are installed from a local `apache/comdev` checkout and are **tracked at `main`, not pinned**.
   Unlike the system tools in check 2, there is no cooldown and no manifest bump, because comdev ships them as in-repo source with no tagged releases (see [`tools/ponymail/tool.md` → Keeping the checkout current](../../../../tools/ponymail/tool.md#keeping-the-checkout-current)).
   For each server registered in the user/project `mcpServers` config, resolve the checkout root from its `args` path (`<comdev>/mcp/<server>/index.js`), then:
   - Confirm `origin` is an `apache/comdev` URL and the checkout is on `main` (`git -C <root> rev-parse --abbrev-ref HEAD`).
     Flag a detached HEAD / feature branch as drift; remediation `git -C <root> checkout main`.
   - Run `git -C <root> fetch origin main` (the live fetch the read-only verify skill defers to update) and report the behind-count (`git -C <root> rev-list --count HEAD..origin/main`).
     When behind, print — do not run — the refresh commands:

     ```bash
     git -C <root> pull --ff-only
     ( cd <root>/mcp/<server> && npm install )
     ```

   Surface the upstream compare link (`https://github.com/apache/comdev/compare/<local-sha>...main`) so the operator can see what changed before pulling.
   Do not pull or `npm install` for them — the fast-forward stays an explicit, user-run step, same as the framework-checkout pull in check 1.
