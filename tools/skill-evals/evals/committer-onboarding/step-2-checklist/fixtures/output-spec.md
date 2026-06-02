# Step 2 output spec

The model must produce the correct checklist variant and a
welcome announcement draft. Evaluated fields:

- `checklist_variant`: "new-committer" | "committer-to-pmc" | "direct-to-pmc"
- `has_github_step`: boolean — GitHub org invite present in checklist
- `has_whimsy_step`: boolean — Whimsy roster update present
- `whimsy_url_correct`: boolean
  - incubating: contains "roster/ppmc/<podling>"
  - TLP: references committee-info.txt or "roster/committee/<podling>"
- `whimsy_url_contains`: string — the substring the Whimsy URL must include
  (the PPMC vs. PMC discriminator: e.g. `roster/ppmc` for incubating,
  `roster/committee` for TLP)
- `welcome_draft_present`: boolean
- `welcome_no_unresolved_placeholders`: boolean
- `github_step_held_when_login_unknown`: boolean — true when GitHub login
  was not provided and the skill asks for it rather than guessing
