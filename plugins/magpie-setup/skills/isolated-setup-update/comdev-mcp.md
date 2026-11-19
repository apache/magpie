<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Check 5 — comdev MCP checkouts (`ponymail`, `apache-projects`)

Read from `SKILL.md` § *What to check* when either server is registered in the user or project `mcpServers` config.

   These ASF MCP servers are installed from a local `apache/comdev` checkout and are **tracked at `main`, not pinned**.
   Unlike the system tools in check 2, there is no cooldown and no manifest bump, because comdev ships them as in-repo source with no tagged releases (see [`tools/ponymail/tool.md` → Keeping the checkout current](../../../../tools/ponymail/tool.md#keeping-the-checkout-current)).
   For each server registered in the user/project `mcpServers` config, take two paths from the `index.js` in its `args`:
   - `<server-dir>` is the directory that holds that `index.js`, such as `/home/me/code/comdev/mcp/ponymail-mcp`.
     It is **not** `mcp/<server name>`: the directories are `mcp/ponymail-mcp` and `mcp/apache-projects-mcp`, while the registered names are `ponymail` and `apache-projects`.
   - `<root>` is the checkout root, `git -C <server-dir> rev-parse --show-toplevel`.

   Every command you print carries those resolved absolute paths, never a placeholder: the operator pastes it into a shell as it stands.
   Then:
   - Confirm `origin` is an `apache/comdev` URL and the checkout is on `main` (`git -C <root> rev-parse --abbrev-ref HEAD`).
     Flag a detached HEAD / feature branch as drift; remediation `git -C <root> checkout main`.
   - Run `git -C <root> fetch origin main` (the live fetch the read-only verify skill defers to update) and report the behind-count (`git -C <root> rev-list --count HEAD..origin/main`).
     When behind, print — do not run — the refresh commands, one `npm install` per registered server:

     ```bash
     git -C <root> pull --ff-only
     ( cd <server-dir> && npm install )
     ```

   Surface the upstream compare link (`https://github.com/apache/comdev/compare/<local-sha>...main`) so the operator can see what changed before pulling.
   Do not pull or `npm install` for them — the fast-forward stays an explicit, user-run step, same as the framework-checkout pull in check 1.

## When the registration cannot be read

Under the secure setup the sandbox denies `~/.claude.json`, where Claude Code keeps `mcpServers`, so the agent may not learn either path.
Do not hand the operator a command with a placeholder in it.
Print this check instead, unchanged; it reads the registration in the operator's own shell and works from any directory (it needs `jq`, in `/usr/bin` on macOS 15 and later):

```bash
for s in ponymail apache-projects; do
  js=$(jq -r --arg s "$s" '[.mcpServers[$s]?, .projects[]?.mcpServers[$s]?]
        | map(select(. != null)) | first | .args[]? | select(endswith("index.js"))' ~/.claude.json)
  [ -n "$js" ] || { echo "$s: not registered"; continue; }
  d=$(dirname "$js"); git -C "$d" fetch -q origin main
  echo "$s: $d is $(git -C "$d" rev-list --count HEAD..origin/main) commit(s) behind"
done
```

When it reports a server behind, the refresh is the same loop with its last two lines replaced:

```bash
for s in ponymail apache-projects; do
  js=$(jq -r --arg s "$s" '[.mcpServers[$s]?, .projects[]?.mcpServers[$s]?]
        | map(select(. != null)) | first | .args[]? | select(endswith("index.js"))' ~/.claude.json)
  [ -n "$js" ] || continue
  d=$(dirname "$js"); git -C "$d" pull --ff-only && ( cd "$d" && npm install )
done
```

Both servers usually share one checkout, so the second `pull` finds nothing new; its `npm install` still runs for that server's own directory.
Restart the agent afterwards so the servers reload.
