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
It reads the registration in the operator's own shell, so it works from any directory, pasted into bash or zsh; it needs `jq`, in `/usr/bin` on macOS 15 and later.
It reads only `~/.claude.json`, user-scope and per-project registrations alike, and only an absolute `index.js` path in them: never a `.mcp.json`, which a cloned repository or a sandboxed agent can write, while the sandbox can neither read nor write `~/.claude.json`.
It makes the same checks as the steps above: an origin that is exactly `apache/comdev` on GitHub, as `git remote get-url` reports it after any `insteadOf` rewrite; the `main` branch; a fetch that succeeded.
A checkout failing one of them is reported and skipped, never counted.
Its `git fetch` and `git merge` run with `core.hooksPath=/dev/null`, so no hook in the checkout runs outside the sandbox.
It runs in a subshell, so its `exit` cannot close the operator's terminal and its variables do not stay behind, and it carries no `#` comments, which interactive zsh does not treat as comments by default.

```bash
(
refresh=
command -v jq >/dev/null || { echo "jq is not installed; install it and run this again"; exit 1; }
[ -r ~/.claude.json ] || { echo "cannot read ~/.claude.json, where Claude Code registers MCP servers"; exit 1; }
regs=$(jq -r '
    [.mcpServers?, ((.projects? // {}) | objects | .[]? | objects | .mcpServers?)]
    | .[] | objects | to_entries[] | select(.key == "ponymail" or .key == "apache-projects")
    | . as $e | [$e.value | objects | .args[]? | strings | select(startswith("/") and endswith("/index.js"))][0] // empty
    | "\($e.key)\t\(.)"' ~/.claude.json) || { echo "could not parse ~/.claude.json"; exit 1; }
regs=$(printf '%s\n' "$regs" | sort -u)
[ -n "$regs" ] || { echo "no ponymail or apache-projects registration in ~/.claude.json"; exit 0; }
ok=""
while IFS=$'\t' read -r s js; do
  [ -n "$s" ] || continue
  d=$(dirname "$js")
  root=$(git -C "$d" rev-parse --show-toplevel 2>/dev/null) || { echo "$s: $d is not a git checkout"; continue; }
  url=$(git -C "$root" remote get-url --all origin 2>/dev/null)
  case "$url" in
    https://github.com/apache/comdev|https://github.com/apache/comdev.git) ;;
    git@github.com:apache/comdev|git@github.com:apache/comdev.git) ;;
    ssh://git@github.com/apache/comdev|ssh://git@github.com/apache/comdev.git) ;;
    *) echo "$s: origin of $root is '$url', not apache/comdev; skipped"; continue ;;
  esac
  br=$(git -C "$root" rev-parse --abbrev-ref HEAD)
  [ "$br" = main ] || { echo "$s: $root is on '$br', not main; run: git -C '$root' checkout main"; continue; }
  up=$(git -c core.hooksPath=/dev/null -C "$root" fetch -q origin main </dev/null && git -C "$root" rev-parse --verify -q FETCH_HEAD) || { echo "$s: fetch failed in $root; not checked"; continue; }
  n=$(git -C "$root" rev-list --count "HEAD..$up") || { echo "$s: cannot compare $root with the fetched main; not checked"; continue; }
  echo "$s: $d is $n commit(s) behind apache/comdev main at $up; changes: https://github.com/apache/comdev/compare/$(git -C "$root" rev-parse HEAD)...$up"
  ok="$ok$s"$'\t'"$d"$'\t'"$root"$'\t'"$up"$'\n'
done <<EOF
$regs
EOF
if [ -z "$refresh" ]; then
  [ -z "$ok" ] || echo "to update, read the changes, then run this again with refresh=<the commit after 'main at'>"
  exit 0
fi
while IFS=$'\t' read -r s d root up; do
  [ -n "$s" ] || continue
  target=$(git -C "$root" rev-parse --verify -q "$refresh^{commit}") && git -C "$root" merge-base --is-ancestor "$target" "$up" || { echo "$s: $refresh is not on the main just fetched for $root; nothing changed"; continue; }
  git -c core.hooksPath=/dev/null -C "$root" merge -q --ff-only "$target" </dev/null || { echo "$s: fast-forward failed in $root"; continue; }
  if ( cd "$d" && npm install </dev/null ); then echo "$s: $d is at $target, npm install done"
  else echo "$s: npm install failed in $d; run this again to retry"; fi
done <<EOF
$ok
EOF
)
```

As printed it only reports: one line per registered server, with the commit on `apache/comdev` `main` it was compared with.
When a checkout is behind, the operator reads the compare link, then runs the script again with `refresh=` set to the commit that line printed after `main at`.
That run fetches again but fast-forwards to the commit the operator reviewed, never past it, and only when that commit is on the `main` just fetched.
It runs `npm install` in every checked server's own directory, so two servers sharing a checkout end on the same commit, and a run after a failed install retries it.
Restart the agent afterwards so the servers reload.
