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
Print this script instead, unchanged.
It reads the registration in the operator's own shell, so it works from any directory, in bash or zsh; it needs `jq`, in `/usr/bin` on macOS 15 and later.
It covers every registration it finds, user-scope and per-project in `~/.claude.json` plus a `.mcp.json` in the current directory, and makes the same checks as the steps above: an `apache/comdev` origin, the `main` branch, a fetch that succeeded.
A checkout failing one of them is reported and skipped, never counted.

```bash
refresh=no  # yes: fast-forward the checkouts that are behind, then npm install
for f in ~/.claude.json .mcp.json; do
  [ -f "$f" ] && jq -r '
      ((.mcpServers // {}), ((.projects // {})[] | .mcpServers // {}))
      | to_entries[] | select(.key == "ponymail" or .key == "apache-projects")
      | . as $e | [$e.value.args[]? | select(type == "string" and endswith("index.js"))][0] // empty
      | "\($e.key)\t\(.)"' "$f"
done | sort -u | {
  found=no; refreshed=" "
  while IFS=$'\t' read -r s js; do
    found=yes; d=$(dirname "$js")
    root=$(git -C "$d" rev-parse --show-toplevel 2>/dev/null) || { echo "$s: $d is not a git checkout"; continue; }
    url=$(git -C "$root" config --get remote.origin.url)
    case "$url" in
      *github.com[:/]apache/comdev|*github.com[:/]apache/comdev.git) ;;
      *) echo "$s: origin of $root is '$url', not apache/comdev; skipped"; continue ;;
    esac
    br=$(git -C "$root" rev-parse --abbrev-ref HEAD)
    [ "$br" = main ] || { echo "$s: $root is on '$br', not main; run: git -C '$root' checkout main"; continue; }
    git -C "$root" fetch -q origin main || { echo "$s: fetch failed in $root; not checked"; continue; }
    n=$(git -C "$root" rev-list --count HEAD..origin/main)
    echo "$s: $d is $n commit(s) behind; changes: https://github.com/apache/comdev/compare/$(git -C "$root" rev-parse HEAD)...main"
    [ "$refresh" = yes ] || continue
    if [ "$n" -gt 0 ]; then
      git -C "$root" merge -q --ff-only origin/main || { echo "$s: fast-forward failed in $root"; continue; }
      refreshed="$refreshed$root "
    fi
    case "$refreshed" in *" $root "*) ( cd "$d" && npm install ) ;; esac
  done
  [ "$found" = yes ] || echo "no ponymail or apache-projects registration in ~/.claude.json or ./.mcp.json"
}
```

As printed it only reports.
When it shows a checkout behind, the operator reads the compare link, then runs it again with `refresh=yes`.
That fast-forwards to the `origin/main` just checked, never to another branch's upstream, and runs `npm install` in each server's own directory, including the second server of a checkout both share.
Restart the agent afterwards so the servers reload.
