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

"""setup-isolated-setup-install lefthook hooks-path guard (skill-contributed).

`lefthook install --force` writes lefthook's hook into the directory the global
`core.hooksPath` names, over the framework's dispatcher, and
`--reset-hooks-path` unsets the whole-user setup. Both are destructive when
that path is the framework's own. Discovered by the agent-guard dispatcher;
import-free (uses ``ctx``).
"""

import os

TRIGGERS = ["lefthook:install"]

FRAMEWORK_HOOKS_PATHS = ("~/.claude/git-hooks", "~/.claude-config/git-hooks")


def _install_arguments(argv):
    """The arguments after the ``install`` subcommand, or an empty list."""
    for index, token in enumerate(argv[1:], start=1):
        if token.startswith("-"):
            continue
        return argv[index + 1 :] if token == "install" else []
    return []


def _destructive_flag(argument):
    # lefthook takes the `--flag=value` spelling for its boolean flags, so match
    # the name and read the value separately: `--force=true` is destructive,
    # `--force=false` is not.
    name, _, value = argument.partition("=")
    off = value.lower() in ("false", "0", "f", "no", "off")
    if name in ("-f", "--force"):
        return None if off else "--force"
    if name in ("-r", "--reset-hooks-path"):
        return None if off else "--reset-hooks-path"
    if name.startswith("-") and not name.startswith("--"):
        # In a bundle (`-fr=false`) the value belongs to the last switch only;
        # every switch before it is set.
        letters = name[1:-1] if off else name[1:]
        if "f" in letters:
            return "--force"
        if "r" in letters:
            return "--reset-hooks-path"
    return None


def _is_framework_path(value):
    actual = os.path.normcase(os.path.realpath(os.path.expanduser(value)))
    return any(
        actual == os.path.normcase(os.path.realpath(os.path.expanduser(name)))
        for name in FRAMEWORK_HOOKS_PATHS
    )


def guard(ctx):
    flag = None
    for argument in _install_arguments(ctx.argv):
        flag = _destructive_flag(argument)
        if flag:
            break
    if flag is None:
        return None
    if ctx.override("MAGPIE_ALLOW_LEFTHOOK_HOOKS_PATH"):
        return None
    hooks_path = ctx.run(["git", "config", "--global", "--get", "core.hooksPath"])
    if not hooks_path or not _is_framework_path(hooks_path):
        return None
    effect = "unset" if flag == "--reset-hooks-path" else "replace"
    return (
        f"agent-guard[lefthook-hooks-path]: `lefthook install {flag}` would {effect} the "
        f"framework's global core.hooksPath ({hooks_path}). Run plain `lefthook install`: "
        "the ~/.claude/bin/lefthook shim keeps the hook in this repository's own hooks "
        "dir. Override: MAGPIE_ALLOW_LEFTHOOK_HOOKS_PATH=1."
    )
