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


"""Tests for ``check-skill-config.py``'s generated family config tables."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[1] / "check-skill-config.py"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_skill_config", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


def test_a_description_link_is_rebased_onto_the_family_readme():
    """The index prose is written from the template directory; copied verbatim
    into ``docs/<family>/README.md`` it only resolved while the two happened to
    sit at the same depth."""
    text = "See [`docs/skill-sources/`](../../../docs/skill-sources/README.md)."
    rebased = mod.rebase_links(text, Path("plugins/magpie-setup/templates"), Path("docs/setup"))
    assert rebased == "See [`docs/skill-sources/`](../skill-sources/README.md)."


def test_absolute_and_anchor_links_are_left_alone():
    text = "[a](https://example.org/x) [b](#section) [c](/root/path)"
    assert mod.rebase_links(text, Path("plugins/magpie-setup/templates"), Path("docs/setup")) == text


def test_generated_tables_link_the_real_template_directory():
    """GitHub does not follow the ``projects/_template`` directory symlink, so a
    rendered link through it would 404."""
    assert Path("plugins/magpie-setup/templates") == mod.TEMPLATE_DIR
    assert (REPO_ROOT / mod.TEMPLATE_DIR / "project.md").is_file()
    assert not (REPO_ROOT / mod.TEMPLATE_DIR).is_symlink()
