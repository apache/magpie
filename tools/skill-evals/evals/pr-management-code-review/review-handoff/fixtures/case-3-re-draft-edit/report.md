<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Session context:
- PR: #6501 — "Add retry jitter to HTTP provider"
- Draft disposition: REQUEST_CHANGES
- dry_run: false

Drafted review body:
> **REQUEST_CHANGES**
>
> ### [Testing]
> The `run_with_retry` method is new user-facing behaviour but no unit tests
> are included. Please add tests covering the happy path and the max-retries
> edge case.
>
> ---
> *This review was drafted by an AI-assisted tool and reviewed by a maintainer.
> Reply on the PR if anything looks incorrect.*

Maintainer response: "Change 'the happy path and the max-retries edge case' to 'happy path, zero-retries, and delay-overflow edge cases'. Then post it."
