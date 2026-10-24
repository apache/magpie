<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-fix — the Step 0 checks

Step 0 of [`SKILL.md`](../SKILL.md#step-0--pre-flight-check), check by check.
Relative links are rooted one level deeper than in `SKILL.md`.

1. **`gh` authenticated** — `gh api repos/<tracker> --jq .name` and `gh api repos/<upstream> --jq .name` both return.
   A 401/403 on the first means no `<tracker>` access; on the second it is a quota/auth issue — both need user action, stop.
2. **Fork exists and is pushable** — `gh repo view <your-login>/<upstream-repo-name> --json name --jq .name` returns the bare repo name (the segment after the `/` in `<upstream>`).
   If there is no fork, tell the user to run `gh repo fork <upstream> --clone=false` and re-invoke.
3. **Local clone is found and clean** — resolve the clone path from [the resolved `user.md` ([order](../../../../../AGENTS.md#usermd-resolution-order))](../../../../../docs/setup/agentic-overrides.md) → `environment.upstream_clone` (per [`AGENTS.md` § Per-project and per-user configuration](../../../../../AGENTS.md#per-project-and-per-user-configuration)).
   Verify its `origin` remote points at `<upstream>` and `git status --porcelain` is empty.
   On uncommitted work, stop and ask the user to stash / commit / clean first.
   Do not probe hard-coded filesystem paths.
4. **Base branch is current** — `git fetch origin` and make sure the base (default `<default-branch>`, or the branch the user specified) is a fast-forward of `origin/<base>`.
5. **Toolchain probe** — run the tool-version checks named in [`<project-config>/fix-workflow.md`](../../../../../<project-config>/fix-workflow.md#toolchain).
   Any missing tool stops the skill; installing tools mid-run is out of scope.
6. **Privacy-LLM gate-check** passes:

   ```bash
   uv run --project <framework>/tools/privacy-llm/checker \
     privacy-llm-check
   ```

   The redact-after-fetch protocol ([`tools/privacy-llm/wiring.md`](../../../../../tools/privacy-llm/wiring.md)) applies to the Step 1 sync's fetch of the `<tracker>` issue body and comments.
