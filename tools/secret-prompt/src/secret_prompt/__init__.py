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
import re
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


# Variables that change how a command runs or where it reads its configuration; letting the
# caller set them would make the command shown in the prompt run something else.
_DENIED_NAMES = {"PATH", "IFS", "HOME", "ENV", "BASH_ENV", "SHELLOPTS", "BASHOPTS", "PS4"}
_DENIED_PREFIXES = ("LD_", "DYLD_", "PYTHON", "PERL5", "RUBY", "NODE_", "GIT_")
# npm's publish credential; it only authenticates, so it is safe to set despite its prefix.
_ALLOWED_NAMES = {"NODE_AUTH_TOKEN"}
# A dialog's prompt text is visible in its argv, so an inherited value is shown only when its
# name says where the secret goes and nothing in it suggests a credential. Names are matched
# by whole segments, so UNAUTHORIZED or KEYRING are not credentials.
_ROUTING_SEGMENTS = {
    "CERT",
    "ENDPOINT",
    "HOST",
    "INDEX",
    "REGISTRY",
    "REGISTRIES",
    "REPOSITORY",
    "URL",
    "USER",
    "USERNAME",
}
_SECRET_SEGMENTS = {
    "AUTH",
    "BEARER",
    "COOKIE",
    "CRED",
    "CREDENTIAL",
    "DSN",
    "HOOK",
    "JWT",
    "PAT",
    "PRIVATE",
    "PW",
    "PWD",
    "SESSION",
    "WEBHOOK",
}
_SECRET_SUFFIXES = ("TOKEN", "PASS", "PASSWORD", "PASSWD", "PASSPHRASE", "SECRET", "KEY")
_HIDDEN_VALUE = "(set; value not shown)"
_MAX_TEXT = 200
_MAX_COMMAND = 1000
# Characters GTK and Qt may render as markup in a dialog label.
_MARKUP = ("<", "&")

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
    # "--" ends osascript's option parsing, so text starting with "-" stays an argument.
    return _run_dialog(["osascript", "-e", _OSASCRIPT, "--", prompt, title], lambda r: "-128" in r.stderr)


def _refuse_markup(name: str, text: str) -> None:
    if any(char in text for char in _MARKUP):
        raise PromptBackendError(f"{name} may render '<' or '&' as markup, so it cannot show this prompt")


def ask_zenity(prompt: str, title: str) -> str:
    # A real Cancel exits 1 with nothing on stderr; GTK also exits 1, with a message, when it
    # cannot open the display.
    _refuse_markup("zenity", prompt + title)
    return _run_dialog(
        ["zenity", "--entry", "--hide-text", f"--title={title}", f"--text={prompt}"],
        lambda r: r.returncode == 1 and not r.stderr.strip(),
    )


def ask_kdialog(prompt: str, title: str) -> str:
    _refuse_markup("kdialog", prompt + title)
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
    names = [args.env]
    for item in args.set:
        name, sep, _ = item.partition("=")
        if not sep or not name.isidentifier():
            parser.error(f"--set {item!r} is not NAME=VALUE")
        names.append(name)
    for name in names:
        if is_denied_name(name):
            parser.error(f"{name} changes how the command runs, so secret-prompt will not set it")
    for option, text in (("--prompt", args.prompt), ("--title", args.title)):
        if text is not None and not is_plain_text(text):
            parser.error(
                f"{option} must be one line of at most {_MAX_TEXT} printable characters, not starting with '-'"
            )
    return args


def is_denied_name(name: str) -> bool:
    upper = name.upper()
    if upper in _ALLOWED_NAMES:
        return False
    return upper in _DENIED_NAMES or upper.startswith(_DENIED_PREFIXES)


def is_plain_text(text: str) -> bool:
    return len(text) <= _MAX_TEXT and not text.startswith("-") and all(char.isprintable() for char in text)


def is_credential_name(name: str) -> bool:
    # Each segment also without one trailing S, for TOKENS or SECRETS; never rstrip, or PASS loses it.
    forms = {form for seg in name.upper().split("_") for form in (seg, seg.removesuffix("S"))}
    return any(form in _SECRET_SEGMENTS or form.endswith(_SECRET_SUFFIXES) for form in forms)


def is_routing_name(name: str) -> bool:
    return not is_credential_name(name) and not _ROUTING_SEGMENTS.isdisjoint(name.upper().split("_"))


def is_plain_email(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}", value) is not None


