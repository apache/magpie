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

"""Fossil repository client and SQLite helpers."""

from __future__ import annotations

import os
import sqlite3
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any


class FossilError(Exception):
    """General exception for Fossil bridge errors."""


def clean_env() -> dict[str, str]:
    """Clean location-redirecting env variables."""
    return {
        k: v
        for k, v in os.environ.items()
        if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_PREFIX")
    }


def run_fossil(args: Sequence[str], cwd: Path | None = None) -> str:
    """Run a fossil command, returning its stdout."""
    try:
        proc = subprocess.run(
            ["fossil", *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            env=clean_env(),
        )
    except FileNotFoundError as exc:
        raise FossilError("fossil command not found. Ensure Fossil SCM is installed.") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise FossilError(f"fossil command failed (rc={proc.returncode}): {detail}")
    return proc.stdout


def find_repo_db(start_dir: Path) -> Path | None:
    """Resolve the Fossil repository database path from the checkout."""
    for d in (start_dir, *start_dir.parents):
        for marker in (".fslckg", "_FOSSIL_"):
            db_path = d / marker
            if db_path.exists():
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT value FROM vvar WHERE name = 'repository'")
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        return Path(row[0])
                except sqlite3.Error:
                    pass
    return None


def query_db(repo_path: Path, query: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    """Execute a read-only SQL query against the Fossil SQLite database."""
    try:
        conn = sqlite3.connect(repo_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        raise FossilError(f"Failed to query Fossil SQLite database: {exc}") from exc
