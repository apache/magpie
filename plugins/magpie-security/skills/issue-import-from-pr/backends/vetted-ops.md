<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-pr — the rollup write without the secure setup

From Step 7e.

These run through vetted-ops' `vetted-op-tracker` entry point,
which the secure setup lets out of the sandbox (every write still asks).
Without the secure setup, the same operations are
`uv run --directory <framework>/tools/github-rollup github-rollup --repo <tracker> append|amend-latest|fold …`
and `uv run --directory <framework>/tools/github-body-field body-field --repo <tracker> get|set …`;
see [`tools/vetted-ops/README.md`](../../../../../tools/vetted-ops/README.md#tracker-procedures-rollup-and-body-field-writes).
