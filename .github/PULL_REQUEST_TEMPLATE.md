<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Summary

<!--
1-3 bullets: what changed and why. The "why" is what reviewers care
about most — a one-line summary of the motivation beats a paragraph
restating the diff.
-->

-

## Type of change

<!-- Tick all that apply. -->

- [ ] Skill change (`.claude/skills/<name>/`) — eval fixtures updated below
- [ ] Tool / bridge contract (`tools/<system>/*.md`)
- [ ] Python package (`tools/*/` with `pyproject.toml`)
- [ ] Groovy reference impl
- [ ] Cross-cutting (RFC, AGENTS.md, sandbox, privacy-LLM)
- [ ] Documentation (`docs/`, `README.md`, `CONTRIBUTING.md`)
- [ ] Project template (`projects/_template/`)
- [ ] CI / dev loop (`prek`, workflows, validators)
- [ ] Other:

## Test plan

<!--
How you verified the change. Be specific. The reviewer reads this to
decide what to spot-check vs trust. Empty "ran the tests" doesn't help.
-->

- [ ] `prek run --all-files` passes
- [ ] For Python packages touched: `uv run pytest` / `ruff check` / `mypy` passes
- [ ] For Groovy bridges touched: command-line invocation tested end-to-end
- [ ] For skill changes: eval suite passes for the affected skill
      (`PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner tools/skill-evals/evals/<skill>/`)
- [ ] For skill *behaviour* changes: a new or updated eval fixture is included in this PR
      (a regression test for the bug fixed / the behaviour added — see CONTRIBUTING.md)
- [ ] Other:

## RFC-AI-0004 compliance

<!--
Tick the principles the change touches. Skip rows that don't apply.
RFC-AI-0004 is the framework's constitution — see
docs/rfcs/RFC-AI-0004.md.
-->

- [ ] **HITL** — any new mutation is gated on explicit user confirmation
- [ ] **Sandbox** — no new unrestricted host access; network reach declared in the adapter
- [ ] **Vendor neutrality** — placeholders (`<PROJECT>`, `<tracker>`, `<upstream>`, `<security-list>`) used in all skill / tool prose (the `check-placeholders` prek hook is the mechanical gate)
- [ ] **Conversational + correctable** — agentic-override path documented if behaviour is adopter-tunable
- [ ] **Write-access discipline** — no autonomous outbound messages; drafts only, sent on confirmation
- [ ] **Privacy LLM** — private content does not reach a non-approved LLM; redactor invoked where needed

## Linked issues

<!-- e.g. Closes #NNN, Refs #NNN. List every related issue. -->

## Notes for reviewers (optional)

<!--
Anything specific you want the reviewer to look at. Areas of uncertainty.
Trade-offs you considered and rejected. Decisions that the agent and you
disagreed on during the authoring loop.
-->
