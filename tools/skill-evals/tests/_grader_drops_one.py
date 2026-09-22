#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
"""Mock batched grader that silently drops one path on its first call.

Stands in for the real grader's intermittent habit of omitting a field from
a larger batch. The first invocation returns a verdict for every ``Field:``
path except the last one; every later invocation verdicts everything it is
asked about. Call state is kept in the file named by
``GRADER_DROP_STATE_FILE``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def main() -> None:
    paths = re.findall(r"^Field: (\S+)$", sys.stdin.read(), flags=re.MULTILINE)
    state = Path(os.environ["GRADER_DROP_STATE_FILE"])
    first_call = not state.exists()
    state.write_text((state.read_text() if state.exists() else "") + "call\n")
    answered = paths[:-1] if first_call and len(paths) > 1 else paths
    print(json.dumps({p: {"match": True, "reason": "ok"} for p in answered}))


if __name__ == "__main__":
    main()
