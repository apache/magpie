<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Checker output

PYTHONPATH="$HOME/.cache/apache-magpie/preflight" python3 -P -m setup_preflight.isolated_verify check --project-root .

```json
{
  "facts": {
    "platform": "Darwin",
    "harness": "claude",
    "project_root": "/home/alice/myrepo",
    "framework_checkout": "/home/alice/myrepo",
    "framework_found_via": "this repository",
    "framework_rejected": [],
    "settings": [
      {
        "path": "/etc/claude-code/managed-settings.json",
        "scope": "managed",
        "state": "absent"
      },
      {
        "path": ".claude/settings.local.json",
        "scope": "project-local",
        "state": "read"
      },
      {
        "path": ".claude/settings.json",
        "scope": "project",
        "state": "read"
      },
      {
        "path": "~/.claude/settings.json",
        "scope": "user",
        "state": "read"
      },
      {
        "path": "~/.claude/settings.local.json",
        "scope": "user-local (not loaded)",
        "state": "absent"
      }
    ]
  },
  "findings": [
    {
      "check": "1",
      "status": "pass",
      "evidence": [
        "sandbox.enabled: true (.claude/settings.json)",
        "permissions.deny: .claude/settings.json",
        "permissions.ask: .claude/settings.json",
        "sandbox.network.allowedDomains: .claude/settings.json",
        "sandbox.filesystem.allowRead: .claude/settings.local.json, .claude/settings.json",
        "sandbox.filesystem.allowWrite: .claude/settings.local.json, .claude/settings.json",
        "sandbox.filesystem.denyRead covers ~/: .claude/settings.json"
      ]
    },
    {
      "check": "2",
      "status": "pass",
      "evidence": [
        "PreToolUse Bash → sandbox-bypass-warn.sh",
        "PostToolUse Bash → sandbox-error-hint.sh",
        "statusLine → ~/.claude/scripts/sandbox-status-line.sh"
      ]
    },
    {
      "check": "3",
      "status": "pass",
      "evidence": [
        "sandbox-bypass-warn.sh: executable",
        "sandbox-error-hint.sh: executable",
        "sandbox-status-line.sh: executable"
      ]
    },
    {
      "check": "4",
      "status": "pass",
      "evidence": [
        "~/.bashrc: source ~/.claude/scripts/agent-iso.sh",
        "note: alias claude='claude-iso' set in ~/.bashrc"
      ]
    },
    {
      "check": "5",
      "status": "fail",
      "evidence": [
        "claude-code 2.1.150 is below the min_version floor 2.1.202",
        "bubblewrap/socat: not needed here (Seatbelt is built in)"
      ]
    },
    {
      "check": "6",
      "status": "pass",
      "evidence": [
        "effective sandbox.enabled: true (from .claude/settings.json): [sandbox]",
        "/etc/claude-code/managed-settings.json: sandbox.enabled = absent",
        ".claude/settings.local.json: sandbox.enabled = not set",
        ".claude/settings.json: sandbox.enabled = true",
        "~/.claude/settings.json: sandbox.enabled = not set",
        "~/.claude/settings.local.json: sandbox.enabled = absent"
      ]
    },
    {
      "check": "7",
      "status": "manual",
      "evidence": [
        "live denial probes, one Bash call each"
      ]
    },
    {
      "check": "8",
      "status": "pass",
      "evidence": [
        ".claude/settings.local.json: /home/alice/myrepo in allowRead and allowWrite",
        "scope: per-project (core.hooksPath unset)"
      ],
      "manual": [
        "live probe"
      ],
      "see": null
    },
    {
      "check": "9",
      "status": "n/a",
      "evidence": [
        "no vetted-ops config.toml and no vetted-op rule"
      ]
    },
    {
      "check": "10",
      "status": "n/a",
      "evidence": [
        "commit.gpgsign: unset",
        "SSH_AUTH_SOCK via gpg-agent: no"
      ]
    },
    {
      "check": "11",
      "status": "pass",
      "evidence": [
        "\"gh *\" in sandbox.excludedCommands: .claude/settings.json",
        "11b: no catch-all gh ask rule"
      ]
    },
    {
      "check": "12",
      "status": "manual",
      "evidence": [
        "container runtimes on PATH: none (12a-12d n/a)"
      ],
      "see": "conditional-checks.md#check-12--container-gateway-wired"
    },
    {
      "check": "13",
      "status": "n/a",
      "evidence": [
        "no eval-harness exclusion and no ~/.claude/scripts/magpie-run-evals.sh"
      ]
    },
    {
      "check": "14",
      "status": "manual",
      "evidence": [
        "n/a unless the magpie-adversarial-review plugin is installed"
      ],
      "see": "conditional-checks.md#check-14--adversarial-review-exclusion-if-installed"
    },
    {
      "check": "15",
      "status": "n/a",
      "evidence": [
        "permissions.blockReadsOutsideWorkingDirectories not true in any scope"
      ]
    },
    {
      "check": "16",
      "status": "n/a",
      "evidence": [
        "no vetted-ops config.toml and no vetted-op rule"
      ]
    },
    {
      "check": "17",
      "status": "n/a",
      "evidence": [
        "roborev not on PATH"
      ]
    },
    {
      "check": "18",
      "status": "manual",
      "evidence": [
        "local agent settings against the reconciliation"
      ]
    },
    {
      "check": "19",
      "status": "manual",
      "evidence": [
        "sandbox enabled"
      ]
    }
  ]
}
```

## Check 8 — live probe

Read .git/HEAD: OK (content: "ref: refs/heads/main")
Write .magpie-verify-probe.tmp: OK (removed)
