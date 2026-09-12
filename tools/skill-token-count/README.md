<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [skill-token-count](#skill-token-count)
  - [Prerequisites](#prerequisites)
  - [Usage](#usage)
  - [Measurement and provenance](#measurement-and-provenance)
  - [Hook](#hook)
  - [Scope](#scope)
  - [Runtime replay benchmark](#runtime-replay-benchmark)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0 -->

# skill-token-count

**Capability:** substrate:framework-dev + substrate:analytics

**Harness:** agnostic

Measures full local skill files with pinned `tiktoken` and checks the generated
table in [mode economics](../../docs/mode-economics.md).
Implements the deterministic measurement check discussed in
[issue 327](https://github.com/apache/magpie/issues/327).

## Prerequisites

- **Runtime:** Python 3.11+ via uv, with pinned `tiktoken`.
- **CLIs:** None beyond uv and Python for file counts. The optional runtime
  replay adapter requires Claude Code.
- **Credentials / auth:** None for file counts. The opt-in replay adapter
  uses the Claude Code authentication and provider network configuration.
- **Network:** Package installation uses the configured package index.
  Only the explicit preparation command downloads the checksum-verified
  vocabulary from `openaipublic.blob.core.windows.net`. Measurements require
  the prepared cache and do not bootstrap it automatically.

## Usage

From the repository root, prepare once in a terminal outside the isolated
agent before running checks. No sandbox allowlist change is needed:

```bash
uv run --project tools/skill-token-count skill-token-count --prepare-tokenizer
```

The default persistent cache is `~/.cache/apache-magpie/tiktoken/`, shared
between worktrees. `TIKTOKEN_CACHE_DIR` can select a pre-provisioned cache
(including one copied to an offline machine); an empty value is rejected.
The vocabulary SHA-256 is checked before measurement.

Then regenerate or check:

```bash
uv run --project tools/skill-token-count skill-token-count --write
uv run --project tools/skill-token-count skill-token-count --check
uv run --directory tools/skill-token-count pytest
```

`--check` is the default and never writes. Exit status is 0 when current,
1 for drift, and 2 for invalid input. `--write` replaces only the marked block;
missing, duplicated, or reversed markers are errors. No files are staged.
`--root PATH` supports a different checkout or an extracted source archive.

## Measurement and provenance

Each regular `skills/**/SKILL.md` is read as UTF-8, with LF-normalized line
endings, including frontmatter and comments. `encode_ordinary` counts literal
special-token spellings as text. Referenced documents, tool output, model
responses, and external `source.md` redirects are not included. Harness
symlinks outside `skills/` are not counted again. Symlinked skill files are errors.

Rows are sorted by repository-relative path. A per-file SHA-256 identifies
the normalized source; a full manifest SHA-256 covers every path, token count,
full source digest, tokenizer version, encoding, and measurement schema.
The manifest is canonical JSON (ASCII escaped, compact separators, insertion
order as defined in the generator). The displayed source digest is abbreviated;
the manifest includes all 64 characters.

The generated block records a UTC measurement date. Checks and unchanged
writes preserve it; regeneration after changed inputs stamps a new date.
The date is descriptive metadata, not part of the content fingerprint.
A HEAD stamp is deliberately omitted: it would become stale when the
generated table is committed.
This tool works without Git history, including shallow CI and source archives.
For the publication revision and date, inspect the committed document history:

```bash
git log -1 --format='%H %cI' -- docs/mode-economics.md
```

That is the document's commit date, not a claim about when tokenization ran.
No runtime percentiles or provider billing measurements are inferred.

## Hook

The prek hook checks after skill fixers and runs on skill, generator, lockfile,
or target-document changes. A dedicated path-filtered CI workflow prepares the
vocabulary and checks the table. The general CI all-files run excludes this
hook to avoid running token measurements on unrelated PRs. Workspace dependency
installation and ordinary lint/test gates retain their existing behavior.
It deliberately checks rather than mutates, so generated headings cannot
invalidate an earlier doctoc pass. Regenerate and rerun prek after drift.
Deleted files may be omitted from a local hook's input; the dedicated CI workflow
and an explicit `--check` detect deletions even when no surviving file triggered
the local hook.

## Scope

This implements file-count provenance and drift detection from
[issue 327](https://github.com/apache/magpie/issues/327), not the complete
measurement programme. A [dated replay sample](benchmarks/2026-09-11.md)
and a [patch-drafting sample](benchmarks/2026-09-11-drafting.md) provide
actual CLI-usage percentiles for five skills across four modes. File counts
alone cannot supply those metrics. Production workload
percentiles and cross-model comparisons still require broader observations;
a PR should state this scope rather than claiming universal mode costs.

## Runtime replay benchmark

The optional `skill_token_count.runtime` module measures actual model usage for
synthetic decision-to-draft/report replays. It loads each full skill entrypoint
and sibling Markdown references, then supplies captured project/configuration
and tool observations from `benchmarks/replay-v1.json`. Live tools and MCP
servers are disabled; there are no external writes. It stops at the approval
boundary. This is distinct from both per-step evals and live operational runs.

This adapter requires an authenticated Claude Code CLI. Model calls may incur
charges and run only with explicit `--run`; ordinary tests and CI never launch
the benchmark. Default: three scenarios per skill, two repetitions, four workers. Modes are
validated against skill frontmatter before any call; summaries group by skill
so two Mentoring skills do not silently become one distribution.

```bash
uv run --project tools/skill-token-count python -m skill_token_count.runtime \
  --run --records /tmp/magpie-runtime-records.json
uv run --project tools/skill-token-count python -m skill_token_count.runtime \
  --records /tmp/magpie-runtime-records.json
# Run the three distinct patch-drafting scenarios:
uv run --project tools/skill-token-count python -m skill_token_count.runtime \
  --run --corpus tools/skill-token-count/benchmarks/drafting-v1.json \
  --records /tmp/magpie-drafting-records.json
# Render a saved run without calling a model:
uv run --project tools/skill-token-count python -m skill_token_count.runtime \
  --records tools/skill-token-count/benchmarks/2026-09-11.json --format markdown
```

The collector accepts object or event-array CLI output and requires a single
terminal result with numeric usage. It preserves failures; missing usage is an
error, never zero. p50 and p90 use linear interpolation with inclusive endpoints
(Hyndman-Fan type 7); only successful CLI results enter these distributions.
A successful CLI result is not a quality grade. Inspect the recorded responses
before describing them as completed tasks.

Totals sum `modelUsage` across models: input + cache creation + cache reads +
output. Thinking tokens are already included in output and are not added again.
Top-level `usage` is retained separately because it can omit auxiliary CLI calls.
Cache reads count toward token traffic, not as full-price uncached input.
Any CLI-reported cost is informational list-price telemetry, not a billing record.

Run metadata includes CLI/model versions, source commit and per-file hashes,
corpus and prompt hashes, repetitions, timestamps, durations, usage and final
responses. A fresh working directory prevents repository auto-discovery, but
user/admin CLI settings and provider caching may still affect overhead.
Cross-machine or cross-model equivalence is not assumed. Only synthetic inputs
belong in the published corpus; do not import private project traces here.

The first sample's `drafting-*` identifiers are legacy IDs for
`good-first-issue-author`, a Mentoring skill. Its labels and corpus hash were
corrected; the original hash is retained in `metadata_correction`. Prompts,
responses, usage, and timestamps were not changed. The Drafting sample uses
`issue-fix-workflow` and measures patch generation, not patch application or
red/green test execution. CLI completion is not evidence that tests passed,
even when a generated PR draft says they did.
