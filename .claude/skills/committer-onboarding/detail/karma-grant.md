<!-- SPDX-License-Identifier: Apache-2.0 -->
# Karma grant guide

Step-by-step instructions for each karma-grant action in
Step 2 of `committer-onboarding`. Work through these in
order; confirm each one with the nominator before moving on.

Whimsy (https://whimsy.apache.org) is the most convenient tool for
roster management at the ASF. It is a derived source. The
authoritative records are:

- **Committer group membership** → LDAP (grants actual resource access)
- **PMC membership** → `committee-info.txt` in the foundation/officers
  SVN repository (the official ASF record per policy; LDAP committee
  group is a derived copy)

Whimsy writes to both LDAP and committee-info.txt when you use the
roster tool, so using Whimsy is the correct single step for either
type of addition. GitHub org membership and other downstream systems
derive from LDAP automatically via gitbox.

---

## Whimsy roster update (do this first)

Adding the candidate in Whimsy writes to LDAP — the single step that
grants project resource access and updates the public roster.

### Incubating podling

1. Open https://whimsy.apache.org/roster/ppmc/<podling>
2. Log in with your Apache credentials (any current PPMC member
   can make this change).
3. To add as a **committer**: click **Add committer** in the
   Committers section and enter `<apache-id>`.
4. To add as a **PPMC member** (`committer-to-pmc` or
   `direct-to-pmc` scenarios): click **Add PPMC member** in the
   PPMC section instead (or in addition for `direct-to-pmc`, where
   both roles are granted at once).
5. Changes take effect in LDAP within a few minutes; GitHub org
   membership via gitbox propagates automatically from there.

> If you are not a PPMC member, ask another PPMC member or your
> IPMC mentor to make the update.

### Top-level project

1. Open https://whimsy.apache.org/roster/committee/<project>
2. Log in with your Apache credentials (any current PMC member
   can make this change).
3. To add as a **committer**: click **Add committer** in the
   Committers section and enter `<apache-id>`.
4. To add as a **PMC member** (`committer-to-pmc` or
   `direct-to-pmc` scenarios): click **Add PMC member** in the
   PMC section instead (or in addition for `direct-to-pmc`, where
   both roles are granted at once).
5. Changes take effect in LDAP within a few minutes; GitHub org
   membership via gitbox propagates automatically from there.

> If you are not a PMC member, ask another PMC member to make the
> update.

---

## Mailing lists

Mailing list subscriptions are self-managed by the new committer or
PMC/PPMC member. The nominator does not need to subscribe them or
take any action on their behalf.

**Public lists** — the new member subscribes themselves via the
Whimsy self-service page:
https://whimsy.apache.org/roster/committer/__self__

**Private@ (PMC members for TLPs / PPMC members for podlings only)**
— the new member subscribes themselves in one of two ways:

- Via the Whimsy self-service page above, or
- By sending a subscribe request to `private-subscribe@<project>.apache.org`
  (a moderator will approve it)

Committers-only (not PMC/PPMC) do not join private@.

---

## Issue tracker (Jira / GitHub Issues)

If the project uses **GitHub Issues**, committer rights flow
from the GitHub org membership — no separate step needed.

If the project uses **Jira** (https://issues.apache.org/jira):

1. Log in as a project admin.
2. Go to **Project settings → People**.
3. Add `<apache-id>@apache.org` with role **Developers**.

---

## Verification

After completing all steps, confirm the Whimsy committer profile
shows the new project:

```text
https://whimsy.apache.org/roster/committer/<apache-id>
```

If the profile does not show the project after 15 minutes,
the LDAP sync may be lagging — wait another 15 minutes and retry.
If still missing, raise with infrastructure@apache.org.
