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
Reading files the agent must not be able to redirect.

The write entry points run outside the sandbox, so every file they act on (the
policy, a body to publish) is read without following a symlink anywhere on its
path, from the very descriptor that was checked.
"""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path


def symlink_free(path: Path) -> bool:
    """Whether no component of the absolute ``path`` is a symlink."""
    lexical = os.path.abspath(path)
    return os.path.realpath(lexical) == lexical


class TamperedPath(RuntimeError):
    """A symlink on the path, or something other than a regular file at its end."""


def read_regular_file(path: Path) -> bytes | None:
    """The bytes of the regular file at ``path``, or None if it does not exist.

    Every component is opened relative to the previous one with ``O_NOFOLLOW``,
    so a symlink anywhere on the path is refused and the file read is the very
    one checked: no window between a check and an open for a swap to land in.
    Raises `TamperedPath` for a symlink or a non-regular file.
    """
    parts = Path(os.path.abspath(path)).parts
    dir_fd = os.open(parts[0], os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in parts[1:-1]:
            try:
                next_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
            except FileNotFoundError:
                return None
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise TamperedPath(
                        f"{path}: {name!r} on its path is a symlink or not a directory"
                    ) from None
                raise
            os.close(dir_fd)
            dir_fd = next_fd
        try:
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
        except FileNotFoundError:
            return None
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise TamperedPath(f"{path} is a symlink") from None
            raise
    finally:
        os.close(dir_fd)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise TamperedPath(f"{path} is not a regular file")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(fd)
