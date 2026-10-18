<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Quality signals to check — image IP

`code-review context` lists added images under `images_to_judge`; the judgement is yours.

The "Quality signals to check" category is primarily driven by the adopter's
source files. The following is a **framework-level default** that applies
regardless of adopter-specific rules.

When the diff adds one or more binary image files (`.png`, `.jpg`, `.jpeg`,
`.gif`, `.svg`, `.ico`, `.webp`), use judgment rather than raising an
automatic finding:

- **Contributor-created screenshots, diagrams, and documentation graphics**
  are legitimate by default — no finding.
- **Logos, brand assets, or illustrations** that look professionally produced
  warrant a short comment asking the contributor to confirm the source and
  licence: *"Could you confirm this image is original work or confirm its
  licence? If it's from a third-party source, it may need a `LICENSE` entry
  or a different approach."*

Do not flag every image addition. The signal is the visual character of the
asset — a hand-drawn architecture diagram is different from a polished brand
logo. When in doubt, ask rather than block.
