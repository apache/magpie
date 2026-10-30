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

"""`python3 -m setup_preflight` — the form the shared pre-flight block uses.

The block runs the copy in the user's personal config layer (see
`layers.py`), which is on `PYTHONPATH` rather than installed,
so `-m` is what resolves the package's own relative imports.

It refuses to run on a Python older than 3.11 before importing anything
else: the block treats a non-zero exit as "the checker did not run",
never as a pass. Keep this file free of syntax a 3.x interpreter cannot
parse, so an old `python3` reaches the refusal instead of a SyntaxError.
"""

import sys

MIN_PYTHON = (3, 11)

# The block runs whatever `python3` is on PATH, which requires-python does not govern.
if sys.version_info < MIN_PYTHON:
    sys.stderr.write(
        f"setup_preflight needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or later; this is {sys.version_info[0]}.{sys.version_info[1]} ({sys.executable}). "
        "Put a newer python3 first on PATH.\n"
    )
    raise SystemExit(3)

from .cli import main  # noqa: E402 - only after the version check

raise SystemExit(main())
