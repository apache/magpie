<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## step-10 — the verify interval has elapsed

Suggest `/magpie-setup verify`, once, and say why it is worth taking:
`verify` is the only place a sandboxed session's own latest-version
comparison happens, because the plugin cache it would need to read is
denied there.

`setup.verify_interval_days` resolves project → organization → framework.
Write `verify_suggested_at` when you show the suggestion, whether or not
the user takes it — a suggestion already made re-arms the clock as surely as a `verify`
that was taken, so the same project is not told twice inside one window.
A project just configured or adopted needs no reminder to verify what it
was just checked against, which is why the comparison falls back to the
stamp's `at:`.
