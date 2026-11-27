<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Release-management lifecycle (end-to-end)
status: experimental
kind: feature
mode: Drafting
source: >
  MISSION.md § Initial Goals ("cut a first Apache release through the
  standard process within 3 months of resolution adoption"). README.md
  § Skill families (release-management, proposed). Designed spec-first in
  docs/release-management/ (README.md, process.md, spec.md) plus the
  adopter scaffold plugins/magpie-setup/templates/release-management-config.md
  (reached as projects/_template/, #1410).
  All ten skills have since shipped (release-prepare, release-keys-sync,
  release-rc-cut, release-vote-draft, release-archive-sweep,
  release-audit-report, release-announce-draft, release-verify-rc,
  release-vote-tally, release-promote).
acceptance:
  - The family's design (14-step process, per-skill state-change
    boundaries, adopter contract) is reviewable independently of any
    runtime skill; it already is, in docs/release-management/.
  - Each release-* skill, when it lands, ships flagged `experimental` and
    carries `mode: Drafting` or `mode: Triage` per the skill table.
  - The agent never holds, invokes, or proxies the Release Manager's
    signing key, and never publishes the release; steps 3, 4, 10, 11 emit
    paste-ready recipes the human executes as themselves.
---

# Release-management lifecycle

## What it does

End-to-end automation for an ASF project's release lifecycle, from the
planning issue and version bump through to `[ANNOUNCE]` on
`announce@apache.org`, the archive sweep, and the per-release audit log.
Ten skills compose into the canonical 14-step process. The procedural
shape is foundation-wide; project-specific content (release-train
identity, build invocation, `KEYS` path, vote-window length, retention
rule, audit-log location) plugs in through `<project-config>/`, exactly
as the security family does. Non-ASF adopters are first-class: the
distribution backend, approval mechanism, and announcement backend each
parametrise the lifecycle without baking in an ASF assumption.

This is the load-bearing parallel to the security-issue lifecycle: a
multi-skill, high-procedure ASF-process family with shared
state-change-boundary discipline, designed docs-first before any skill
code lands.

## Where it lives

- Design docs (present today): `docs/release-management/README.md`
  (family overview + skill table), `docs/release-management/process.md`
  (14-step lifecycle, Mermaid flow, label reference),
  `docs/release-management/spec.md` (per-skill scope and state-change
  boundary), plus the operator runbooks
  `docs/release-management/atr-release-runbook.md`,
  `docs/release-management/svn-release-runbook.md`,
  `docs/release-management/manual-release-process.md`, and
  `docs/release-management/reproducibility.md`.
- Adopter contract: `release-management-config.md`, `release-build.md`,
  `pmc-roster.md`, `site-repo.md`, the shared `release-trains.md`, and
  `workflows/release-candidate.yml`, all under
  `plugins/magpie-setup/templates/` since #1410 so a marketplace install of
  `magpie-setup` ships them; `projects/_template` is a symlink to that
  directory, so the old paths still resolve.
  The filled-example values in the template use the neutral `Apache Foo`
  project rather than a real adopter (#1407).
- Magpie's own release configuration: `projects/magpie/` holds the filled
  `release-management-config.md` (ATR for both distribution and vote),
  `release-build.md`, `release-trains.md`, and `pmc-roster.md`; #1412 also
  committed `release-management-config.md`, `release-build.md`,
  `release-trains.md`, and `pmc-roster.md` under
  `.apache-magpie-overrides/` for the framework checkout's self-adoption.
- Skills (all ten shipped, all `experimental`, under
  `plugins/magpie-release-management/skills/<alias>/` with
  `skills/release-<alias>` symlinks): `release-prepare`
  (`mode: Drafting`) drafts the planning issue (Step 1), the prep PR with
  version bump / changelog / NOTICE / LICENSE (Step 2), and the
  post-release development-version bump PR (Step 14), never marking ready,
  merging, or closing; `release-keys-sync` (`mode: Drafting`) drafts the
  KEYS-file diff and paste-ready `svn` command sequence to add the RM's
  public key and validates key strength against the ASF floor, never
  holding or reading the private key (Step 3); `release-rc-cut`
  (`mode: Drafting`) emits the paste-ready tag / build / sign / checksum /
  staging command sequences for an RC, run locally by the RM with their
  own key (Steps 4–5), its only GitHub access being the vetted `tags`
  read and `repo-issue-comment` write (#1518); `release-announce-draft`
  (`mode: Drafting`) drafts
  the `[ANNOUNCE]` body and proposes the site-bump PR for a promoted
  release (Step 11), enforcing the one-hour promote-wait gate,
  `@apache.org` address reminder, Download Page link constraint, and
  no-send / no-auto-merge boundaries; `release-verify-rc` (`mode: Triage`)
  runs read-only RC pre-flight (signatures, checksums, RAT headers,
  NOTICE/LICENSE, prohibited binaries, published-JVM-artefact
  compliance via `tools/maven-artifact-verify` — POM licence set (a POM
  carrying a DTD or entity declaration is refused unparsed, #2105),
  podling disclaimer, companion jars, a WARN when a main jar carries no
  `META-INF/LICENSE` or `META-INF/NOTICE` (#2112), plus informational
  reproducibility / namespace / companion-content observations —
  plus the Nexus staging repository behind them via the read-only
  `tools/asf-nexus` adapter (ASF-only); version consistency,
  Step 6).
  For a podling, Step 5 also fails an RC with neither `DISCLAIMER` nor
  `DISCLAIMER-WIP` at the source root (presence only, not wording).
  The stage comes from the optional, ASF-only `project_stage` key
  (`incubating` / `top-level`) in `release-management-config.md`, never
  from a file in the RC: `verify-rc args` adds `--podling` itself, and the
  JVM step uses the same signal, falling back to the disclaimer file only
  when the key is unset. Unset on an ASF project, `args` warns, and the
  skill asks the release manager once and records the answer (#2114);
  `release-vote-draft` (`mode: Drafting`) drafts the `[VOTE]` email body
  and planning-issue comment after a PASS pre-flight, naming the Nexus
  staging-repository URL when the RC carries JVM artefacts (read from the
  planning issue for this RC, else `release-build.md`, and refused unless it
  is a `<name>-NNNN` id or a URL carrying one, #2150), never sending or
  posting (Step 7); `release-vote-tally` (`mode: Triage`) classifies
  +1/0/-1 binding vs non-binding once the window closes and drafts the
  `[RESULT]` (Step 9); `release-promote` (`mode: Drafting`) emits the
  backend-shaped staging→release promotion command set for a vote-passed
  release (Step 10), with the release manager's close / promote / drop
  guidance for the Nexus staging repository (#2112), its Step 2b
  (`promote/nexus-staging.md`, JVM releases only, #2150) saying when the RM
  closes, promotes or drops it, emitting no transition command the project's
  build does not already declare, and holding the `promoted` label until both
  the distribution and the Nexus promotion are done; `release-archive-sweep` (`mode: Triage`) scans the
  dist area and proposes the command set to move past-retention releases
  to the archive, read-only on the dist surface (Step 12); and
  `release-audit-report` (`mode: Triage`) assembles the per-release audit
  record from the planning issue, vote thread, artefact list, and announce
  archive URL (titled with the `<product-name>` display name, passed to
  `audit-report gather --product-name`, #2096) and proposes the audit-log PR, read-only on every release
  surface (Step 13). All ten skills have now shipped.
- Deterministic helpers, so fixed rules run as code rather than being
  re-derived from prose each run:
  `tools/release-config` (#1510) loads the adopter's release configuration
  and runs every skill's deterministic Step 0 checks
  (`release-config preflight --skill <name>`, JSON `blockers` / `warnings` /
  `values`) and the Step 1 config metadata (`release-config load`), with
  shared rules (version / RC format, approver roster, ASF identity,
  automated-signing offer, archive destination) implemented once.
  `tools/release-management` renders rc-cut's tag, build, sign, checksum,
  staging and reproducibility blocks from that loaded configuration without
  executing them. Rebuild commands preserve shell comments and heredocs,
  and stop before running any build command if the checkout is unavailable.
  Top-level build commands resolve release placeholders; custom builds emit
  their reproducibility record. Per-entry modes describe the checks actually
  run, and a failed outcome cannot propose a staging label.
  It also classifies `release-verify-rc`'s results from saved files only
  (#1619): `verify-rc args` emits the `release-verify` invocations from
  `release-build.md`, and `rat`, `source-tree`, `jvm`, `nexus`, `repro` and
  `report` classify Steps 4, 7, 6b, 6c, 9 and 10, checking the Nexus
  staging-repository id shape (`<name>-NNNN`, which fits both
  `orgapache<project>-NNNN` and `maven-NNNN`, #2209) before any URL is
  built and withholding the
  trusted-hardware attestation unless automated signing, a Step 9 `PASS`
  and every artefact `identical` all hold.
  It renders the `[VOTE]` draft and planning-issue comment
  (`vote-draft verdict` / `render`, #1617), the backend-shaped promotion
  command set with a HOLD per unreproduced convenience artefact
  (`promote verdict` / `render`, #1618), and the `[ANNOUNCE]` body and
  site-bump PR (`announce-draft verdict` / `render`, #1618), each refusing
  (exit `2`) what the skill must refuse.
  A source version is a dotted version of two or more numeric parts with
  no `.postN` (`2.11.0`) or, for a release wave named by date, a calendar
  date `YYYY-MM-DD` (`2026-10-06`, tagged `2026-10-06-rc1`); an impossible
  date such as `2026-02-30` blocks (#1605).
  `prepare plan-query --tag-date` refuses an impossible date or time the
  same way, not only a malformed one (#2291).
  `tools/release-verify` (#1511) runs `release-verify-rc`'s mechanical steps
  offline (`inventory`, `signatures`, `checksums`, `notice-license`,
  `binaries`, `symlinks`, `version`, `verdict`), verifying signatures in a
  throwaway `GNUPGHOME` and refusing a `KEYS` file with private-key material.
  Its `checksums` step requires the first digest of the configured set:
  `sha512` by default, `sha256` for a project that declares a SHA-256-only
  set, as ASF policy accepts either; every other staged digest is checked,
  and `release-config preflight --skill rc-cut` accepts a set with `sha256`
  or `sha512` and no `md5` / `sha1` (#2212).
  `maven-artifact-verify` refuses a `--digests` value that names no digest
  type (exit `2`, `FAIL`), which would otherwise pass companions that carry
  no checksum at all (#2332).
  A `**/` in a prohibited-binaries glob matches zero or more directories,
  so `**/gradle-wrapper.jar` matches a jar at the root but not
  `fake-gradle-wrapper.jar` (#2257).
  Its `version` step reads a `--manifest` only inside `--tree`: one that
  resolves outside it (`..`, an absolute path elsewhere, or a symlink) is
  not read and `FAIL`s, so Step 8 cannot pass on a file the RC lacks (#2424).
  Per-skill sibling scripts (#1512) under `skills/<alias>/scripts/` with
  stdlib `unittest` suites have all moved into `tools/release-management`
  beside each skill's renders: the `vote-tally` tally (formerly `tally.py`)
  is `release-management vote-tally tally`; `prepare`'s former
  `prev_tag.py`, `category_x.py` and `next_dev_version.py` are
  `release-management prepare prev-tag`, `category-x` and
  `next-dev-version`, beside its Step 0 verdict, the planning-issue and PR
  renders, the changelog coverage check, the 2e archive review and the
  Step A eligibility gate and workflow render; `archive-sweep`
  `retention.py` is `release-management archive-sweep retention` (beside
  `verdict`, `listing`, `trains` and `render`); `audit-report`
  `render_record.py` is `release-management audit-report record` (beside
  `verdict`, `gather`, `voters`, `check` and `pr`); and `keys-sync`
  `check_key.py` is `release-management keys-sync check` (beside `verdict`
  and `render`), its gpg listing moved to `release-verify list-keys`, so
  release-management still runs nothing.
- Conditional steps load only when they run (#1515): `prepare` splits into
  `plan.md`, `prep.md`, `post.md` and `automated-signing.md`; `rc-cut` into
  `ci-signed.md` and `reproducibility-self-check.md`; `verify-rc` into
  `jvm-artefacts.md`, `nexus-staging.md` and `reproducibility.md`.
  Since #1604–#1625 every skill in the family also keeps its prerequisites
  and references in `prerequisites.md` / `references.md` and loads one file
  per outcome, backend or classification (`outcomes/`, `backends/`,
  `blockers/`, `classifications/`, `mechanisms/`, `delivery/`,
  `overrides/`) only when the deterministic verdict names it.
- Adapters it will read/draft through: `tools/github`, `tools/ponymail`
  (vote threads), `tools/gmail` (announce/vote drafts), plus the project's
  `svn` dist tree as a distribution backend.

## Behaviour & contract

- **The agent never holds the signing key.** Steps 3 (`KEYS`), 4 (RC tag,
  sign, checksums, `svn` import to `dist/dev/<project>/`), and 10
  (`svn mv dist/dev → dist/release`) emit paste-ready command recipes; the
  Release Manager runs every signing and `svn commit` operation as
  themselves. Mirrors `security-cve-allocate` (Vulnogram URL + paste-ready
  JSON, human submits).
- **Upload credentials stay with the Release Manager.** A `stage_command` or
  `publish_command` that needs the RM's token (e.g. `twine upload`) is declared
  wrapped in `tools/secret-prompt`, which asks the RM for it — in their
  terminal, or as a macOS / Linux dialog when an agent runs the step — and
  passes it only to that one command's environment, so it never reaches a
  file, the shell history, or the agent's transcript.
- **The agent never publishes the release.** Step 10 (promotion) and step
  11 (`[ANNOUNCE]` send + site-bump merge) are the moments of release; the
  agent drafts artefacts, the RM and PMC execute and merge.
- **Drafts, never sends.** `[VOTE]` (step 7) and `[ANNOUNCE]` (step 11)
  email bodies are drafted to the maintainer's outbox; no skill calls a
  send.
- **Conservative tally.** `release-vote-tally` classifies +1/0/-1 binding
  vs non-binding against the PMC roster and refuses to count ambiguous
  votes, flagging `AMBIGUOUS, needs RM call` rather than guessing.
  A roster voter resolved by Primary email with no Apache ID is keyed by
  the normalised address, so email-only voters stay distinct and cannot
  supersede one another (#1913).
  `tally.py` binds a vote only to the real mailbox of its `from` header,
  parsed as an address header: an address written into the display name
  does not count, and a `from` with several addresses or none that parses
  is non-binding and can never supersede another voter's vote (#1530).
  When a voter's later message carries an earlier date, the tally reports
  the mismatch by comparing the dates as instants, so the same moment in two
  time zones is not flagged; dates it cannot parse, or one zoned and one
  naive, fall back to a text comparison (#2241).
- **Public release text carries no embargoed security framing.** An
  `--expedited` reason reaches the public `[VOTE]` body and planning-issue
  comment, so until the advisory ships `release-vote-draft` writes it
  neutrally, with no CVE ID and no "security fix", keeps any approval the
  RM cited, and tells the RM what was left out (#1509).
- **Bodies go through a file.** PR and comment bodies are written to a
  scratch file and passed with `--body-file`, and PRs open with
  `gh pr create --web` for the RM to review (#1502).
- **Read-only verification.** `release-verify-rc` (signatures, checksums,
  RAT license headers, NOTICE/LICENSE, prohibited binaries, source-tree
  integrity, version consistency, and the optional reproducibility step)
  and `release-audit-report` make no state change; voters can run
  verification in their own dev loop before posting `+1`.
- **The verify-rc pane is additive.** Under Claude Code,
  `plugins/magpie-release-management/hooks/verify-rc-pane.ts` draws a live
  checklist of the skill's 13 steps, JVM artefacts and Nexus staging included (#2007).
  The Bash tool-call feed interceptor updates step statuses, details, and the overall
  verdict in real time as `release-config` and `release-verify` subcommands run (#2013).
  The same module (`verify-rc-pane.ts`, importing `vote-tally-band.ts`) draws a
  live vote-tally band above the prompt while a `vote-tally` command runs
  (#2216): binding and non-binding counts, the hours left in the 72-hour
  window, and a status of voting / passed / closed / failed, where approval
  needs at least three binding +1 and more binding +1 than -1, and a
  canonical `PASSED` / `FAILED` from the tally script wins.
  Voter handles and RC tags are sanitised (escape sequences, bidi and
  zero-width characters, markup delimiters stripped, length bounded) before
  display.
  Both are display only; the tally and the `[RESULT]` draft come from the
  skill.
- **The source artefact is a reproducible export of the tag.** With
  `release-build.md § Source archive` at its default
  (`source_archive_method: git-archive`), `release-rc-cut` emits
  `repro-archive build` (`tools/reproducible-archive`): `git archive` at the
  tag, honouring `.gitattributes` `export-ignore`, with every
  reproducible-builds.org archive rule applied (single `SOURCE_DATE_EPOCH`
  mtime, sorted members, uid/gid 0, `a=rX,u+w`, no PAX `atime`/`ctime`,
  `gzip -n`, `zip -X`), so the bytes are a function of the tag alone.
  Never an archive of a working tree.
  The zip comment is the commit id, as `git archive` writes it, and the
  check accepts 40 or 64 lowercase hex characters (SHA-1 or SHA-256 object
  names) and nothing else (#2347).
  `compare` matches the ordered list of members under each name, so an
  archive repeating a name whose count, content or order differs is
  `differs`, never content-identical (#2341).
- **First-release `.gitattributes` review is an education step.**
  `release-prepare prep` Step 2e classifies every top-level path, checks
  references before proposing an exclusion, confirms each entry with the
  RM, lands `.gitattributes` in the prep PR and records
  `export_ignore_reviewed`; `release-rc-cut` blocks while the review is
  outstanding (`--allow-unreviewed-archive` is the logged override).
- **Reproducibility checks are optional, and mandatory under automated
  signing.** `release-build.md § Reproducibility checks` enables the
  source rebuild-and-compare (`identical` / `content-identical` /
  `differs`) and the per-artefact convenience rebuild (`byte-identical` or
  `documented-divergence`) in `release-rc-cut` Step 2b and
  `release-verify-rc` Step 9.
- **Convenience artefacts are project-specific and config-declared.** The
  framework assumes none; `release-build.md § Convenience artefacts` lists
  each one with its own `build_command`, `staging` / `stage_command`,
  `reproducibility` mode, `vote_included` flag and `publish_channel` /
  `publish_command`. `release-rc-cut` builds and stages them under the
  tag's `SOURCE_DATE_EPOCH`, `release-verify-rc` rebuilds and compares
  them (the check that decides whether a binary is good, since it cannot
  be reviewed), `release-vote-draft` lists them, `release-promote`
  publishes only those that reproduced and emits a HOLD for the rest, and
  `release-announce-draft` names their channels. `release-verify-rc` Step 7
  runs the project's own `source_tree_validators`, none assumed.
- **🪶 ASF-specific automated release signing.** Offered only under
  `organization: ASF` (`release_process.automated_signing` in the ASF
  organization manifest; `null` elsewhere). `release-prepare
  automated-signing` drafts — never files or sends — the Infra key-request
  ticket, the Security Team notification and the workflow PR
  (`plugins/magpie-setup/templates/workflows/release-candidate.yml`, no key
  material).
  With `automated_release_signing: enabled`, `release-rc-cut` emits the
  RM-signed tag push instead of local sign/stage, `release-verify-rc` Step 9
  is mandatory at a byte-identical bar and carries the committer's
  `--trusted-hardware` attestation, and `release-promote` blocks without
  that attestation on the planning issue. The agent still holds no key.
- **Promotion gated on health evidence, not throughput.** Moving any
  release-* skill from `experimental` to default-on, or from Agentic Drafting to a
  state-changing lane, requires evidence from Release Managers and binding
  voters that the process is healthier (fewer stalled RCs, shorter
  time-to-`[ANNOUNCE]`, fewer reverted promotions).
- **Audit records are structured.** `release-audit-report` output should
  follow a schema/template with required fields for release version, RC
  artefacts, vote thread, tally outcome, promotion revision, announcement
  URL, archive state, and follow-up notes. Missing required fields are a
  report finding, not silently omitted prose.

## Out of scope

- Holding, invoking, or proxying the RM's private signing key.
- Publishing the release: the `svn mv` promotion, the `[ANNOUNCE]` send,
  and the site-bump merge are human acts.
- A new mode. Release-management is a family spanning the existing Agentic Triage
  and Agentic Drafting modes; it introduces no new mode.

## Acceptance criteria

1. The 14-step process, per-skill state-change boundaries, and adopter
   contract are reviewable from `docs/release-management/` without any
   skill code (they are today).
2. Each `release-*` skill, as it lands, validates under
   `skill-and-tool-validate`, ships `experimental`, and carries the
   `mode` its skill-table row assigns.
3. No skill in the family signs, imports, promotes, sends, or merges on
   autopilot; the key-holding and publishing steps emit paste-ready
   recipes only.
4. `release-audit-report` validates the audit record against the
   required-field schema and flags incomplete lifecycle evidence before
   proposing an audit-log PR.
5. `release-config preflight` accepts a source version or RC identifier
   that is either a dotted numeric version or a real calendar date
   `YYYY-MM-DD`, and blocks a malformed one or an impossible date (#1605;
   `tools/release-config/tests/test_preflight.py`).

## Validation

```bash
test -f docs/release-management/spec.md
test -f docs/release-management/process.md
test -f plugins/magpie-setup/templates/release-management-config.md
test -L projects/_template
test -f .agents/skills/magpie-release-prepare/SKILL.md
test -f .agents/skills/magpie-release-keys-sync/SKILL.md
test -f .agents/skills/magpie-release-rc-cut/SKILL.md
test -f .agents/skills/magpie-release-vote-draft/SKILL.md
test -f .agents/skills/magpie-release-archive-sweep/SKILL.md
test -f .agents/skills/magpie-release-audit-report/SKILL.md
test -f .agents/skills/magpie-release-announce-draft/SKILL.md
test -f .agents/skills/magpie-release-verify-rc/SKILL.md
test -f .agents/skills/magpie-release-vote-tally/SKILL.md
test -f .agents/skills/magpie-release-promote/SKILL.md
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/release-config python -m pytest
uv run --project tools/release-verify python -m pytest
tools/dev/run-skill-script-tests.sh
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/release-announce-draft/
```

## Known gaps

- **Only part of the podling checks is covered.** `release-verify-rc`
  checks that a disclaimer file is present, but not `incubating` in the
  archive names or the two-stage PPMC-then-IPMC vote;
  `organizations/ASF/skill-sources.md` still recommends the IPMC's
  `releasecheck` for podlings.
  <!-- gap-closes-when: none (narrative) -->
- **All ten skills have shipped** — `release-prepare`, `release-keys-sync`,
  `release-rc-cut`, `release-vote-draft`, `release-archive-sweep`,
  `release-audit-report`, `release-announce-draft`, `release-verify-rc`,
  `release-vote-tally`, `release-promote` — each `experimental` with an
  eval suite. The family is feature-complete; no skill remains `proposed`.
- **Health-evidence promotion criteria are unmeasured.** No adopter has
  cut a full release through the family yet, so the RM/binding-voter
  evidence window that would justify default-on or a state-changing lane
  has no data behind it.
- **Release audit record schema has shipped.** The canonical structured
  schema lives at
  `plugins/magpie-release-management/skills/audit-report/audit-record-schema.md`
  (reached as `skills/release-audit-report/audit-record-schema.md`).
  `tools/release-management/tests/test_audit_report.py` validates
  incomplete records, including the former `case-4-all-required-missing`
  eval case.
- **Magpie's committed override is the unfilled template.** Per-file
  `<project-config>` resolution reads
  `.apache-magpie-overrides/release-management-config.md` in this
  repository, and that file (added by #1412) is the template's
  `Apache Foo` example with `release_dist_backend = svnpubsub` and
  `release_vote_backend = manual`, whereas
  `projects/magpie/release-management-config.md` carries Magpie's real
  values (`project_dist_name: magpie`, ATR for both backends).
  `.apache-magpie-overrides/release-build.md` likewise differs from
  `projects/magpie/release-build.md`.
- **`release-verify-rc` is back over the 500-line cap.** The
  decide-and-render-as-code passes (#1604, #1617–#1619, #1624, #1625) brought
  every `SKILL.md` in the family under it (`release-prepare` fell from 1,208
  to 367), but later additions grew `verify-rc/SKILL.md` to 527 lines;
  `rc-cut/SKILL.md` (498) is next.
  <!-- gap-closes-when: none (narrative) -->
