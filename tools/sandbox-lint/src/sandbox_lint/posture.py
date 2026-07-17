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

"""Harness-neutral security-posture check for sandbox-lint.

For agentic runtimes that do not have a dedicated sandbox configuration file
(Cursor, Gemini CLI, and others), the security posture comes from
OS-level enforcement components shared across all harnesses. This module
validates that those components are present in the framework tree so the
security posture holds regardless of which harness drives the session.

The check is statically conservative: it verifies artifact presence, not live
runtime behaviour. For runtime diagnostics — SSH-agent reachability, localhost
port binding, docker/podman socket — use ``setup-isolated-setup-doctor``.

Layer numbers below follow the RFC-AI-0002 four-layer model (Layer 0 clean-env,
Layer 1 filesystem sandbox, Layer 2 tool permissions, Layer 3 forced
confirmation). The two harness-neutral components this check validates cover the
two layers that do not require a per-harness ``settings.json``:

* **Layer 0 — clean-env wrapper** (``agent-iso <cli>`` / ``agent-iso.sh``):
  strips credential-shaped environment variables before exec. Provided by
  ``tools/agent-isolation/``. Harness-agnostic since
  ``harness-posture-portability``.
* **Layer 3 — forced confirmation / action guard** (``agent-guard --exec
  <cmd>``): the harness-neutral equivalent of Claude Code's ``permissions.ask``
  (RFC-AI-0002 Layer 3). It inspects every shell command before execution and
  denies ones that break a hard framework rule (unauthorised ``git push``, wrong
  commit-trailer format, …). The ``--exec`` path lets any harness or shell
  wrapper enforce guard rules without a harness-specific hook adapter. Provided
  by ``tools/agent-guard/``. Harness-neutral since ``harness-guard-exec-mode``.

Layers 1 (filesystem sandbox) and 2 (tool permissions) remain harness- or
OS-specific and are out of scope for this presence check.

Runtimes that expose a pre-tool hook API (Claude Code, OpenCode) can also wire
Layer 3 as an in-process hook; for other runtimes the ``--exec`` wrapper path
is the enforcement mechanism. Both paths call the same ``dispatch()`` core.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PostureViolation:
    """A single harness-neutral posture violation."""

    layer: str  # "layer-0" or "layer-3"
    detail: str  # human-readable description of what is missing and how to fix it


def check_posture_violations(framework_root: Path) -> list[PostureViolation]:
    """Return posture violations; empty list means the harness-neutral posture is in place.

    ``framework_root`` is the directory that contains ``tools/agent-isolation/``
    and ``tools/agent-guard/``. In a self-adoption setup this is the Magpie repo
    root; in an adopter repo it is ``.apache-magpie/`` (the installed snapshot).
    """
    violations: list[PostureViolation] = []

    # --- Layer 0: clean-env wrapper -------------------------------------------
    # The harness-agnostic ``agent-iso <cli>`` entry point added by
    # ``harness-posture-portability`` is the canonical generic path. The artifact
    # to probe is the underlying script, which is the same for every harness.
    agent_iso = framework_root / "tools" / "agent-isolation" / "agent-iso.sh"
    if not agent_iso.is_file():
        violations.append(
            PostureViolation(
                layer="layer-0",
                detail=(
                    f"clean-env wrapper not found at {agent_iso}. "
                    "Without it credential-shaped environment variables "
                    "(ANTHROPIC_API_KEY, GH_TOKEN, AWS_*, …) leak into the agent "
                    "session even when an OS-level sandbox is in place. "
                    "Install the framework snapshot or point --any-harness at "
                    "the correct framework root. "
                    "See tools/agent-isolation/README.md"
                ),
            )
        )

    # --- Layer 3: action guard (harness-neutral --exec path) ------------------
    # The dispatch core is stdlib-only and is invoked directly as
    #   python3 …/agent_guard/__init__.py --exec <cmd>
    # for any harness that can wrap shell commands through an executable.
    # The --exec path was added by harness-guard-exec-mode.
    agent_guard = framework_root / "tools" / "agent-guard" / "src" / "agent_guard" / "__init__.py"
    if not agent_guard.is_file():
        violations.append(
            PostureViolation(
                layer="layer-3",
                detail=(
                    f"action guard dispatch core not found at {agent_guard}. "
                    "Without it, dangerous shell commands (git push, gh pr create, …) "
                    "run ungated. Wire the guard via an in-process hook (Claude Code, "
                    "OpenCode) or the harness-neutral --exec wrapper path "
                    "(any other runtime). "
                    "See tools/agent-guard/README.md § Harness-neutral path"
                ),
            )
        )

    return violations


def find_framework_root(start: Path | None = None) -> Path:
    """Walk up the directory tree to locate the framework root.

    At each ancestor this checks two layouts, in order:

    1. **Self-adoption / framework tree** — the directory directly contains
       ``tools/agent-isolation/`` (the Magpie repo itself). Returns that
       directory.
    2. **Adopter repo** — the directory contains ``.apache-magpie/`` with the
       installed snapshot (``.apache-magpie/tools/agent-isolation/``). Returns
       the ``.apache-magpie`` snapshot dir, which is the ``framework_root``
       :func:`check_posture_violations` expects. Without this, a bare
       ``--any-harness`` from an adopter repo root would miss the snapshot and
       falsely report both layers missing.

    Falls back to *start* (default: ``Path.cwd()``) so the violation messages
    are still useful even when the search fails.
    """
    root = start if start is not None else Path.cwd()
    for candidate in [root, *root.parents]:
        if (candidate / "tools" / "agent-isolation").is_dir():
            return candidate
        snapshot = candidate / ".apache-magpie"
        if (snapshot / "tools" / "agent-isolation").is_dir():
            return snapshot
    return root  # caller's checks will report the missing artifacts
