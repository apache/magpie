# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""Which harness is running, and which plugin versions it has installed.

Both the pre-flight (`cli`) and `upgrade gather` read the installed plugin
map; it lives here so neither has to import the other.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

#: How to notice which harness is running, and that harness's own
#: plugin-listing command (`install.md` Step M2/M5).  The markers mirror
#: the canonical self-detection order in `tools/adversarial-review`: a
#: harness started from inside another inherits the outer one's variables,
#: so the innermost candidates are checked first and Claude Code's widely
#: inherited `CLAUDECODE` comes last.  Only the running harness's listing
#: runs — a machine may have several installed, and whichever comes first
#: in a fixed probe order is not the one whose versions this session runs.
#: Copilot installs from a repo URL or catalogue and has no listing CLI,
#: so its entry has none: the floor stays unknown there rather than
#: guessing what a listing would print.  Pi's `pi list` prints package
#: sources without versions and has no JSON form, so Pi is unknown too.
#: Goose has no plugin listing either, and its marker (`AGENT_SESSION_ID`)
#: has a generic name, so it is checked after every harness-specific one.
HARNESS_LISTINGS: tuple[tuple[str, tuple[tuple[str, str | None], ...], list[str] | None], ...] = (
    ("codex", (("CODEX_SANDBOX", None), ("CODEX_THREAD_ID", None)), ["codex", "plugin", "list", "--json"]),
    ("copilot", (("COPILOT_CLI", None),), None),
    ("antigravity", (("ANTIGRAVITY_CONVERSATION_ID", None),), ["agy", "plugin", "list", "--json"]),
    ("pi", (("PI_SESSION_ID", None),), None),
    ("goose", (("AGENT_SESSION_ID", None),), None),
    ("claude", (("CLAUDECODE", "1"),), ["claude", "plugin", "list", "--json"]),
)


def _running_harness(env: Mapping[str, str]) -> tuple[str | None, list[str] | None]:
    """The harness these environment variables are running, and its listing."""
    for harness, markers, argv in HARNESS_LISTINGS:
        for var, want in markers:
            value = env.get(var)
            if value and (want is None or value == want):
                return harness, argv
    return None, None


def _parse_listing(text: str, harness: str | None = None) -> dict[str, str] | None:
    """One harness listing, parsed into the shared `{name: version}` map.

    Shared by every harness's listing command: `None` for unknown (the
    output did not parse, or an empty parsed listing leaves the sandbox
    read-denial ambiguity standing), never an empty map.
    """
    try:
        listing = json.loads(text)
    except json.JSONDecodeError:
        return None
    # Codex 0.149.1 separates installed plugins from available catalogue
    # entries. Only the former describe what this session can run.
    if harness == "codex" and isinstance(listing, dict):
        listing = listing.get("installed")
    if not isinstance(listing, list):
        return None
    out: dict[str, str] = {}
    for item in listing:
        if not isinstance(item, dict):
            return None
        version = item.get("version")
        # Antigravity 1.3.6 lists plugins without a manifest version (e.g.
        # Google's own) with no `version` key; they cannot be Magpie's.
        if harness == "antigravity" and "version" not in item:
            continue
        if not isinstance(item.get("name"), str) or not isinstance(version, str):
            return None
        out[item["name"]] = version
    # A listing that parses but is empty leaves the sandbox read-denial
    # ambiguity standing, so we report unknown rather than an empty map.
    return out or None


def read_installed(
    explicit: str | None, env: Mapping[str, str] | None = None
) -> tuple[str | None, dict[str, str] | None]:
    """The running harness and its installed plugin map, or `None` for
    *unknown* — never `{}` for it.  The pair is a coherent answer: both
    are `None` unless the running harness's own listing was read and
    parsed.

    `--plugin-list` lets the caller supply what it already read; the
    harness is still detected from the environment, so its own parsing
    and floor rules apply, and stays `None` only when no harness with a
    listing command is running — the map then stands alone.  Otherwise the
    running harness is detected from its own environment markers and only
    its listing command runs — no other harness's listing may answer for
    it.  Every failure mode collapses to `(None, None)`: the harness
    undetectable, a listing CLI the running harness does not have
    (Copilot), the command missing, a non-zero exit, a timeout or a
    refusal from the sandbox, unparsable output, or a sandbox that denies
    the plugin cache. An empty listing also stays unknown because it
    cannot be distinguished from a denied cache read.
    """
    if explicit is not None:
        text = sys.stdin.read() if explicit == "-" else Path(explicit).read_text(encoding="utf-8")
        # A supplied listing is still the running harness's own: without
        # its id, an Antigravity `magpie` plugin reads as every floor plugin
        # missing and a Codex envelope as unparsable.
        harness, argv = _running_harness(os.environ if env is None else env)
        if argv is None:
            harness = None
        parsed = _parse_listing(text, harness)
        return (harness if parsed is not None else None), parsed
    harness, argv = _running_harness(os.environ if env is None else env)
    if argv is None:
        # No harness is running here, or the one running has no listing
        # CLI (Copilot installs from a repo URL): unknown, and no other
        # harness's listing may be probed instead.
        return None, None
    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        # The listing cannot be produced: the binary is missing from the
        # harness it belongs to, it times out, or the sandbox refuses to
        # execute it.  Unknown — never another harness's answer.
        return None, None
    if completed.returncode != 0:
        return None, None
    parsed = _parse_listing(completed.stdout, harness)
    if parsed is None:
        return None, None
    return harness, parsed
