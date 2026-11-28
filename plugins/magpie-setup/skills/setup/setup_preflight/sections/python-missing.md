<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## python-missing — no Python the framework's tools can run on

The framework's tools run through `uv` on Python `<facts.version>`, and uv has none installed.
uv would normally download it on the first tool run, but under the secure setup the sandbox cannot: uv installs interpreters into `~/.local/share/uv/python`, which the sandbox may read but never write.

1. **Tell the user before anything else, in one line:**

   > Magpie's tools need Python `<facts.version>`, which isn't installed yet, and the sandbox can't install it. Run the command below once in your own terminal.

2. **Give them the command to run in their own terminal**, never through the agent:

   ```bash
   uv python install <facts.version>
   ```

   It downloads the interpreter from `releases.astral.sh` into uv's own directory, outside the sandbox, which is where it must come from.

Never install the interpreter from here, point uv at another directory, or widen a sandbox grant to make room for one.
Then carry on with the user's request; a step that runs a tool before the install fails with "Permission denied", and the user can rerun it after.
