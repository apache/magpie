<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Pick the intervention

`mentor assess` returned `outcome: draft`: no hand-off trigger fired and no maintainer is engaged.
Choosing the intervention is your call. Match the thread against the four interventions and the configured `pointers`:

- **Exactly one fits** → read its file and render it: [`intervention-missing-repro.md`](intervention-missing-repro.md), [`intervention-missing-version.md`](intervention-missing-version.md), [`intervention-convention-pointer.md`](intervention-convention-pointer.md), [`intervention-why-question.md`](intervention-why-question.md).
- **Several fit** → ask the maintainer which one to lead with; one comment, one ask.
- **None fits** → the thread is on track: exit silently, record `declined-pre-draft`.

Deliberately not templates: a greeting or welcome (the maintainer's relationship to start), a closing comment (triage owns closes), any approval or "looks good", and praise.
