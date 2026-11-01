<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**Write lock (one write phase per skill per repository).** The read and
classify steps above have no side effects and may overlap with any other
run. Posting does: two overlapping runs of this skill over the same
repository post the same comment or label twice, which is what makes
contributors distrust the bot. So before the first write of this step,
take the skill's write lock:

```bash
uvx --from ~/.claude/magpie/skill-lock skill-lock acquire {override_name} --repo <upstream> --note "<selector or pool summary>"
```

- Exit `0` (`status: acquired`): proceed. Keep the `token` from the JSON
  result for the release below. Then, **just before each write, re-read
  that item** and skip it if this skill's marker (its proposal comment or
  label) landed after your classify read: a run that classified before
  another run posted can reach its write step after that run released
  the lock. List skipped items in the recap as already handled.
- Exit `3` (`status: already_running`): **stop here and post nothing.**
  Show the maintainer the `holder` record (started, expires, note) and
  say this is not a failure of the sweep: another run of this skill is
  writing to the same repository. If the maintainer knows that run is
  dead, they clear it with the `--force` command in the result's `hint`
  and re-run this step; never clear it on your own.
- Exit `2`: report the error and stop.

Release it after the recap, and **also on the stop-and-surface path** when
a post fails, so a failed run never leaves the lock held for its lease:

```bash
uvx --from ~/.claude/magpie/skill-lock skill-lock release {override_name} --repo <upstream> --token <token>
```

The lock is scoped to this skill and `<upstream>` only; other skills and
other repositories never contend. It lives in the personal config layer
(`run/locks/`), never in the working tree, so it serialises runs from one
clone only. Runs from another clone or another machine are caught by the
re-read before each write, not by the lock. Details and exit codes:
[`tools/skill-lock/README.md`](../../../../tools/skill-lock/README.md).
