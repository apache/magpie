<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Live Token-Cost & Context Meter Band](#live-token-cost--context-meter-band)
  - [Overview](#overview)
  - [Mod behavior](#mod-behavior)
  - [Configuration](#configuration)
    - [Environment variable](#environment-variable)
    - [Configuration files & resolution order](#configuration-files--resolution-order)
  - [Vendor neutrality & fallback](#vendor-neutrality--fallback)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Live Token-Cost & Context Meter Band

During extended agent sessions — such as authoring skills (`write-skill`), optimizing prompts (`optimize-skill`), running evaluations (`eval`), or triaging backlogs — agents accumulate substantial conversational history.
Without visibility into token accumulation, context saturation can trigger automatic compaction without warning, degrading model context fidelity and discarding intermediate reasoning.
The Live Token-Cost & Context Meter Band is an additive Claude Code mod in `magpie-utilities` that renders a real-time, zero-token status band above the terminal prompt.

## Overview

The meter band queries `$.session.usage()` in-process on every prompt cycle (`ui.render` on `AbovePrompt`).
It renders token usage, context saturation percentage, and session cost:

```text
[Context Meter] 38.4k / 200k tokens (19.2% context used) · $0.14 session cost
```

When context reaches higher saturation tiers, the band shifts color to give the maintainer proactive warning before compaction kicks in:

- **Info (green/default):** Normal saturation (<70%).
- **Warning (yellow):** Moderate saturation (70% to 84.9%).
- **Critical (red):** Heavy saturation (≥85%), alerting that compaction is imminent.

## Mod behavior

1. **Zero-Token:** Evaluated purely in TypeScript middleware inside the host agent; consumes zero model tokens.
2. **Fail-Open & Yielding:** If `$.session.usage()` is unavailable or throws, if total tokens is zero, or if a user survey currently holds the band (`e.props?.hasSurvey`), the hook passes through to `next(e)` immediately.
3. **Adaptive Display:** If context window max or session cost is not supplied by the engine, the meter displays available figures cleanly without `NaN` or broken formatting:

```text
[Context Meter] 38.4k tokens · $0.14 session cost
```

## Configuration

The meter band is enabled by default in interactive Claude Code sessions.
Adopters can tune or disable it via environment variable or configuration file.

### Environment variable

Set `MAGPIE_TOKEN_METER` to disable the band immediately:

```bash
export MAGPIE_TOKEN_METER=0   # or false, disabled
```

### Configuration files & resolution order

Per `AGENTS.md` § Configuration resolution order, settings resolve **personal layer first**, falling back to the project layer, and finally framework defaults:

1. **Personal layer (adopted):** `<workspace>/.apache-magpie-local/token-meter.toml`
2. **Personal layer (unadopted):** `<workspace>/.git/apache-magpie/token-meter.toml`
3. **Project layer (committed):** `<workspace>/.apache-magpie-overrides/token-meter.toml`

Example configuration (`token-meter.toml`):

```toml
# Apache Magpie Token Meter Configuration
[token_meter]
enabled = true

# Display mode: "always" (default) or "threshold-only"
# In "threshold-only" mode, the band is hidden until context saturation reaches warn_percent.
mode = "always"

# Percentage thresholds for color shifts
warn_percent = 70
critical_percent = 85
```

The configuration is cached in memory with a 10-second TTL keyed by the resolved file path to avoid filesystem overhead on hot render cycles.

## Vendor neutrality & fallback

Per [`docs/when-to-use-mods.md`](../when-to-use-mods.md), this mod is strictly additive.
In environments without Claude Code hooks — such as Google Antigravity, OpenAI Codex, Cursor, or headless CI runners — all Magpie skills continue to operate with 100% functionality.
