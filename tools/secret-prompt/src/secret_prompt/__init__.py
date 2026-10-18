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

"""Ask the operator for a secret and run one command with it in one environment variable.

The secret goes from the prompt into the child process's environment and nowhere else: it is
never printed, written to a file or passed on a command line, so it stays out of the shell
history, ``ps`` and an agent's transcript. A cancelled or rejected prompt runs nothing.
"""

from __future__ import annotations

import argparse
import getpass
import os
import platform
import shlex
import shutil
import subprocess
import sys
import urllib.parse
from collections.abc import Callable, Mapping, Sequence

BACKENDS = ("tty", "osascript", "zenity", "kdialog", "pinentry")

# The prompt text reaches AppleScript as an argument, never spliced into the script source,
# so a quote in it cannot change what the dialog runs.
_OSASCRIPT = """on run argv
  set answer to display dialog (item 1 of argv) default answer "" with hidden answer with title (item 2 of argv) buttons {"Cancel", "OK"} default button "OK"
  return text returned of answer
end run"""


class PromptCancelledError(Exception):
    """The operator dismissed the prompt."""


class PromptBackendError(Exception):
    """A backend could not ask: its program is missing, or it failed without the operator's say."""


# pinentry's GPG_ERR_CANCELED, as "ERR 83886179 Operation cancelled".
_PINENTRY_CANCELLED = "83886179"


def has_tty() -> bool:
    try:
        with open("/dev/tty"):
            return True
    except OSError:
        return False


def has_display(env: Mapping[str, str]) -> bool:
    return bool(env.get("DISPLAY") or env.get("WAYLAND_DISPLAY"))


def candidate_backends(
    system: str,
    env: Mapping[str, str],
    tty: bool,
    which: Callable[[str], str | None] = shutil.which,
) -> list[str]:
    """The ways to ask, in order: the terminal when there is one, then the platform's dialogs."""
    names = ["tty"] if tty else []
    if system == "Darwin" and which("osascript"):
        names.append("osascript")
    if has_display(env):
        names.extend(name for name in ("zenity", "kdialog") if which(name))
    if which("pinentry"):
        names.append("pinentry")
    if not names:
        raise PromptBackendError(
            "no terminal, and none of osascript (macOS), zenity or kdialog (Linux desktop) "
            "or pinentry is available"
        )
    return names


