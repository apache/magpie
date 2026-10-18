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

"""Bundled example contributed guard: block ``git commit --no-verify``.

This is the **template** for skill-contributed guards. To add a guard, drop a
file shaped like this into any discovered ``guards.d`` directory — no edit to
``agent_guard`` and no change to the ``settings.json`` hook wiring is needed; the
dispatcher discovers it automatically.

The contract:

* ``TRIGGERS`` — optional list of command families this guard cares about
  (``"gh"``, ``"git:commit"``, ``"git:push"``, …). Omit to run on every guarded
  command. The dispatcher uses it as a cheap pre-filter.
* ``guard(ctx)`` — return a deny-reason string to block the command, or ``None``
  to allow it. ``ctx`` is the ``GuardContext`` (see ``agent_guard``); the guard
  imports nothing.

This guard blocks ``--no-verify`` / ``-n`` (which skips the prek hooks — license
headers, placeholders, lint, the validator) unless the maintainer overrides it.
"""

TRIGGERS = ["git:commit"]


def guard(ctx):
    if ctx.git_subcommand() != "commit":
        return None
    if not any(tok in ("--no-verify", "-n") for tok in ctx.argv):
        return None
    if ctx.override("MAGPIE_ALLOW_NO_VERIFY"):
        return None
    return (
        "agent-guard[no-verify]: `git commit --no-verify` skips the prek hooks "
        "(license headers, placeholder check, lint, the skill/tool validator). "
        "Commit without --no-verify so the checks run, or override with "
        "MAGPIE_ALLOW_NO_VERIFY=1 if you are certain."
    )
