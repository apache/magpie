<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 6c — Nexus staging repository (ASF projects publishing Maven artefacts)

**When it runs.** Only when all of these hold; otherwise skip this
step cleanly and state the skip explicitly, do not silently pass:

- the Step 1 listing contains at least one `.jar` or `.pom`
  (JVM-only — a Python or Rust ASF project has no staging repository
  and must not be warned about one);
- `release-build.md § JVM artefact checks` does not declare
  `jvm_artefact_checks: off`;
- 🪶 ASF-specific: the resolved `organization` of the adopter
  (`<project-config>/project.md` → `organization`, the same chain
  Step 9's automated-signing gate reads) is `ASF` —
  `repository.apache.org` is ASF infrastructure, and a non-ASF
  adopter has nothing to probe;
- a staging repository id is resolvable, in this order: the
  `nexus_staging_repo` key of `release-build.md § JVM artefact
  checks`; then the planning issue body when `--post-to` was passed
  (look for a `nexus-staging-repo:` or staging-repository URL line).
  Nexus assigns the id (`orgapache<project>-NNNN`) at deploy time and
  it cannot be predicted, so an unresolvable id is a clean `SKIP`
  naming where to supply it — never a guess. The resolved id is then
  validated before it reaches a URL: it must match the Nexus shape
  (`orgapache<project>-NNNN`, digits and lowercase only) — the
  planning issue body is content the step reads, and the id is
  spliced into `curl` URLs the agent runs itself. A value that does
  not match is a `SKIP` naming the bad value, never a probe; the
  literal `snapshots` passes validation and is then flagged by the
  classification rules.

Step 6b verified the jars and POMs staged **locally**. For an ASF JVM
project the jars downstream consumers actually resolve are staged in
the Nexus staging repository at `repository.apache.org` and promoted
to Maven Central after the vote — the surface this step verifies,
with the [`asf-nexus`](../../../../tools/asf-nexus/README.md)
adapter (blocking check 4 of
[issue #1173](https://github.com/apache/magpie/issues/1173)): the
staged repository is `closed` (not `open`), its coordinates and
version match the RC under vote, and every artefact in it carries its
`.asc` signature and checksums with a complete companion set. The
endpoint contract and recipes are the adapter's
[`operations.md`](../../../../tools/asf-nexus/operations.md); the
classification rules below are its
[`staging-verification.md`](../../../../tools/asf-nexus/staging-verification.md)
in short form.

**Credentials and the sandbox.** The authenticated staging-API reads
need ASF Nexus credentials stored as a netrc-format file at
`~/.config/apache-magpie/asf-nexus/netrc` (`machine
repository.apache.org login <user> password <pass>`, `chmod 600` —
never a `-u user:pass` on the command line, which exposes the
password in `ps` and transcripts). `~/.config/` is denied to the
sandboxed agent by design, so these two recipes are for the RM to
paste into their **own** terminal; the agent's own run takes the
anonymous path and reports `STATE-UNVERIFIED` for the state question.
That is the expected voter shape, not a verification failure — and a
sandbox network refusal (the probe blocked before it left the
machine) is likewise reported as `STATE-UNVERIFIED` / not-probed,
never as "repository not reachable": one says "the runner could not
see", the other says "nothing is there".

Emit the paste-ready recipe per the adapter's recipes with every
placeholder resolved: `<repo>` is the staging repository id resolved
above; the anonymous existence check and the artefact-inventory crawl
run for every runner; the authenticated state check and the
profile-wide listing run only for an RM pasting into their own
terminal.

**Golden rule:** this step performs read-only `GET`s against
`repository.apache.org`, nothing else. It never closes, drops, or
promotes a staging repository — a promotion is irreversible (promoted
artefacts sync to Maven Central, where they are immutable), and any
voter, including one with no karma on the target repository, must be
able to run this step.

Return ONLY valid JSON with this structure:

```json
{
  "step": "nexus-staging",
  "status": "PASS" | "WARN" | "FAIL" | "SKIP",
  "staging_repos": [
    {"id": "<repository id>", "state": "closed" | "open" | "unverified", "matches_rc": true}
  ],
  "nexus_findings": ["<one line per hard finding or warning>"],
  "paste_recipe": "<multi-line shell commands>"
}
```

`staging_repos` lists every staging repository surfaced for the
project — a single entry on the anonymous path, one per sibling on
the authenticated path, ordered by repository id ascending; never
silently pick one when there are several. `nexus_findings` carries only hard findings and warnings,
one line each naming the repository or artefact and what is wrong; an
empty list means nothing to report. A `SKIP` leaves it empty, except
a `SKIP` for a malformed staging repository id, which records the
rejected value as one line so the RM sees what to correct.

`status` is `FAIL` on any hard finding: repository not reachable at
the id given for this RC (`404` — stated factually as "not reachable
at the id given for this RC"); repository `open` (still mutable — not
a valid vote target; distinct from not-reachable, never conflated
with it); the snapshots repository targeted
(`content/repositories/snapshots/` is never a valid vote target,
whatever the version string claims); coordinates or version mismatch
against the RC's declared release version (the plain version carried
by the staged POMs — the `-rcN` suffix lives in the dist path and
tag, not in the Maven version); a `.jar` or `.pom` in the inventory
with no sibling `.asc`; a main jar whose `-sources.jar` /
`-javadoc.jar` companion (or its `.asc` / checksum companion) is
absent from the inventory — `packaging=pom` modules are exempt, and
other classifiers (`-tests`, `-shaded`, `-linux-x86_64`, …) are
neither expected nor flagged. `WARN` when only `STATE-UNVERIFIED` or
stale-sibling findings remain. `PASS` otherwise. `SKIP` per the gates
above.
