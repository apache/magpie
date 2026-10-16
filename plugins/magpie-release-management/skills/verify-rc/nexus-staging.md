<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 6c — Nexus staging repository (ASF projects publishing Maven artefacts)

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
classification rules are its
[`staging-verification.md`](../../../../tools/asf-nexus/staging-verification.md),
implemented in `release-management verify-rc nexus`.

**Golden rule:** this step performs read-only `GET`s against
`repository.apache.org`, nothing else. It never closes, drops, or
promotes a staging repository — a promotion is irreversible (promoted
artefacts sync to Maven Central, where they are immutable), and any
voter, including one with no karma on the target repository, must be
able to run this step.

**Credentials and the sandbox.** The authenticated staging-API reads
need ASF Nexus credentials stored as a netrc-format file at
`~/.config/apache-magpie/asf-nexus/netrc` (`machine
repository.apache.org login <user> password <pass>`, `chmod 600` —
never a `-u user:pass` on the command line, which exposes the
password in `ps` and transcripts). `~/.config/` is denied to the
sandboxed agent by design, so those recipes are for the RM to
paste into their **own** terminal; the agent's own run takes the
anonymous path and reports `STATE-UNVERIFIED` for the state question.
That is the expected voter shape, not a verification failure — and a
sandbox network refusal (the probe blocked before it left the
machine) is likewise reported as `STATE-UNVERIFIED` / not-probed,
never as "repository not reachable": one says "the runner could not
see", the other says "nothing is there".

**Run.** The gates, the recipe and the classification are one command
(`<verify-rc>` as in SKILL.md; `<inventory.json>` is Step 1's saved JSON):

```bash
<verify-rc> nexus --inventory <inventory.json> [--issue-body <planning-issue-body>] [--rm-credentials]
```

Pass `--issue-body` only when `--post-to` was passed, and `--rm-credentials` only when the RM runs the authenticated recipes in their own terminal.
The command checks the gates in order and prints an explicit `SKIP` naming the reason when one fails:
no `.jar` / `.pom` in the Step 1 listing (JVM-only — a Python or Rust ASF project must not be warned about a staging repository);
`jvm_artefact_checks: off`; 🪶 an `organization` other than `ASF` (`repository.apache.org` is ASF infrastructure);
no staging repository id (the `nexus_staging_repo` key of `release-build.md § JVM artefact checks`, then a `nexus-staging-repo:` or staging-repository URL line on the planning issue —
Nexus assigns the id at deploy time, so an unresolvable id is a `SKIP` naming where to supply it, never a guess);
or an id that does not match the Nexus shape `orgapache<project>-NNNN` (digits and lowercase only).
That last gate protects the URLs: the planning issue body is content the step reads, and the id is spliced into the `curl` URLs you run,
so a malformed value is a `SKIP` recording the rejected value in `nexus_findings`, never a probe; the literal `snapshots` passes and is then a finding.

Otherwise `paste_recipe` holds the probe with the id resolved: the anonymous existence check and the artefact-inventory crawl for every runner,
plus the authenticated state check and the profile-wide listing with `--rm-credentials`.
Run it, save each output, and re-run the command with them to classify:
`--existence-code <http-code>`, `--crawl <file>`, and with `--rm-credentials` also `--state <file>` and `--profile <file>`;
pass `--not-probed` instead when the sandbox refused the probe.

The command's JSON is this step's: `FAIL` on any hard finding —
not reachable at the id given for this RC (`404`), `open` (still mutable; never conflated with not-reachable),
the snapshots repository targeted, coordinates or version other than the RC's plain release version (the `-rcN` suffix lives in the dist path and tag),
no `.jar` / `.pom` for the RC's version at all (an inventory of only `maven-metadata.xml` names no coordinates and never matches),
a `.jar` / `.pom` with no sibling `.asc`, or a main jar's incomplete companion set (`packaging=pom` modules exempt; other classifiers neither expected nor flagged);
`WARN` when only `STATE-UNVERIFIED` or stale-sibling findings remain; `PASS` otherwise.
`staging_repos` lists every staging repository surfaced, ordered by id — never silently pick one when there are several;
`matches_rc` is `null` when the inventory could not be read (not probed, or an existence code other than `200` / `404`).

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