def _excerpt(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return lines[-1][:200] if lines else "no error output"


def ask_tty(prompt: str, title: str) -> str:
    # getpass reads from /dev/tty with echo off, even when stdin is redirected.
    try:
        return getpass.getpass(f"{prompt}: ")
    except (EOFError, KeyboardInterrupt) as err:
        raise PromptCancelledError("prompt cancelled") from err


def _run(cmd: Sequence[str], input: str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, input=input, capture_output=True, text=True, check=False)
    except OSError as err:
        raise PromptBackendError(f"cannot run {cmd[0]}: {err.strerror}") from err


def _run_dialog(cmd: Sequence[str], cancelled: Callable[[subprocess.CompletedProcess[str]], bool]) -> str:
    result = _run(cmd)
    if result.returncode == 0:
        return result.stdout
    if cancelled(result):
        raise PromptCancelledError("prompt cancelled")
    # A dialog's stderr never holds the secret, so an excerpt is safe to show.
    raise PromptBackendError(f"{cmd[0]} failed: {_excerpt(result.stderr)}")


def ask_osascript(prompt: str, title: str) -> str:
    # The Cancel button is AppleScript error -128; any other failure (e.g. Apple Events
    # blocked by a sandbox) means no dialog was shown.
    return _run_dialog(["osascript", "-e", _OSASCRIPT, prompt, title], lambda r: "-128" in r.stderr)


def ask_zenity(prompt: str, title: str) -> str:
    # A real Cancel exits 1 with nothing on stderr; GTK also exits 1, with a message, when it
    # cannot open the display.
    return _run_dialog(
        ["zenity", "--entry", "--hide-text", f"--title={title}", f"--text={prompt}"],
        lambda r: r.returncode == 1 and not r.stderr.strip(),
    )


def ask_kdialog(prompt: str, title: str) -> str:
    return _run_dialog(["kdialog", "--title", title, "--password", prompt], lambda r: r.returncode == 1)


def _assuan_quote(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def ask_pinentry(prompt: str, title: str, program: str = "pinentry") -> str:
    """Speak the Assuan protocol to pinentry: describe the request, then GETPIN."""
    script = (
        f"SETTITLE {_assuan_quote(title)}\nSETDESC {_assuan_quote(prompt)}\nSETPROMPT Secret:\nGETPIN\nBYE\n"
    )
    result = _run([program], input=script)
    for line in result.stdout.splitlines():
        if line.startswith("D "):
            return urllib.parse.unquote(line[2:])
        if line.startswith("ERR"):
            fields = line.split()
            if len(fields) > 1 and fields[1] == _PINENTRY_CANCELLED:
                raise PromptCancelledError("prompt cancelled")
            raise PromptBackendError(f"{program} failed: {line[:200]}")
    raise PromptBackendError(f"{program} failed: {_excerpt(result.stderr)}")


ASKERS: dict[str, Callable[[str, str], str]] = {
    "tty": ask_tty,
    "osascript": ask_osascript,
    "zenity": ask_zenity,
    "kdialog": ask_kdialog,
    "pinentry": ask_pinentry,
}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="secret-prompt",
        description="Ask for a secret and run COMMAND with it in the environment variable --env.",
        epilog="Example: secret-prompt --env TWINE_PASSWORD --prefix pypi- -- twine upload dist/*",
    )
    parser.add_argument("--env", required=True, help="environment variable that receives the secret")
    parser.add_argument("--prompt", help="text shown in the prompt (default: names the variable)")
    parser.add_argument("--title", default="Secret needed", help="dialog title")
    parser.add_argument(
        "--prefix", default="", help="refuse a secret that does not start with this, e.g. pypi-"
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="also set a non-secret variable for the command, e.g. TWINE_USERNAME=__token__",
    )
    parser.add_argument("--backend", choices=("auto", *BACKENDS), default="auto")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="the command to run, after --")
    args = parser.parse_args(argv)
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("give the command to run after --")
    if not args.env.isidentifier():
        parser.error(f"--env {args.env!r} is not a valid environment variable name")
    for item in args.set:
        name, sep, _ = item.partition("=")
        if not sep or not name.isidentifier():
            parser.error(f"--set {item!r} is not NAME=VALUE")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    # Always name the receiving command, so the operator can see where the secret goes
    # before pasting it; the caller cannot turn this off.
    command = shlex.join(args.command)
    if len(command) > 300:
        command = command[:297] + "..."
    prompt = f"{args.prompt or f'Paste the value for {args.env}'}\n\nIt will be passed to: {command}"
    backends = [args.backend] if args.backend != "auto" else None
    failures: list[str] = []
    secret = ""
    try:
        for backend in backends or candidate_backends(platform.system(), os.environ, has_tty()):
            try:
                secret = ASKERS[backend](prompt, args.title).strip()
                break
            except PromptBackendError as err:
                failures.append(f"{backend}: {err}")
        else:
            raise PromptBackendError("; ".join(failures))
    except PromptCancelledError as err:
        print(f"secret-prompt: {err}; {args.command[0]} was not run", file=sys.stderr)
        return 1
    except PromptBackendError as err:
        print(
            f"secret-prompt: could not ask for the secret ({err}); {args.command[0]} was not run",
            file=sys.stderr,
        )
        return 1
    if not secret:
        print(f"secret-prompt: no secret entered; {args.command[0]} was not run", file=sys.stderr)
        return 1
    if args.prefix and not secret.startswith(args.prefix):
        # Name only the expected prefix: echoing what was pasted would leak it.
        print(
            f"secret-prompt: the secret does not start with {args.prefix!r}; {args.command[0]} was not run",
            file=sys.stderr,
        )
        return 1
    env = dict(os.environ)
    env.update(item.split("=", 1) for item in args.set)
    env[args.env] = secret
    try:
        os.execvpe(args.command[0], args.command, env)
    except OSError as err:
        print(f"secret-prompt: cannot run {args.command[0]}: {err.strerror}", file=sys.stderr)
        return 127
