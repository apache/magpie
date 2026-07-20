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

import re
from typing import Any, NamedTuple

# Pattern lists nest exactly one level: ["gh", "auth", ["token", "refresh"]].
_PATTERN_RE = re.compile(r"pattern\s*=\s*(\[(?:[^\[\]]|\[[^\]]*\])*\])")
_DECISION_RE = re.compile(r'decision\s*=\s*"(allow|prompt|forbidden)"')
_ELEMENT_RE = re.compile(r'\[[^\]]*\]|"[^"]*"')
_TOKEN_RE = re.compile(r'"([^"]*)"')


class _Rule(NamedTuple):
    elements: tuple[tuple[str, ...], ...]
    decision: str

    def has(self, *words: str) -> bool:
        tokens = {token for element in self.elements for token in element}
        return all(word in tokens for word in words)


def _parse_rules(rules_text: str) -> list[_Rule]:
    """Parse prefix_rule declarations into pattern elements plus decision.

    Comment lines are dropped first: a commented-out rule must not satisfy
    an invariant. Splitting happens on declaration starts instead of the
    closing paren: a ')' inside a justification string must not truncate a
    block. Invariants then match the extracted pattern tokens only, so a
    justification string that mentions "push" or "download" can neither
    satisfy nor trip a check.
    """
    code = "\n".join(line for line in rules_text.splitlines() if not line.lstrip().startswith("#"))
    rules: list[_Rule] = []
    for block in code.split("prefix_rule(")[1:]:
        pattern_match = _PATTERN_RE.search(block)
        decision_match = _DECISION_RE.search(block)
        if not pattern_match or not decision_match:
            continue
        inner = pattern_match.group(1)[1:-1]
        elements = tuple(tuple(_TOKEN_RE.findall(chunk.group(0))) for chunk in _ELEMENT_RE.finditer(inner))
        rules.append(_Rule(elements=elements, decision=decision_match.group(1)))
    return rules


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

    rules = _parse_rules(rules_text)
    if not rules:
        errors.append("rules/magpie.rules: no parseable prefix_rule declarations found")
        return errors

    prompt_rules = [rule for rule in rules if rule.decision == "prompt"]
    allow_rules = [rule for rule in rules if rule.decision == "allow"]
    forbidden_rules = [rule for rule in rules if rule.decision == "forbidden"]

    if not any(rule.has("gh", "pr") for rule in prompt_rules):
        errors.append("rules/magpie.rules: GitHub pull-request mutations must prompt")
    if not any(rule.has("gh", "issue") for rule in prompt_rules):
        errors.append("rules/magpie.rules: GitHub issue mutations must prompt")
    if not any(rule.has("git", "push") for rule in prompt_rules):
        errors.append("rules/magpie.rules: git push must prompt")
    if not any(rule.has("gh", "auth", "token") for rule in forbidden_rules):
        errors.append("rules/magpie.rules: gh auth token must be forbidden")
    if not any(rule.has("gh", "pr") for rule in allow_rules):
        errors.append("rules/magpie.rules: declare a scoped read-only GitHub allow rule")
    if any(rule.has("gh", "release", "download") for rule in allow_rules):
        errors.append(
            "rules/magpie.rules: gh release download must not be allowed without "
            "confirmation because it writes local files"
        )

    return errors
