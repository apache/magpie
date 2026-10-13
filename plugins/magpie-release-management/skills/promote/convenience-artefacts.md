<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Convenience artefacts (optional, project-specific)

Only when `convenience_artefacts` is non-empty.
The source promotion is the release; this section publishes what the project ships *besides* the source, to wherever the project declared.
The render emits it **after** the dist promotion and the final tag, as its own section, one entry per artefact:

- `publish_channel: dist-release` — nothing to emit: the artefact moved with the source in the promotion above; it says so.
- any other channel — the entry's `publish_command` verbatim, with `<version>` substituted
  (for example `twine upload dist/apache_<project>-<version>*`, `mvn nexus-staging:release -DstagingRepositoryId=<id>`, `docker push <registry>/<image>:<version>`, `helm push …`).
  These are the project's own commands; the skill never invents a channel or a command the config does not declare.
  An entry with no `publish_command` emits nothing and comes back in `warnings`.

**Reproducibility gate — the artefact must be good before it is published.**
A convenience artefact is publishable only if the `release-verify-rc` run recorded on the planning issue rebuilt it from the voted tag and it reproduced:
`identical`, or `WARN` with every difference matched by its `known_divergences`.
Step 1's `metadata.convenience` applies the rule from the `--verify-binary` results you passed
(read them from the verify-rc Step 9 comment: `binaries.identical`, documented `WARN`, `binaries.differs`).
Each `held` entry (`differs`, or `not checked` when no verify-rc run covered it) gets a **HOLD** note in place of its publish command,
and appears in `convenience_held`; no publish command for it appears anywhere.

The source promotion is not held back by a convenience artefact;
the source is the release, the artefact is a courtesy, and a courtesy that cannot be verified is withheld, not shipped.
