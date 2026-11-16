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
The Vulnogram CVE-tool operations: the ASF CVE tool, run outside the sandbox.

The ``vulnogram-api-*`` commands read an OAuth session from
``~/.config/apache-magpie/``, which the sandbox denies, so an agent cannot run
them itself. Excluding them from the sandbox as they are would hand the agent
their whole flag surface: ``--credentials`` (a session file it wrote, naming
a host of its choosing), ``--allow-state-downgrade``, ``--allow-product-change``
and the rest. These operations instead run each command with a fixed argv:

* the client is the copy shipped beside vetted-ops (``tool_dir``), never a path
  the agent can write;
* only the CVE id, the record JSON (piped on stdin, the bytes vetted-ops
  validated) and the allocation title are the caller's; every override flag
  stays off, so the record commands' merge-mode guards always apply;
* the child gets an allowlisted environment (``child_env``): ``HOME`` from the
  password database, a fixed ``PATH``, locale and ``TMPDIR`` only. No
  ``VULNOGRAM_*`` session override and no ``PYTHON*`` / ``UV_*`` / ``DYLD_*`` /
  ``LD_*`` variable reaches it, so the session is always the user's own
  default file and nothing the caller exports changes what Python or uv load.

Publishing a record (``vulnogram-api-record-publish``) is deliberately absent:
it is the release manager's terminal step and stays a hand-run command.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .config import account_home

#: The client's directory, relative to the ``tools/`` tree vetted-ops ships in.
TOOL_SUBDIR = Path("cve-tool-vulnogram") / "oauth-api"

#: The stable path the vetted-ops plugin's SessionStart hook points at the
#: installed plugin's ``tools/vetted-ops`` (outside every sandbox-writable root).
#: Resolved from the password database, never ``$HOME``.
STABLE_LINK = account_home() / ".claude" / "magpie" / "vetted-ops"

#: The only variables copied from the caller's environment into the child.
#: Everything else (``VULNOGRAM_*``, ``PYTHON*``, ``UV_*``, ``DYLD_*``, ``LD_*``,
#: ``VIRTUAL_ENV``, proxies) is dropped.
PASSED_ENV = ("LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ", "TMPDIR")

#: The child's ``PATH`` after the directory ``uv`` was found in.
SYSTEM_PATH = ("/usr/bin", "/bin")

#: Console scripts each operation may run, and nothing else.
SCRIPTS = frozenset({"vulnogram-api-record-fetch", "vulnogram-api-record-update", "vulnogram-api-allocate"})


def tool_dir() -> Path:
    """The trusted Vulnogram client directory.

    Same rule as :func:`vetted_ops.tracker_backends.backend_dir`: from a source
    tree (a checkout, or ``uv run --project`` on the installed plugin) the
    client is the sibling ``tools/cve-tool-vulnogram/oauth-api``; from an
    installed wheel the module sits in a uv cache the agent can write to, so the
    client comes from beside the protected stable link instead.
    """
    here = Path(__file__).resolve()
    if here.parents[1].name == "src" and (here.parents[2] / "pyproject.toml").is_file():
        return here.parents[3] / TOOL_SUBDIR
    return STABLE_LINK.resolve().parent / TOOL_SUBDIR


def uv_executable() -> str:
    """``uv`` as an absolute path, so the child's ``PATH`` cannot pick another one.

    It is looked up on the ``PATH`` vetted-op itself was started with — the
    harness's, since a caller that prefixes the command with its own variables
    no longer matches the sandbox exclusion that runs it out here.
    """
    found = shutil.which("uv")
    if found is None:
        raise FileNotFoundError("uv is not on PATH; the Vulnogram operations run the client with it")
    return str(Path(found).resolve())


def argv(script: str, *args: str) -> list[str]:
    """The fixed command line for one Vulnogram console script."""
    if script not in SCRIPTS:  # pragma: no cover - the catalogue names only these
        raise ValueError(f"{script!r} is not a vetted Vulnogram command")
    return [uv_executable(), "run", "--quiet", "--project", str(tool_dir()), script, *args]


def is_cve_tool_argv(command: list[str]) -> bool:
    """True when ``command`` is exactly the shape :func:`argv` builds."""
    return (
        len(command) >= 6
        and command[0] == uv_executable()
        and command[1:4] == ["run", "--quiet", "--project"]
        and command[4] == str(tool_dir())
        and command[5] in SCRIPTS
    )


def child_env() -> dict[str, str]:
    """The allowlisted environment for a Vulnogram command (see :data:`PASSED_ENV`)."""
    env = {k: os.environ[k] for k in PASSED_ENV if k in os.environ}
    env["HOME"] = str(account_home())
    env["PATH"] = os.pathsep.join((str(Path(uv_executable()).parent), *SYSTEM_PATH))
    return env
