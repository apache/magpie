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

"""Fossil wiki subsystem integration."""

from __future__ import annotations

from pathlib import Path

from magpie_fossil.client import run_fossil


def list_wiki(repo_path: Path) -> list[str]:
    """List all wiki page names in the repository."""
    out = run_fossil(["wiki", "list", "-R", str(repo_path)])
    return [line.strip() for line in out.splitlines() if line.strip()]


def read_wiki(repo_path: Path, name: str) -> str:
    """Read content of a specific wiki page."""
    return run_fossil(["wiki", "export", name, "-R", str(repo_path)])
