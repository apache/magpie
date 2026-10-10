<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The PR is a layer of a stack

When the Step 2 stack probe returns a non-null `stack`, the PR's base
is the branch of the layer below, not the trunk, and its diff is that
layer alone. Add `Stack: #<S> layer <k>/<size>` to the headline, do **not**
apply the backport calibration to the non-trunk base, and say once per
stack: *"Chain, ordering and cross-layer checks are
`pr-management-stack-review pr:<N>`; continuing with this layer's
line-by-line review."* Approving a layer stays this skill's job; the
stack skill never approves.
