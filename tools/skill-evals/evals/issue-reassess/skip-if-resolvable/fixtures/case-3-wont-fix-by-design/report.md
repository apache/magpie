<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: PROJ-3902 — Config loader ignores environment overrides for nested keys
Reporter: pbrennan (2021-08-05)
Status: Open

Recent comments (newest last):

  [2021-08-06] pbrennan (CONTRIBUTOR):
    Expected the env var to win over the file value, like top-level keys do.

  [2021-09-14] rhalvorsen (MEMBER):
    Won't fix — per the dev@ thread
    https://lists.example.org/thread/nested-config-overrides this is by
    design: nested keys are file-only so that a partial env override can
    never produce a half-merged section. The behaviour is documented in
    the configuration reference (section "Override precedence").
