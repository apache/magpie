<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2b — The Nexus side (JVM artefacts)

A JVM release is voted on in two places at once.
The `dist/` tree carries the voted source artefact, and the jars downstream consumers resolve live in a Nexus staging repository at `repository.apache.org` until they are promoted to Maven Central.
This file covers the repository's lifecycle next to the distribution promotion in Step 2.
It emits no command and runs nothing: the release manager performs every transition under their own ASF credentials, in their own terminal or in the Nexus UI.

## When this step applies

Only when the release publishes Maven artefacts.
The signals are the ones Step 6c of [`release-verify-rc`](../verify-rc/nexus-staging.md) uses: a `nexus_staging_repo` in `release-build.md § JVM artefact checks`, or a `nexus-staging-repo:` line or staging-repository URL on the planning issue.
A source-only release has no staging repository and this step does not apply.
Never invent a repository id; Nexus assigns it at deploy time.

## Close, before the vote opens

A repository created by `mvn deploy` starts `open`, which means its contents can still change while people are voting on them.
The release manager closes it before sending the `[VOTE]`, which makes Nexus run its own rules (signatures, POM metadata, the sources and javadoc companions) and freezes the contents.
`release-verify-rc` Step 6c expects `closed`; an `open` repository is a hard finding there, because a vote cannot bind artefacts that may still move.

Close it with the Nexus UI's **Close** action, or with the close goal of the project's own staging plugin, when its build configures `nexus-staging-maven-plugin`.
The build's own configuration decides whether that goal exists; this skill does not emit the command.
Record the outcome on the planning issue so voters and the verifier see the same state.

## Promote, after the vote passes

Promotion is the irreversible step: the artefacts become immutable on Maven Central and cannot be replaced or withdrawn.
Run it only after the planning issue carries `vote-passed`, and treat it as part of the same release event as the distribution promotion in Step 2, never before it.
The repository id is the one Step 6c verified as `closed` and matching this RC.

When the project declares the promotion as a convenience artefact's `publish_command` (for example `mvn nexus-staging:release -DstagingRepositoryId=<id>`), Step 2's block already emits it verbatim; use that line.
Otherwise promote through the Nexus UI's **Release** action, or the release goal of the project's own staging plugin, when its build configures `nexus-staging-maven-plugin`; confirm the goal and its flags in the project's build documentation before running it.
The authoritative background is [ASF Infra's publishing guide](https://infra.apache.org/publishing-maven-artifacts.html): deploy, close, vote, promote, then Central picks the artefacts up.

Do not flip the `promoted` label until both halves are done: the distribution promotion in Step 2 and the Nexus promotion here.

## Drop, when the vote fails or the RC is withdrawn

A repository whose vote failed, or that the RM withdraws, is dropped rather than promoted.
Dropping publishes nothing: it discards the staging repository, and its artefacts never reach Central.
Drop it with the Nexus UI's **Drop** action, or the drop goal of the project's own staging plugin, when its build configures `nexus-staging-maven-plugin`.
The next release candidate gets a new repository and a new id, so a dropped id is never reused.

Two cautions.
Do not drop a repository while a re-vote on the same RC is still possible: a dropped repository cannot be re-opened, so the RC would have to be rebuilt and redeployed.
And do not treat the drop as part of the failed vote itself: record the failure with `release-vote-tally` first, then drop once the RM has decided the RC will not be re-voted.

## What this skill never does

It never closes, drops or promotes a repository, and never emits a transition command it cannot source from the project's configuration, for the same reasons Golden rules 1 and 2 keep the distribution promotion in the RM's hands:

- A promotion is irreversible, and every voter may be a non-committer.
- The read-only [`tools/asf-nexus`](../../../../tools/asf-nexus/README.md) adapter verifies state and never transitions it.
- The `~/.config/apache-magpie/asf-nexus/netrc` credentials the authenticated reads need are denied to the sandboxed agent by design, so the RM runs them in their own terminal.

When the RM asks the skill to close, drop or promote a repository, say what the action does, confirm it is the right one for the vote's outcome, and give them the matching UI action or the command the project's build already declares.
Then wait for them to report the result; do not run it on their behalf.
