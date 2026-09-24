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
from __future__ import annotations

from pathlib import Path

import pytest

from adversarial_review.config import ConfigError, ReviewConfig, parse, resolve

SRC = Path("adversarial-review.md")
FULL = """\
# Adversarial review

```yaml
adversarial_review:
  mode: on-pr-create        # on-pr-create | on-demand | off
  reviewers: [codex, copilot]
  timeout_minutes: 10
  models:                   # optional per-backend overrides
    copilot: gpt-5
```
"""


def test_full_example_from_the_spec():
    cfg = parse(FULL, SRC)
    assert cfg == ReviewConfig("on-pr-create", ("codex", "copilot"), 10.0, {"copilot": "gpt-5"}, SRC)


def test_defaults_when_keys_are_absent():
    cfg = parse("```yaml\nadversarial_review:\n  reviewers: [gemini]\n```\n", SRC)
    assert cfg.mode == "on-pr-create" and cfg.timeout_minutes == 8.0 and cfg.models == {}


def test_no_file_means_no_reviewers(tmp_path):
    assert resolve(tmp_path) == ReviewConfig()


def test_personal_layer_wins_whole(tmp_path):
    for layer, body in (
        (".apache-magpie-overrides", "[codex, copilot]"),
        (".apache-magpie-local", "[gemini]"),
    ):
        (tmp_path / layer).mkdir()
        (tmp_path / layer / "adversarial-review.md").write_text(
            f"```yaml\nadversarial_review:\n  mode: off\n  reviewers: {body}\n```\n", encoding="utf-8"
        )
    cfg = resolve(tmp_path)
    assert (
        cfg.reviewers == ("gemini",)
        and cfg.source == tmp_path / ".apache-magpie-local" / "adversarial-review.md"
    )


@pytest.mark.parametrize(
    ("block", "message"),
    [
        ("adversarial_review:\n  mode: sometimes\n", "mode"),
        ("adversarial_review:\n  reviewers: [codex, vim]\n", "unknown reviewer"),
        ("adversarial_review:\n  reviewers: codex\n", "list"),
        ("adversarial_review:\n  timeout_minutes: soon\n", "timeout_minutes"),
        ("adversarial_review:\n  timeout_minutes: 0\n", "timeout_minutes"),
        ("adversarial_review:\n  colour: blue\n", "unknown key"),
        ("adversarial_review:\n  models:\n    vim: x\n", "unknown reviewer"),
        ("adversarial_review:\n   mode: off\n", "indentation"),
        ("other:\n  mode: off\n", "adversarial_review"),
    ],
)
def test_invalid_config_is_an_error_naming_the_problem(block, message):
    with pytest.raises(ConfigError, match=message):
        parse(f"```yaml\n{block}```\n", SRC)


def test_file_without_a_block_is_an_error():
    with pytest.raises(ConfigError, match="no ```yaml block"):
        parse("# nothing here\n", SRC)


def test_the_shipped_template_parses():
    template = Path(__file__).resolve().parents[3] / "projects" / "_template" / "adversarial-review.md"
    cfg = parse(template.read_text(encoding="utf-8"), template)
    assert cfg.mode == "on-pr-create" and cfg.reviewers == () and cfg.timeout_minutes == 8.0
