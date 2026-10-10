<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Prerequisites — pre-flight checks

The skill performs three pre-flight checks before reviewing any
PR. Failures of check 1 are a hard stop; checks 2 and 3 degrade
gracefully with a one-line warning each.

---

## 1. `gh` authentication and collaborator access (HARD STOP)

```bash
gh auth status
```

Required outcome: the active account is logged in and the
selected protocol works (the skill uses HTTPS GraphQL queries via
`gh api`; SSH-only setups are fine because the API path doesn't
go through SSH).

The active account must additionally be a **collaborator** on
the target repo (`<upstream>` by default): without collaborator
access the eventual post returns `HTTP 403: Resource not accessible
by integration` and nothing else. Read the login and the permission:

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-code-review viewer
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-code-review --save permission.txt upstream-permission <viewer>
```

`admin` or `write` is sufficient (the field carries the legacy values
only: `maintain` reports as `write`, `triage` as `read`).
`read` is not enough to post reviews; warn and offer `dry-run` mode
(which drafts but does not post).

The saved permission also decides which `COMMENT` footer `render`
uses: GitHub blocks `APPROVE` / `REQUEST_CHANGES` from an account
without write access, but a `COMMENT` can still post after the warning
above, so its footer must not claim a maintainer confirmed it unless
this check says so.

If `gh auth status` fails entirely, surface it and ask the
maintainer to run `gh auth login`. Do not proceed.

---

## 2. Resolve adversarial-reviewer configuration (DEGRADES)

Adversarial-reviewer integration is opt-in, and comes in two shapes:
**model CLIs** the agent runs through the `magpie-adversarial-review`
tool (the *tool path*), or a **slash command** the maintainer types
(the *slash path*). The skill does not scan installed extensions; the
tool's own `detect` is only consulted for what the maintainer named.

In priority order, first match wins:

1. **`no-adversarial`** on the current invocation → no reviewer this
   session (still announce: *"adversarial reviewer disabled for this
   session"*).
2. **`with-reviewers:<list>`** → the tool path, with exactly that list
   (comma-separated backend names: `codex`, `copilot`, `gemini`,
   `grok`, `claude`).
3. **`with-reviewer:<command>`** → the slash path, with that command.
4. **`adversarial-review.md`** (`.apache-magpie-local/` first, then
   `.apache-magpie-overrides/`) with a non-empty `reviewers` list and
   `mode` other than `off` → the tool path, with the configured list.
   A code review is itself a request for a review, so `on-demand`
   counts here.
5. **Project-scope `AGENTS.md`** at the repo root, if it has a
   `## Review preferences` (or equivalent) section that names a slash
   command → the slash path.
6. **Harness-specific project file** (e.g. `.claude/CLAUDE.md`) under
   the working directory, same convention.
7. **User-scope harness file** (e.g. `~/.claude/CLAUDE.md`), same
   convention.

The tool path needs the `magpie-adversarial-review` plugin. When it was
selected but the plugin is not installed, say so with the install
command (`/plugin install magpie-adversarial-review@apache-magpie`) and
continue with the next rule — rule 3 when `with-reviewers:` selected it,
rule 5 when the configuration did.

Announce the result once at session start:

> *Adversarial reviewers configured: codex, copilot (run by me through
> the adversarial-review tool after my own review of each PR; each
> PR's diff, title and body go to those models' providers).*

> *Adversarial reviewer configured: `<COMMAND>`. After my review of each
> PR I'll propose typing it so we get a second read.*

> *No adversarial reviewer configured. Reviews this session use only my
> own pass. Pass `with-reviewers:codex,copilot` (model CLIs) or
> `with-reviewer:<command>` (a slash command) next time if you want a
> second read.*

See [`adversarial.md`](adversarial.md) for the full integration
mechanics — including why the assistant proposes the slash
command but never fires it.

---

## 3. Resolve the selector and compute working set (DEGRADES)

Save the open-PR sweep and build the queue:

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-code-review --save cr-open.json gql-cr-open
uv run --project <framework>/tools/pr-management pr-management code-review queue --saved-dir <workspace>/saved --viewer <viewer> <selector…>
```

The first run lists what else it needs under `needs` — the ownership
file (`cr-codeowners-github`, falling back to `cr-codeowners-root`
then `cr-codeowners-docs` on a 404), each `CODEOWNERS` team's roster
(`team-members`, the team's own membership — not the organisation's),
the viewer's base-branch commits for touching-mine
(`cr-viewer-commits`) and each commit's files (`cr-commit-files`).
Save them and run `queue` again until `needs` is empty; the reads
are cached for the session in the saved directory.

Announce `announcements` once (an empty touching-mine set, a missing
`CODEOWNERS`). When the queue is empty, print `empty_message` and
exit — never widen the search silently.

---

## CI precheck (per PR, not per session)

`context` reports the PR's rollup state and whether real CI ran (`ci`), and `disposition` applies them:

- `SUCCESS` with real CI — `APPROVE` stays on the table.
- `PENDING` — flag it in the headline ("CI still running"); the maintainer may defer with `[S]kip-for-now`.
- `FAILURE` / `ERROR` — `APPROVE` is off the table (Golden rule 8); `COMMENT`, or `REQUEST_CHANGES` when you judge the failure diff-caused.
- `EXPECTED` (workflow approval pending) — recommend `pr-management-triage pr:<N>` for the workflow-approval flow first; do not review a PR whose CI has not run.

### Real-CI guard

**Mandatory whenever the rollup reads `SUCCESS`.** Fast bot checks
(`Mergeable`, `WIP`, `DCO`, `boring-cyborg`) succeed unconditionally, so on
a PR whose real workflows are held in `action_required` the bots alone pull
the rollup to `SUCCESS` while nothing has been built, linted or tested.
The guard is the shared rule in
[`tools/pr-management` → Shared rules](../../../../tools/pr-management/README.md#shared-rules)
(the adopter's `real_ci_patterns`); `context` and `queue` apply it:

- the headline says `CI: no real CI has run (bot checks only)` rather than passing;
- `APPROVE` is off the table — Golden rule 8 covers a PR whose real CI never ran exactly as it covers one that fails;
- `queue` ranks it **below** every PR with a real run, however small the diff;
- report what reading the code established and say plainly that CI is unverified — never "approvable once CI runs".

Releasing the held workflow runs is a triage action: point the
maintainer at `pr-management-triage pr:<N>`.

---

## Browser-open availability (DEGRADES)

The sandbox blocks the OS opener (`open`, `xdg-open`, `start`), so the
skill never launches a browser itself. On the Step 1 `[y]`, hand the
maintainer the files-tab URL (`files_tab` from `context`) as
`! open <url>` to run themselves, or print it to click — the PR URL is
always on the headline anyway (Golden rule 10).

---

## Repo override

If the maintainer passes `repo:<owner>/<name>`, all checks
target that repo. For repos that aren't `<upstream>`, also
check that the conventional `area:*` labels exist (since
[`classifications/selector-area.md`](classifications/selector-area.md) supports `area:` filters):

```bash
gh label list --repo <repo> --search "area:" --limit 1
```

(a bare `gh` command; the `repo:` override also needs a vetted-ops
policy whose `upstream` is that repository, passed with `--config`).

If no `area:` labels exist, warn:

> *No `area:*` labels on `<repo>`. The `area:` selector will
> match nothing here.*

…and proceed with the rest of the selector.
