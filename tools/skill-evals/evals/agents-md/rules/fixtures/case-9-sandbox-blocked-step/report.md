<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

A step you need fails on a sandbox restriction: the proxy does not carry the transport it needs.

A. Re-run the command with the sandbox disabled.
B. Look for a route that stays inside the sandbox or a vetted operation that covers it; failing that, give the user the one command to run and propose an upstream fix.
C. Add the command to `sandbox.excludedCommands` so it works from now on.
