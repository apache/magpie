<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-model-verify — the bundled helper

## The bundled helper

[`scripts/model_pr.py`](scripts/model_pr.py) collapses fork → clone → write the
scaffold (create-or-append, idempotent) → commit → push → open the PR into one
command. The create-versus-append branch on `SECURITY.md` and `AGENTS.md` is the
fiddly part — it must create the file when absent and append exactly one section
when present, without touching a line of existing prose — so it is a tested pure
function rather than something re-derived per repository.

```bash
# In-repo model: lands the model file and wires AGENTS.md -> SECURITY.md -> it.
python3 <skill-dir>/scripts/model_pr.py open \
  --repo <owner>/<name> \
  --model /path/to/THREAT_MODEL.md \
  --date <YYYY-MM-DD> \
  --title "<title>" \
  --body-file "$TMPDIR/model-pr-body.md" \
  --dry-run

# Pointer: a satellite repository deferring to an umbrella model elsewhere.
python3 <skill-dir>/scripts/model_pr.py open \
  --repo <owner>/<name> \
  --pointer https://github.com/<owner>/<umbrella>/blob/main/THREAT_MODEL.md \
  --date <YYYY-MM-DD> \
  --agents-note "This repository is build-time tooling for <PROJECT>." \
  --dry-run
```

`<skill-dir>` is the directory holding this skill's `SKILL.md`; `<framework>/skills/` does not exist on a marketplace install.

Always run `--dry-run` first and show the diff. Without `--submit` the final step
is `gh pr create --web`, so the human still submits from the browser. When `--workdir`
points to an existing directory or when running a real run after `--dry-run` with
the same `--workdir`, pass `--overwrite` to reuse it.

`--license-header` picks what the created files carry: `spdx` (default),
`apache-full` (the canonical boilerplate — some license checkers match only
that form and not the SPDX identifier), or `none`. `--report-to` supplies the
private reporting address a newly created `SECURITY.md` needs;
`--branch-prefix` and `--base` adapt to the project's branch conventions.
