// SPDX-License-Identifier: Apache-2.0
//
// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.

import { describe, test } from 'claude-code/testing';
import {
  evaluatePublicSurfaceCommand,
  findForbiddenTerms,
  parseProjectManifest,
  parseSubcommand,
  register,
  resolvePath,
  resolveProjectConfig,
  splitShellCommands,
} from './public-surface-scrub.ts';

function assert(condition: any, message?: string): void {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

function assertStrictEqual(actual: any, expected: any, message?: string): void {
  if (actual !== expected) {
    throw new Error(message || `Expected ${JSON.stringify(expected)} but got ${JSON.stringify(actual)}`);
  }
}

function assertDeepStrictEqual(actual: any, expected: any): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Expected deep equality: ${JSON.stringify(expected)} !== ${JSON.stringify(actual)}`);
  }
}

describe('Deterministic Public-Surface Scrub mod (family:security)', () => {
  describe('findForbiddenTerms', () => {
    test('returns empty array on neutral behavioral changes', () => {
      assertDeepStrictEqual(findForbiddenTerms('Fix asset graph view leaking DAGs outside user permissions'), []);
      assertDeepStrictEqual(findForbiddenTerms('Add access_key and connection_string to DEFAULT_SENSITIVE_FIELDS'), []);
      assertDeepStrictEqual(findForbiddenTerms('Improve xcom value handling in extra links API'), []);
      assertDeepStrictEqual(findForbiddenTerms(''), []);
      assertDeepStrictEqual(findForbiddenTerms(null as any), []);
    });

    test('detects CVE references', () => {
      const hits = findForbiddenTerms('Fix CVE-2026-12345 in connection test');
      assert(hits.includes('CVE reference'));
      const bareHits = findForbiddenTerms('Address issue reported as cve');
      assert(bareHits.includes('CVE reference'));
    });

    test('detects vulnerability and security fix keywords (spaced and hyphenated)', () => {
      assert(findForbiddenTerms('Fix critical vulnerability in parsing logic').includes('vulnerability'));
      assert(findForbiddenTerms('Security fix for webserver endpoints').includes('security fix'));
      assert(findForbiddenTerms('Apply security-fix for session timeout').includes('security fix'));
      assert(findForbiddenTerms('Security patch for query builder').includes('security fix'));
      assert(findForbiddenTerms('Apply critical security-patch').includes('security fix'));
      assert(findForbiddenTerms('Security advisory update').includes('security fix'));
      assert(findForbiddenTerms('Contact security@apache.org for details').includes('security mailing list'));
    });

    test('detects vulnerability classes with whitespace and hyphens', () => {
      assert(findForbiddenTerms('Prevent SSRF in HTTP provider').includes('SSRF'));
      assert(findForbiddenTerms('Mitigate stored XSS in log view').includes('XSS'));
      assert(findForbiddenTerms('Add CSRF token validation').includes('CSRF'));
      assert(findForbiddenTerms('Prevent SQL injection in search filter').includes('SQL injection'));
      assert(findForbiddenTerms('Mitigate SQL-injection in query filter').includes('SQL injection'));
      assert(findForbiddenTerms('Fix path traversal in file download').includes('path traversal'));
      assert(findForbiddenTerms('Prevent path-traversal in file handler').includes('path traversal'));
      assert(findForbiddenTerms('Prevent remote code execution in worker').includes('remote code execution'));
      assert(findForbiddenTerms('Close RCE vector in serializer').includes('remote code execution'));
      assert(findForbiddenTerms('Fix remote-code-execution vulnerability').includes('remote code execution'));
      assert(findForbiddenTerms('Fix privilege escalation in role mapper').includes('privilege escalation'));
      assert(findForbiddenTerms('Prevent privilege-escalation bug').includes('privilege escalation'));
      assert(findForbiddenTerms('Fix auth bypass in REST API').includes('auth bypass'));
      assert(findForbiddenTerms('Mitigate auth-bypass vulnerability').includes('auth bypass'));
    });

    test('returns multiple matched terms uniquely', () => {
      const terms = findForbiddenTerms('Fix CVE-2026-9999: critical SSRF vulnerability allowing auth-bypass');
      assert(terms.includes('CVE reference'));
      assert(terms.includes('SSRF'));
      assert(terms.includes('vulnerability'));
      assert(terms.includes('auth bypass'));
    });
  });

  describe('parseProjectManifest & resolveProjectConfig', () => {
    test('extracts tracker_repo and upstream_repo from markdown tables', () => {
      const sample = `
# Project Manifest
| Key | Value | Purpose |
|---|---|---|
| \`tracker_repo\` | \`airflow-s/airflow-s\` | Private security tracker |
| \`upstream_repo\` | \`apache/airflow\` | Public codebase where fixes land |
`;
      const parsed = parseProjectManifest(sample);
      assertStrictEqual(parsed.trackerRepo, 'airflow-s/airflow-s');
      assertStrictEqual(parsed.upstreamRepo, 'apache/airflow');
    });

    test('extracts tracker_repo and upstream_repo from yaml format', () => {
      const sample = `
tracker_repo: kafka-s/kafka-s
upstream_repo: apache/kafka
`;
      const parsed = parseProjectManifest(sample);
      assertStrictEqual(parsed.trackerRepo, 'kafka-s/kafka-s');
      assertStrictEqual(parsed.upstreamRepo, 'apache/kafka');
    });

    test('ignores TODO placeholders in project.md template', () => {
      const sample = `
| tracker_repo | TODO: e.g. foo-s/foo-s |
| upstream_repo | TODO: e.g. apache/foo |
`;
      const parsed = parseProjectManifest(sample);
      assertStrictEqual(parsed.trackerRepo, undefined);
      assertStrictEqual(parsed.upstreamRepo, undefined);
    });

    test('ignores "not used" descriptions and extracts clean slugs with annotations', () => {
      const sample = `
| tracker_repo | not used — Apache Magpie has no private security tracker; reports follow the ASF default process via security@apache.org |
| upstream_repo | apache/magpie (derived from the upstream git remote) |
`;
      const parsed = parseProjectManifest(sample);
      assertStrictEqual(parsed.trackerRepo, undefined);
      assertStrictEqual(parsed.upstreamRepo, 'apache/magpie');
    });

    test('resolveProjectConfig probes in precedence order', async () => {
      const mockFiles: Record<string, string> = {
        '.apache-magpie-overrides/project.md': '| tracker_repo | overrides-s/tracker |\n| upstream_repo | apache/overrides |',
      };

      const resolved = await resolveProjectConfig(async (p) => mockFiles[p]);
      assertStrictEqual(resolved.trackerRepo, 'overrides-s/tracker');
      assertStrictEqual(resolved.upstreamRepo, 'apache/overrides');
      assertStrictEqual(resolved.isTrackerCheckout, true);
    });
  });

  describe('splitShellCommands', () => {
    test('splits on semicolons, conditional operators, pipes, and newlines', () => {
      const raw = 'git status; git commit -m "Clean"\ngh pr create -t "Title" && git tag v1.0 || exit 1';
      const parts = splitShellCommands(raw);
      assertDeepStrictEqual(parts, [
        'git status',
        'git commit -m "Clean"',
        'gh pr create -t "Title"',
        'git tag v1.0',
        'exit 1',
      ]);
    });

    test('preserves semicolons and newlines inside quoted strings', () => {
      const raw = 'git commit -m "Header line; second part\nThird line" ; git push';
      const parts = splitShellCommands(raw);
      assertStrictEqual(parts.length, 2);
      assertStrictEqual(parts[0], 'git commit -m "Header line; second part\nThird line"');
      assertStrictEqual(parts[1], 'git push');
    });
  });

  describe('resolvePath', () => {
    test('resolves relative path against git -C directory without node:path', () => {
      assertStrictEqual(resolvePath('/path/to/upstream', 'msg.txt'), '/path/to/upstream/msg.txt');
      assertStrictEqual(resolvePath('/path/to/upstream/', 'msg.txt'), '/path/to/upstream/msg.txt');
      assertStrictEqual(resolvePath('/path/to/upstream', './msg.txt'), '/path/to/upstream/msg.txt');
      assertStrictEqual(resolvePath('/path/to/upstream', '"msg.txt"'), '/path/to/upstream/msg.txt');
      assertStrictEqual(resolvePath('/path/to/upstream', '/abs/msg.txt'), '/abs/msg.txt');
      assertStrictEqual(resolvePath(undefined, 'msg.txt'), 'msg.txt');
    });
  });

  describe('parseSubcommand', () => {
    test('identifies git commit with -m and combined flags', () => {
      const parsed = parseSubcommand('git commit -m "Fix asset graph view"');
      assertStrictEqual(parsed.isPublicSurfaceCommand, true);
      assertStrictEqual(parsed.commandType, 'git commit');
      assertDeepStrictEqual(parsed.extractedTexts, ['Fix asset graph view']);

      const am = parseSubcommand('git commit -am "Fix view"');
      assertDeepStrictEqual(am.extractedTexts, ['Fix view']);

      const sam = parseSubcommand('git commit -sam "Signed and added"');
      assertDeepStrictEqual(sam.extractedTexts, ['Signed and added']);
    });

    test('identifies attached short options without whitespace (-m"...", -m\'...\', -mval, -Fpath)', () => {
      const attachedM = parseSubcommand('git commit -m"Fix view"');
      assertDeepStrictEqual(attachedM.extractedTexts, ['Fix view']);

      const attachedSingleM = parseSubcommand("git commit -m'Fix view'");
      assertDeepStrictEqual(attachedSingleM.extractedTexts, ['Fix view']);

      const attachedBareM = parseSubcommand('git commit -mFixView');
      assertDeepStrictEqual(attachedBareM.extractedTexts, ['FixView']);

      const attachedF = parseSubcommand('git commit -Fmsg.txt');
      assertDeepStrictEqual(attachedF.referencedFiles, ['msg.txt']);

      const attachedT = parseSubcommand('gh pr create -t"Title" -b"Body"');
      assert(attachedT.extractedTexts.includes('Title'));
      assert(attachedT.extractedTexts.includes('Body'));
    });

    test('identifies git tag with annotated message or file', () => {
      const tagM = parseSubcommand('git tag -a v1.0.0 -m "Release v1.0.0"');
      assertStrictEqual(tagM.isPublicSurfaceCommand, true);
      assertStrictEqual(tagM.commandType, 'git tag');
      assertDeepStrictEqual(tagM.extractedTexts, ['Release v1.0.0']);

      const tagF = parseSubcommand('git tag -F tag-notes.txt v1.0.0');
      assertStrictEqual(tagF.isPublicSurfaceCommand, true);
      assertDeepStrictEqual(tagF.referencedFiles, ['tag-notes.txt']);

      // Lightweight tag without message is not a public surface publishing command
      const bareTag = parseSubcommand('git tag v1.0.0');
      assertStrictEqual(bareTag.isPublicSurfaceCommand, false);
    });

    test('identifies gh pr edit and gh pr review', () => {
      const edit = parseSubcommand('gh pr edit 123 --title "New Title" --body "New Body"');
      assertStrictEqual(edit.isPublicSurfaceCommand, true);
      assertStrictEqual(edit.commandType, 'gh pr edit');
      assert(edit.extractedTexts.includes('New Title'));
      assert(edit.extractedTexts.includes('New Body'));

      const review = parseSubcommand('gh pr review 123 --body "Approved changes"');
      assertStrictEqual(review.isPublicSurfaceCommand, true);
      assertStrictEqual(review.commandType, 'gh pr review');
      assertDeepStrictEqual(review.extractedTexts, ['Approved changes']);
    });

    test('identifies gh issue comment', () => {
      const comment = parseSubcommand('gh issue comment 456 --body "Under investigation"');
      assertStrictEqual(comment.isPublicSurfaceCommand, true);
      assertStrictEqual(comment.commandType, 'gh pr comment');
      assertDeepStrictEqual(comment.extractedTexts, ['Under investigation']);
    });

    test('identifies gh api comment creation with -f body=... and quoted key-value pairs', () => {
      const apiCmd = parseSubcommand('gh api repos/apache/airflow/issues/1/comments -f body="Fixed problem"');
      assertStrictEqual(apiCmd.isPublicSurfaceCommand, true);
      assertStrictEqual(apiCmd.commandType, 'gh api');
      assertStrictEqual(apiCmd.targetRepo, 'apache/airflow');
      assertDeepStrictEqual(apiCmd.extractedTexts, ['Fixed problem']);

      const apiQuotedPair = parseSubcommand('gh api repos/apache/airflow/issues/1/comments -f "body=Fixed problem"');
      assertDeepStrictEqual(apiQuotedPair.extractedTexts, ['Fixed problem']);

      const apiField = parseSubcommand('gh api repos/apache/airflow/issues/1/comments --field "body=Fixed problem"');
      assertDeepStrictEqual(apiField.extractedTexts, ['Fixed problem']);

      const apiRawField = parseSubcommand("gh api repos/apache/airflow/issues/1/comments --raw-field 'body=Fixed problem'");
      assertDeepStrictEqual(apiRawField.extractedTexts, ['Fixed problem']);
    });

    test('extracts git -C directory and -R target repo', () => {
      const parsed = parseSubcommand('git -C /home/repo commit -m "Fix"');
      assertStrictEqual(parsed.gitCwd, '/home/repo');

      const ghParsed = parseSubcommand('gh pr create -R apache/airflow -t "T" -b "B"');
      assertStrictEqual(ghParsed.targetRepo, 'apache/airflow');
    });

    test('detects dynamic inputs (heredoc, command substitution, variables, stdin pipe)', () => {
      assertStrictEqual(parseSubcommand("git commit -F - << 'EOF'\nEOF").hasDynamicInput, true);
      assertStrictEqual(parseSubcommand('git commit -m "$(cat msg.txt)"').hasDynamicInput, true);
      assertStrictEqual(parseSubcommand('git commit -m "`echo test`"').hasDynamicInput, true);
      assertStrictEqual(parseSubcommand('git commit -m "$COMMIT_MSG"').hasDynamicInput, true);
      assertStrictEqual(parseSubcommand('git commit -F -').hasDynamicInput, true);
    });
  });

  describe('evaluatePublicSurfaceCommand', () => {
    const defaultProject = {
      trackerRepo: 'airflow-s/airflow-s',
      upstreamRepo: 'apache/airflow',
    };

    test('allows clean neutral commit', async () => {
      const res = await evaluatePublicSurfaceCommand('git commit -m "Fix asset graph view"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, false);
      assertDeepStrictEqual(res.matchedTerms, []);
    });

    test('blocks git commit containing CVE reference', async () => {
      const res = await evaluatePublicSurfaceCommand('git commit -m "Fix CVE-2026-1234 in webserver"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE reference'));
      assert(res.reason?.includes('Apache Magpie Security Guard'));
      assert(res.reason?.includes('Confidentiality Rule'));
    });

    test('blocks git commit with attached -m"..." (no whitespace)', async () => {
      const res = await evaluatePublicSurfaceCommand('git commit -m"Fix CVE-2026-5555"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE reference'));
    });

    test('blocks git commit with attached -am"..." flag', async () => {
      const res = await evaluatePublicSurfaceCommand('git commit -am"Prevent critical SSRF bug"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('SSRF'));
    });

    test('blocks git tag with forbidden terms in annotated message', async () => {
      const res = await evaluatePublicSurfaceCommand('git tag -a v1.0.0 -m "Release with CVE-2026-1111 fix"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE reference'));
    });

    test('blocks gh pr edit containing forbidden terms', async () => {
      const res = await evaluatePublicSurfaceCommand('gh pr edit 50 -R apache/airflow --title "Fix CVE-2026-9999"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE reference'));
    });

    test('blocks gh pr review containing forbidden terms', async () => {
      const res = await evaluatePublicSurfaceCommand('gh pr review 50 -R apache/airflow --body "Looks good, fixes the SSRF"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('SSRF'));
    });

    test('blocks gh issue comment containing forbidden terms', async () => {
      const res = await evaluatePublicSurfaceCommand('gh issue comment 50 -R apache/airflow -b "Confirmed auth-bypass vulnerability"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('auth bypass'));
      assert(res.matchedTerms.includes('vulnerability'));
    });

    test('blocks gh api comment creation with forbidden terms', async () => {
      const res = await evaluatePublicSurfaceCommand('gh api repos/apache/airflow/issues/1/comments -f body="Fixed CVE-2026-1000"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE reference'));
    });

    test('per-subcommand isolation: blocks leaking subcommand even if previous targets tracker', async () => {
      const multiCmd = 'gh pr view 1 -R airflow-s/airflow-s; gh pr comment 2 -R apache/airflow -b "Fixes CVE-2026-9999 SSRF"';
      const res = await evaluatePublicSurfaceCommand(multiCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE reference'));
      assert(res.matchedTerms.includes('SSRF'));
    });

    test('newline separation: detects command separated by newline', async () => {
      const newlineCmd = 'git status\ngit commit -m "Fix CVE-2026-1234 SSRF"';
      const res = await evaluatePublicSurfaceCommand(newlineCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE reference'));
    });

    test('multi-command sequence: git commit clean && gh pr create leaking', async () => {
      const seqCmd = 'git commit -m "Neutral message" && gh pr create -R apache/airflow -t "Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(seqCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE reference'));
    });

    test('fails closed if referenced message file cannot be read', async () => {
      const res = await evaluatePublicSurfaceCommand('git commit -F missing.txt', {
        projectConfig: defaultProject,
        readFile: async () => null,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.reason?.includes('Referenced message file cannot be read') || res.reason?.includes('could not be read'));
      assert(res.reason?.includes('missing.txt'));
    });

    test('resolves file path relative to git -C directory', async () => {
      const mockFiles: Record<string, string> = {
        '/upstream/msg.txt': 'Neutral headline\n\nFixes critical SSRF vulnerability.',
      };
      const res = await evaluatePublicSurfaceCommand('git -C /upstream commit -F msg.txt', {
        projectConfig: defaultProject,
        readFile: async (p) => mockFiles[p],
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('SSRF'));
      assert(res.matchedTerms.includes('vulnerability'));
    });

    test('blocks dynamic input pipelines when forbidden terms appear in command line', async () => {
      const pipeCmd = 'echo "Fixes critical SSRF vulnerability" | gh pr create -R apache/airflow -t "Fix" --body-file -';
      const res = await evaluatePublicSurfaceCommand(pipeCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('SSRF'));
    });

    test('fails closed on indeterminate dynamic inputs (variables, command substitution, stdin, --fill)', async () => {
      // Variable in commit message
      const varCmd = await evaluatePublicSurfaceCommand('git commit -m "$COMMIT_MSG"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(varCmd.blocked, true);
      assert(varCmd.matchedTerms.includes('dynamic input'));
      assert(varCmd.reason?.includes('indeterminate dynamic input'));

      // Command substitution
      const subCmd = await evaluatePublicSurfaceCommand('git commit -m "$(cat /tmp/msg.txt)"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(subCmd.blocked, true);
      assert(subCmd.matchedTerms.includes('dynamic input'));

      // Piped stdin
      const stdinCmd = await evaluatePublicSurfaceCommand('cat msg.txt | git commit -F -', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(stdinCmd.blocked, true);
      assert(stdinCmd.matchedTerms.includes('dynamic input'));

      // gh pr create --fill
      const fillCmd = await evaluatePublicSurfaceCommand('gh pr create -R apache/airflow --fill', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(fillCmd.blocked, true);
      assert(fillCmd.matchedTerms.includes('dynamic input'));
    });

    test('handles git commit --amend: blocks indeterminate reuse; allows clean explicit message', async () => {
      // Amend without message flag reuses unverified prior commit -> blocked
      const bareAmend = await evaluatePublicSurfaceCommand('git commit --amend', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(bareAmend.blocked, true);
      assert(bareAmend.matchedTerms.includes('dynamic input'));

      const noEditAmend = await evaluatePublicSurfaceCommand('git commit --amend --no-edit', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(noEditAmend.blocked, true);
      assert(noEditAmend.matchedTerms.includes('dynamic input'));

      // Amend with explicit clean message -> allowed
      const cleanAmend = await evaluatePublicSurfaceCommand('git commit --amend -m "Update asset graph view"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(cleanAmend.blocked, false);

      // Amend with explicit leaking message -> blocked on terms
      const leakingAmend = await evaluatePublicSurfaceCommand('git commit --amend -m "Fix CVE-2026-9999 SSRF"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(leakingAmend.blocked, true);
      assert(leakingAmend.matchedTerms.includes('CVE reference'));
      assert(leakingAmend.matchedTerms.includes('SSRF'));
    });

    test('allows commands explicitly targeting the private security tracker', async () => {
      const trackerCmd = 'gh pr comment 45 -R airflow-s/airflow-s -b "Confirmed SSRF fix for CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(trackerCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, false);
    });

    test('allows commands targeting other repositories (adopter docs, framework, etc.) and scopes strictly to upstream_repo', async () => {
      // Adopter docs repo is not upstreamRepo -> passes unchecked
      const docsRepoCmd = 'gh pr comment 45 -R apache/airflow-site -b "Update CVE-2026-1234 advisory docs"';
      const docsRes = await evaluatePublicSurfaceCommand(docsRepoCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(docsRes.blocked, false);

      // Framework repo is not upstreamRepo -> passes unchecked
      const frameworkCmd = 'gh pr comment 1 -R apache/magpie -b "fix(generate-cve-json): CVE parser"';
      const frameworkRes = await evaluatePublicSurfaceCommand(frameworkCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(frameworkRes.blocked, false);

      // Upstream repo is strictly blocked
      const upstreamCmd = 'gh pr comment 45 -R apache/airflow -b "Fix CVE-2026-1234"';
      const upstreamRes = await evaluatePublicSurfaceCommand(upstreamCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(upstreamRes.blocked, true);
      assert(upstreamRes.matchedTerms.includes('CVE reference'));

      // If upstream_repo happens to contain 'private' or end in '-s', it does NOT fail open on naming
      const upstreamWithPrivate = 'gh pr comment 45 -R myorg/foo-private -b "Fix SSRF"';
      const resPrivate = await evaluatePublicSurfaceCommand(upstreamWithPrivate, {
        projectConfig: { trackerRepo: 'other-s/other-s', upstreamRepo: 'myorg/foo-private' },
      });
      assertStrictEqual(resPrivate.blocked, true);
      assert(resPrivate.matchedTerms.includes('SSRF'));

      // Custom tracker repo not ending in '-s' is properly exempt
      const customTrackerCmd = 'gh pr comment 1 -R apache/foo-security -b "Investigating CVE-2026-9999"';
      const customTrackerRes = await evaluatePublicSurfaceCommand(customTrackerCmd, {
        projectConfig: { trackerRepo: 'apache/foo-security', upstreamRepo: 'apache/foo' },
      });
      assertStrictEqual(customTrackerRes.blocked, false);

      // When upstreamRepo is unconfigured or is the framework repo itself (apache/magpie), ordinary commits pass
      const unconfiguredRes = await evaluatePublicSurfaceCommand('git commit -m "fix(generate-cve-json): handle CVE fields"', {
        projectConfig: {},
      });
      assertStrictEqual(unconfiguredRes.blocked, false);

      const magpieRepoRes = await evaluatePublicSurfaceCommand('git commit -m "fix(generate-cve-json): validate CVE schema"', {
        projectConfig: { upstreamRepo: 'apache/magpie' },
      });
      assertStrictEqual(magpieRepoRes.blocked, false);

      const magpiePrRes = await evaluatePublicSurfaceCommand('gh pr create -R apache/magpie -t "fix(generate-cve-json): fix vulnerability test"', {
        projectConfig: { upstreamRepo: 'apache/magpie' },
      });
      assertStrictEqual(magpiePrRes.blocked, false);

      // git -C in unrelated repo passes; git -C in upstream repo blocks
      const unrelatedGitCwd = await evaluatePublicSurfaceCommand('git -C /home/user/magpie commit -m "fix: CVE test"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(unrelatedGitCwd.blocked, false);

      const upstreamGitCwd = await evaluatePublicSurfaceCommand('git -C /home/user/airflow commit -m "fix: CVE-2026-1234"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(upstreamGitCwd.blocked, true);
    });

    test('escape hatch: cannot be bypassed from command-line injection', async () => {
      const cmdWithInlineEnv = 'MAGPIE_ALLOW_EMBARGO_TERMS=1 git commit -m "CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmdWithInlineEnv, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE reference'));

      const cmdWithFlag = 'git commit -m "CVE-2026-1234 --allow-embargo-terms"';
      const res2 = await evaluatePublicSurfaceCommand(cmdWithFlag, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res2.blocked, true);
      assert(res2.matchedTerms.includes('CVE reference'));
    });

    test('escape hatch: honored ONLY when set in environment by human', async () => {
      const cmd = 'git commit -m "Backport CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: defaultProject,
        env: { MAGPIE_ALLOW_EMBARGO_TERMS: '1' },
      });
      assertStrictEqual(res.blocked, false);
    });

    test('blocking reason does NOT instruct agent how to bypass; tells to ask maintainer', async () => {
      const res = await evaluatePublicSurfaceCommand('git commit -m "Fix CVE-2026-1234"', {
        projectConfig: defaultProject,
      });
      assert(res.reason?.includes('consult an Apache Magpie security-team maintainer to review and set the environment bypass'));
      assert(!res.reason?.includes('MAGPIE_ALLOW_EMBARGO_TERMS'));
      assert(!res.reason?.includes('--allow-embargo-terms'));
    });
  });

  describe('Claude Code hook integration (register)', () => {
    test('allows clean Bash tool call through via next()', async () => {
      let registeredHook: any = null;
      const on = (event: string, handler: any) => {
        if (event === 'tool.call') {
          registeredHook = handler;
        }
      };

      register(on);
      assert(registeredHook, 'tool.call hook must be registered');

      let nextCalled = false;
      const mockEvent = { tool: 'Bash', input: { command: 'git commit -m "Fix asset graph view"' } };
      const next = (e: any) => {
        nextCalled = true;
        return { success: true, event: e };
      };

      const result = await registeredHook({ fs: { read: async () => '' } }, mockEvent, next);
      assertStrictEqual(nextCalled, true);
      assertStrictEqual(result.success, true);
    });

    test('intercepts and blocks leaking Bash tool call returning error', async () => {
      let registeredHook: any = null;
      const on = (event: string, handler: any) => {
        if (event === 'tool.call') {
          registeredHook = handler;
        }
      };

      register(on);

      const mockProject = `
| Key | Value |
| tracker_repo | airflow-s/airflow-s |
| upstream_repo | apache/airflow |
`;

      let nextCalled = false;
      const mockEvent = {
        tool: 'Bash',
        input: { command: 'gh pr create -R apache/airflow -t "Fix CVE-2026-1111: SSRF vulnerability"' },
      };
      const next = () => {
        nextCalled = true;
      };

      const result = await registeredHook({ fs: { read: async () => mockProject } }, mockEvent, next);
      assertStrictEqual(nextCalled, false, 'next() must NOT be called on blocked commands');
      assert(result.error, 'Error explanation must be returned');
      assert(result.error.includes('Apache Magpie Security Guard'));
      assert(result.error.includes('CVE reference'));
      assert(result.error.includes('SSRF'));
    });

    test('allows Bash tool call when upstream_repo is not configured (e.g. magpie repo)', async () => {
      let registeredHook: any = null;
      const on = (event: string, handler: any) => {
        if (event === 'tool.call') {
          registeredHook = handler;
        }
      };

      register(on);

      let nextCalled = false;
      const mockEvent = {
        tool: 'Bash',
        input: { command: 'git commit -m "fix(generate-cve-json): handle CVE fields"' },
      };
      const next = (e: any) => {
        nextCalled = true;
        return { forwarded: e };
      };

      const result = await registeredHook({ fs: { read: async () => '' } }, mockEvent, next);
      assertStrictEqual(nextCalled, true, 'next() must be called when upstream_repo is not configured');
      assertStrictEqual(result.forwarded.input.command, 'git commit -m "fix(generate-cve-json): handle CVE fields"');
    });

    test('passes non-Bash tools through to next() unchanged', async () => {
      let registeredHook: any = null;
      const on = (event: string, handler: any) => {
        if (event === 'tool.call') {
          registeredHook = handler;
        }
      };

      register(on);

      let nextCalled = false;
      const mockEvent = { tool: 'ReadUrl', input: { url: 'https://cve.org/CVE-2026-1234' } };
      const next = (e: any) => {
        nextCalled = true;
        return { forwarded: e };
      };

      const result = await registeredHook({ fs: { read: async () => '' } }, mockEvent, next);
      assertStrictEqual(nextCalled, true);
      assertStrictEqual(result.forwarded.tool, 'ReadUrl');
    });
  });
});
