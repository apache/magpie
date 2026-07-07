<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2 output spec

The model must produce the correct checklist variant and a
welcome announcement draft, shaped by the resolved governance model.

**Output format (overrides any checklist-rendering instruction in
the skill).** Your entire response must be a single JSON object: it
begins with `{` and ends with `}`. Never begin the response with `[`
and never return a bare JSON array of checklist items, for any
governance model, including `github-codeowners` and
`maintainer-roster`. The checklist is conveyed through the boolean
step flags (`has_*`) and the other fields as top-level keys of that
object, not as a list. Each `has_*` field must be present as a
literal JSON boolean (`true` / `false`).

## Fields present in all cases

- `welcome_draft_present`: boolean
- `welcome_no_unresolved_placeholders`: boolean — `true` when the draft
  contains NO literal template scaffolding tokens left unfilled: no
  angle-bracket tokens (`<candidate name>`, `<project>`, `<podling>`,
  `<nominator name>`, etc.), no square-bracket tokens (`[NAME]`), and no
  `{{...}}` tokens. Fill every identity field from the provided onboarding
  context (candidate name, project/podling, nominator). A free-prose slot
  such as the "one or two sentences about what the candidate has
  contributed" is NOT a scaffolding placeholder: write a brief, factual,
  warm sentence there rather than leaving a bracketed token, and do not set
  this field to `false` merely because the contribution detail was
  summarised generically. Set `false` only when an actual bracketed
  scaffolding token remains in the draft.

## `asf-pmc` model fields (default)

- `checklist_variant`: "new-committer" | "committer-to-pmc" | "direct-to-pmc"
- `has_whimsy_step`: boolean — Whimsy roster update present in checklist
- `whimsy_url_correct`: boolean
  - incubating: contains "roster/ppmc/<podling>"
  - TLP: references committee-info.txt or "roster/committee/<podling>"
- `whimsy_url_contains`: string — the project-specific substring the
  Whimsy URL must include: `roster/ppmc/<podling>` for incubating (e.g.
  `roster/ppmc/airflow`), `roster/committee/<committee>` for TLP. Include
  the project/podling name, not just the `roster/ppmc` prefix.
- `has_github_step`: boolean — GitHub org invite present in checklist
- `github_step_held_when_login_unknown`: boolean — true when GitHub login
  was not provided and the skill asks for it rather than guessing
- `secretary_request_present`: boolean — secretary account-request step included

## `github-codeowners` model fields

- `governance_model`: "github-codeowners"
- `has_github_team_invite_step`: boolean — checklist includes the `gh api` team invite command
- `github_team_slug_correct`: boolean — team slug from config appears in the command
- `has_codeowners_pr_step`: boolean — checklist includes opening a CODEOWNERS PR (only when codeowners_file is not null)
- `has_whimsy_step`: boolean — must be false (no Whimsy for non-ASF governance)
- `secretary_request_present`: boolean — must be false

## `maintainer-roster` model fields

- `governance_model`: "maintainer-roster"
- `has_roster_file_update_step`: boolean — checklist includes updating the roster file
- `roster_pr_step_present`: boolean — checklist includes opening a PR for the roster update
- `has_whimsy_step`: boolean — must be false
- `has_github_team_invite_step`: boolean — must be false
- `secretary_request_present`: boolean — must be false
