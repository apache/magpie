#
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
"""
`adversarial-review.md`: the personal layer (`.apache-magpie-local/`) wins over
the project layer (`.apache-magpie-overrides/`), whole file, not key by key.

The file is Markdown carrying one fenced ```yaml block. The runtime is
stdlib-only, so this parses exactly the subset the documented shape uses — a
two-level mapping, inline lists, `#` comments — and rejects anything else with a
message naming the line, rather than guessing.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .backends import BACKENDS

MODES = ("on-pr-create", "on-demand", "off")
FILE_NAME = "adversarial-review.md"
LAYERS = (".apache-magpie-local", ".apache-magpie-overrides")
ROOT_KEYS = ("mode", "reviewers", "timeout_minutes", "models")

_FENCE = re.compile(r"^```ya?ml[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
_COMMENT = re.compile(r"(^|\s)#.*$")


class ConfigError(ValueError):
    """The configuration file is present but not valid."""


@dataclass(frozen=True)
class ReviewConfig:
    mode: str = "on-pr-create"
    reviewers: tuple[str, ...] = ()
    timeout_minutes: float = 10.0
    models: Mapping[str, str] = field(default_factory=dict)
    source: Path | None = None


def _unquote(value: str) -> str:
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'" else value


def _reviewers(value: str, where: str) -> tuple[str, ...]:
    if not (value.startswith("[") and value.endswith("]")):
        raise ConfigError(f"{where}: reviewers must be an inline list like [codex, copilot]")
    names = tuple(dict.fromkeys(_unquote(v.strip()) for v in value[1:-1].split(",") if v.strip()))
    unknown = [n for n in names if n not in BACKENDS]
    if unknown:
        raise ConfigError(f"{where}: unknown reviewer {', '.join(unknown)}; expected {', '.join(BACKENDS)}")
    return names


def parse(text: str, source: Path) -> ReviewConfig:
    block = next(
        (m.group(1) for m in _FENCE.finditer(text) if re.search(r"^adversarial_review:", m.group(1), re.M)),
        None,
    )
    if block is None:
        if _FENCE.search(text):
            raise ConfigError(f"{source}: the ```yaml block has no top-level `adversarial_review:` key")
        raise ConfigError(f"{source}: no ```yaml block with an `adversarial_review:` key")
    values: dict[str, str] = {}
    models: dict[str, str] = {}
    in_models = False
    for lineno, raw in enumerate(block.splitlines(), 1):
        line = _COMMENT.sub("", raw).rstrip()
        if not line.strip():
            continue
        where = f"{source}: line {lineno}"
        indent = len(line) - len(line.lstrip(" "))
        key, sep, value = line.strip().partition(":")
        key, value = key.strip(), value.strip()
        if not sep:
            raise ConfigError(f"{where}: expected `key: value`")
        if indent == 0:
            if key != "adversarial_review" or value:
                raise ConfigError(f"{where}: the only top-level key is `adversarial_review:`")
            continue
        if indent == 2:
            if key not in ROOT_KEYS:
                raise ConfigError(f"{where}: unknown key {key!r}; expected {', '.join(ROOT_KEYS)}")
            in_models = key == "models"
            if in_models and value:
                raise ConfigError(f"{where}: models must be a nested mapping")
            if not in_models:
                values[key] = value
            continue
        if indent == 4 and in_models:
            if key not in BACKENDS:
                raise ConfigError(f"{where}: unknown reviewer {key!r} under models")
            models[key] = _unquote(value)
            continue
        raise ConfigError(f"{where}: unexpected indentation ({indent} spaces)")
    mode = _unquote(values.get("mode", "on-pr-create"))
    if mode not in MODES:
        raise ConfigError(f"{source}: mode {mode!r} is not one of {', '.join(MODES)}")
    reviewers = _reviewers(values["reviewers"], str(source)) if "reviewers" in values else ()
    try:
        timeout = float(values.get("timeout_minutes", "10"))
    except ValueError:
        raise ConfigError(f"{source}: timeout_minutes must be a number") from None
    if timeout <= 0:
        raise ConfigError(f"{source}: timeout_minutes must be greater than 0")
    return ReviewConfig(mode, reviewers, timeout, models, source)


def resolve(project_root: Path) -> ReviewConfig:
    for layer in LAYERS:
        path = project_root / layer / FILE_NAME
        if path.is_file():
            return parse(path.read_text(encoding="utf-8"), path)
    return ReviewConfig()