def find_unshowable(command: Sequence[str], extra: Mapping[str, str]) -> str | None:
    """Name the first shown string that a control or bidi character could make lie, if any."""
    # shlex.join quotes a newline, ESC or U+202E but does not escape it, so it would still
    # rewrite or reorder the line the operator checks.
    if not all(arg.isprintable() for arg in command):
        return "the command"
    for name, value in extra.items():
        # An inherited name comes from the environment unchecked and can hold anything but '='.
        if not name.isidentifier():
            return "an inherited variable name"
        if len(value) > _MAX_TEXT or not value.isprintable():
            return name
    return None


def split_url(value: str) -> urllib.parse.SplitResult | None:
    if any(char.isspace() or char in "\"'" for char in value):
        return None
    try:
        parts = urllib.parse.urlsplit(value)
    except ValueError:
        return None
    return parts if parts.scheme and parts.netloc else None


def describe_inherited(name: str, value: str) -> str:
    """How an inherited variable appears in the prompt; ValueError when it cannot appear safely."""
    credential = is_credential_name(name)
    if is_denied_name(name):
        # It can make the command run something else (NODE_OPTIONS, GIT_ASKPASS), so it is shown
        # verbatim, or refused when it may also be a credential.
        if credential:
            raise ValueError(f"the inherited {name} changes how the command runs; unset it")
        return value
    at_hint = "; unset it, or remove the user and password from it"
    parts = split_url(value)
    if parts is not None:
        # urlsplit misreads an unencoded '/' in a password, so any '@' could hide the real host.
        if "@" in value:
            raise ValueError(f"the inherited {name} is a URL with a user or password{at_hint}")
        # A URL says where the secret may go, so its host is always shown; its path only under a
        # routing name, as elsewhere it may be the secret itself (a webhook).
        if not is_routing_name(name):
            return f"{parts.scheme}://{parts.netloc}/***"
        shown = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        return shown + ("?***" if parts.query else "") + ("#***" if parts.fragment else "")
    if credential:
        return _HIDDEN_VALUE
    if "://" in value:
        # Quoted or spaced, it is not parsed reliably enough to redact its query or userinfo.
        raise ValueError(f"the inherited {name} is not a URL it can show; unset it")
    if not is_routing_name(name):
        return _HIDDEN_VALUE
    # user:pw@proxy:3128, token@host, alice:s3cret or host/simple?token=... carry a credential;
    # me@example.org and proxy:3128 do not.
    has_userinfo = "@" in value and not is_plain_email(value)
    if has_userinfo or "?" in value or "#" in value or re.search(r":(?!\d+(/|$))", value):
        raise ValueError(f"the inherited {name} may hold a user, password or token{at_hint}")
    return value


def build_prompt(text: str, command: Sequence[str], extra: Mapping[str, str]) -> str:
    """The caller's text, then what it cannot change: the command and the variables it gets."""
    lines = [text, "", "It will be passed to:", shlex.join(command)]
    if extra:
        lines += ["", "with:", *(f"  {name}={value}" for name, value in sorted(extra.items()))]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    # Resolve the command before asking, and run exactly what the prompt shows.
    resolved = shutil.which(args.command[0])
    if resolved is None:
        print(f"secret-prompt: cannot run {args.command[0]}: not found; nothing was asked", file=sys.stderr)
        return 127
    command = [os.path.abspath(resolved), *args.command[1:]]
    if len(shlex.join(command)) > _MAX_COMMAND:
        # Shown in full or not at all: a truncated command could hide what it does.
        print(
            f"secret-prompt: the command is longer than {_MAX_COMMAND} characters; nothing was asked",
            file=sys.stderr,
        )
        return 1
    extra = dict(item.split("=", 1) for item in args.set)
    # Inherited variables sharing the secret's prefix (TWINE_* for TWINE_PASSWORD) can redirect
    # where it goes, e.g. TWINE_REPOSITORY_URL, so the operator sees those too.
    family = args.env.split("_", 1)[0] + "_" if "_" in args.env else None
    if family:
        for name, value in os.environ.items():
            if name.startswith(family) and name != args.env and name not in extra:
                try:
                    extra[name] = describe_inherited(name, value)
                except ValueError as err:
                    print(f"secret-prompt: {err}; nothing was asked", file=sys.stderr)
                    return 1
    unshowable = find_unshowable(command, extra)
    if unshowable:
        print(
            f"secret-prompt: {unshowable} cannot be shown as it is (a control or invisible character, "
            f"or a value over {_MAX_TEXT} characters); nothing was asked",
            file=sys.stderr,
        )
        return 1
    prompt = build_prompt(args.prompt or f"Paste the value for {args.env}", command, extra)
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
        os.execve(command[0], command, env)  # replaces this process; returns only by raising
    except OSError as err:
        print(f"secret-prompt: cannot run {command[0]}: {err.strerror}", file=sys.stderr)
    return 127
