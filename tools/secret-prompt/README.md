<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`secret-prompt`](#secret-prompt)
  - [Prerequisites](#prerequisites)
  - [How to use](#how-to-use)
  - [How it asks](#how-it-asks)
  - [What it guarantees](#what-it-guarantees)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# `secret-prompt`

**Capability:** substrate:release

**Harness:** agnostic

Asks the operator for a secret, such as a single-use PyPI token, and runs
**one command** with it in **one environment variable**. The secret goes from
the prompt into that command's environment and nowhere else: it is never
printed, written to a file, or passed on a command line, so it stays out of
the shell history, `ps`, CI logs, and an agent's transcript.

It exists for the release steps that need a credential the release manager
holds — uploading the convenience packages to PyPI being the common one —
when the step is run by an agent on the release manager's behalf, or from a
script that has no terminal to prompt on. The release manager still types
or pastes the secret themselves, after checking the command the prompt names;
the agent only ever sees that command's output.

## Prerequisites

- **Runtime** — Python 3.11+ (stdlib only), run via `uv`.
- **CLIs** — one way to ask: a terminal, or `osascript` (macOS, built in),
  `zenity` or `kdialog` (Linux desktop), or `pinentry` (any OS with GnuPG,
  including `pinentry-mac`).
- **Credentials / auth** — None of its own; it carries the one secret the
  operator enters.
- **Network** — None; the command it runs may need some.

## How to use

```bash
secret-prompt --env TWINE_PASSWORD --set TWINE_USERNAME=__token__ --prefix pypi- \
    --title "PyPI upload" --prompt "Paste the single-use PyPI token" \
    -- twine upload dist/*.whl dist/*.tar.gz
```

Install it once, so the bare `secret-prompt` in a release recipe resolves:

```bash
uv tool install "git+https://github.com/apache/magpie#subdirectory=tools/secret-prompt"
```

Or run it without installing, from a checkout of this repository or straight from GitHub:

```bash
uv run --directory tools/secret-prompt --project . secret-prompt --env … -- <command>
uvx --from "git+https://github.com/apache/magpie#subdirectory=tools/secret-prompt" \
    secret-prompt --env … -- <command>
```

| Option | Meaning |
| --- | --- |
| `--env NAME` | Environment variable that receives the secret (required). |
| `--set NAME=VALUE` | A non-secret variable for the command too, repeatable (`TWINE_USERNAME=__token__`). |
| `--prefix TEXT` | Refuse a secret that does not start with `TEXT` (`pypi-`), so a wrong paste runs nothing. |
| `--prompt` / `--title` | Text of the prompt and dialog title. |
| `--backend` | `auto` (default), or force `tty`, `osascript`, `zenity`, `kdialog`, `pinentry`. |

Exit status is the command's own; `1` when no usable secret arrived (cancelled,
empty, the wrong prefix, or no backend could ask), `127` when the command cannot
be started.

## How it asks

`--backend auto` uses the first that applies:

1. **A terminal** (`/dev/tty` can be opened) — a hidden prompt there, even when
   stdin is redirected.
2. **macOS** — an `osascript` dialog with a hidden-answer field. The prompt text
   reaches AppleScript as an argument, never spliced into the script.
3. **A Linux desktop** (`DISPLAY` or `WAYLAND_DISPLAY` set) — `zenity --password`,
   else `kdialog --password`.
4. **`pinentry`** — the Assuan `GETPIN` exchange, which covers `pinentry-mac`,
   `pinentry-gnome3`, `pinentry-qt` and the curses ones.

When a backend *fails* rather than being cancelled — its program is missing, or
it cannot show a dialog — `auto` moves on to the next one and, if none can ask,
reports why. A **cancel** (the Cancel button, `Esc`, or `Ctrl-C`) stops there:
nothing else is asked and nothing runs.

An agent's command has no terminal, so on the release manager's Mac it gets
the dialog; the same command in the release manager's own terminal prompts
there instead. A **sandboxed** agent cannot show the macOS dialog — the
Seatbelt sandbox turns off Apple Events — so run the step outside the sandbox
(it is the release manager's upload either way), or let it fall back to
`pinentry`.

## What it guarantees

- The secret is passed only in the environment of the one command it runs
  (`exec`, so that command replaces the tool and keeps its exit status).
- Nothing runs unless a non-empty secret arrives that matches `--prefix`; a
  cancelled dialog runs nothing.
- Error messages name the expected prefix, never what was entered.
- Every prompt ends with what the caller cannot change: **`It will be passed to:`**
  the command, resolved to an absolute path before asking and run exactly as
  shown, and **`with:`** every `--set` variable plus any inherited variable that
  shares the secret's prefix (`TWINE_*` for `TWINE_PASSWORD`, so a
  `TWINE_REPOSITORY_URL` pointing elsewhere is visible). Check those lines
  before pasting: an agent chooses the command, and this is what stops a
  look-alike prompt from handing the token to something that prints or
  forwards it.
- `--set` values are shown as given. An inherited value is shown only when its
  name has a routing segment (`URL`, `HOST`, `REPOSITORY`, `REGISTRY`,
  `INDEX`, `ENDPOINT`, `USER`, `USERNAME`, `CERT`) and no credential-like one;
  every other is listed as `NAME=(set; value not shown)`, because a dialog
  receives the prompt in its argv. A name is credential-like when a segment,
  with or without a trailing `S`, is `AUTH`, `CRED`, `CREDENTIAL`, `JWT`,
  `PAT`, `PW`, `PWD`, `COOKIE`, `SESSION`, `BEARER`, `PRIVATE`, `WEBHOOK`,
  `HOOK` or `DSN`, or ends in `TOKEN`, `PASS`, `PASSWORD`, `PASSWD`,
  `PASSPHRASE`, `SECRET` or `KEY`.
- An inherited URL always shows its host, whatever its name, so where the
  secret may go is never hidden: up to its path under a routing name (query and
  fragment as `?***`/`#***`), otherwise only `scheme://host/***`.
- An inherited variable with one of the denied names below (`NODE_OPTIONS`
  beside `NODE_AUTH_TOKEN`) is shown verbatim, as it can make the command run
  something else.
- Nothing is asked when an inherited variable can't be shown safely. That
  means a URL containing `@` (a user or password, or a host that could be
  disguised), a `://` value too quoted or spaced to parse, or a routing value
  that may carry a credential: an `@` that is not a plain e-mail address, a
  `?` or `#`, or a `:` that is not a port (`user:pw@proxy`, `alice:s3cret`,
  `host/simple?token=…`). It also
  means a denied name that is also credential-like, a shown value with a
  control character or over 200 characters, or a name that is not a plain
  identifier. The error names the variable to unset. Only the secret's own
  prefix is scanned: npm's registry settings (`npm_config_registry`, `.npmrc`)
  are not shown.
- The command is shown in full or not at all: one longer than 1000 characters
  is refused, never truncated. Every command argument and every shown value
  must be printable — no newline, escape sequence or invisible bidi character
  that could rewrite or reorder those lines — and a value may be at most 200
  characters; otherwise nothing is asked. `--prompt` and `--title` must be a single
  printable line of at most 200 characters that does not start with `-`, so
  they cannot imitate the lines above; `zenity` and `kdialog`, whose toolkits may
  render `<` and `&` as markup, decline a prompt containing them and `auto`
  moves on to the next backend.
- `--env` and `--set` refuse names that change how the command runs or where it
  reads its configuration: `PATH`, `IFS`, `HOME`, `ENV`, `BASH_ENV`,
  `SHELLOPTS`, `BASHOPTS`, `PS4`, and the `LD_*`, `DYLD_*`, `PYTHON*`, `PERL5*`,
  `RUBY*`, `NODE_*` and `GIT_*` families — except `NODE_AUTH_TOKEN`, npm's
  publish credential.

What it cannot do is vouch for an environment the caller already controls:
an agent that sets `LD_PRELOAD` or edits `~/.pypirc` *before* calling it can
still subvert the command. The prompt shows what it can; when in doubt, run the
step yourself, in your own terminal.

It does **not** make the secret short-lived: create a single-use token for the
step and delete it straight after, as the release docs say.

## Tests

```bash
uv run --directory tools/secret-prompt --project . pytest
```

Every backend is exercised without a real dialog: `osascript` through a
patched `subprocess.run`, `pinentry` through a fake `pinentry` script on
`PATH`, which also drives an end-to-end run checking that the secret reaches
the command's environment and none of the output.
