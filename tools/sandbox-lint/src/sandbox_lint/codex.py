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

"""Security invariants for Apache Magpie's project-scoped Codex profile."""

from __future__ import annotations

from typing import Any


def _rule_blocks(rules_text: str) -> list[str]:
    # Drop full-line comments first: a commented-out rule must not satisfy
    # an invariant. Then split on declaration starts instead of matching
    # the closing paren: a ')' inside a justification string must not
    # truncate a block.
    code = "\n".join(line for line in rules_text.splitlines() if not line.lstrip().startswith("#"))
    return code.split("prefix_rule(")[1:]


def check_codex_invariants(config: dict[str, Any], rules_text: str) -> list[str]:
    """Return invariant violations; empty means the Codex profile is safe."""
    errors: list[str] = []

    if config.get("sandbox_mode") != "workspace-write":
        errors.append('config.toml: sandbox_mode must be "workspace-write"')
    if config.get("approval_policy") != "on-request":
        errors.append('config.toml: approval_policy must be "on-request"')

    workspace = config.get("sandbox_workspace_write")
    if not isinstance(workspace, dict) or workspace.get("network_access") is not False:
        errors.append(
            "config.toml: sandbox_workspace_write.network_access must be false "
            "so network bridges cross the native approval boundary"
        )

    blocks = _rule_blocks(rules_text)
    if not blocks:
        errors.append("rules/magpie.rules: no prefix_rule declarations found")
        return errors

    prompt_blocks = [block for block in blocks if 'decision = "prompt"' in block]
    allow_blocks = [block for block in blocks if 'decision = "allow"' in block]
    forbidden_blocks = [block for block in blocks if 'decision = "forbidden"' in block]

    if not any('"gh"' in block and '"pr"' in block for block in prompt_blocks):
        errors.append("rules/magpie.rules: GitHub pull-request mutations must prompt")
    if not any('"gh"' in block and '"issue"' in block for block in prompt_blocks):
        errors.append("rules/magpie.rules: GitHub issue mutations must prompt")
    if not any('"git"' in block and '"push"' in block for block in prompt_blocks):
        errors.append("rules/magpie.rules: git push must prompt")
    if not any('"gh"' in block and '"auth"' in block and '"token"' in block for block in forbidden_blocks):
        errors.append("rules/magpie.rules: gh auth token must be forbidden")
    if not any('"gh"' in block and '"pr"' in block for block in allow_blocks):
        errors.append("rules/magpie.rules: declare a scoped read-only GitHub allow rule")
    if any('"gh"' in block and '"release"' in block and '"download"' in block for block in allow_blocks):
        errors.append(
            "rules/magpie.rules: gh release download must not be allowed without "
            "confirmation because it writes local files"
        )

    return errors
