<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `[A]pprove NN` — submit your APPROVE review

The express-lane case: a trivial, all-green PR with no approval yet. The approve is **your** review, assistant-proposed and maintainer-fired — `capability:review`, not an automated merge.

1. **Fresh reads**, then the protocol check:

   ```bash
   uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-quick-merge --save express-one-NN.json gql-pr-express-one NN
   uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-quick-merge --save live-NN.json pr-live-state NN
   uv run --project <framework>/tools/pr-management pr-management quick-merge approve-check --saved-dir <workspace>/saved --pr NN --head <head_sha> \
     --session <scratch>/quick-merge-session.json [--out-dir <scratch> --viewer <viewer>]
   ```

   It refuses when approvals are disabled, when the diff was not viewed this session (or was viewed at another head), when the head moved since the screen, when any Stage-1 gate regressed, or when the branch now conflicts — show its `reason` and re-screen. `needs` lists any read still missing.
2. **Ask** with its `confirm` text, word for word. Anything but `y` cancels.
3. **Run its `command`** — `gh pr review NN --repo <upstream> --approve`, with `--body-file` only when the project set `approve_body` (the tool wrote that file, with its attribution line). Never edit the command; never add `--admin` or any bypass.
4. **Record it:** `uv run --project <framework>/tools/pr-management pr-management quick-merge session approve --session <scratch>/quick-merge-session.json --pr NN --head <head_sha>`, so this session does not propose it again.
5. Print its `note` when present (*"the repo requires N approvals; this adds 1"*), then the `merge_command` for the maintainer to run themselves.
