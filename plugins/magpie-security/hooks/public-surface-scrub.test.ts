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
  inspectDirectoryRemote,
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
      assert(hits.includes('CVE id'));
      const bareHits = findForbiddenTerms('Address issue reported as cve');
      assert(bareHits.includes('CVE'));
    });

    test('detects vulnerability and security fix keywords (spaced and hyphenated)', () => {
      assert(findForbiddenTerms('Fix critical vulnerability in parsing logic').includes('vulnerability'));
      assert(findForbiddenTerms('close vulnerability').includes('vulnerability'));
      assert(findForbiddenTerms('Security fix for webserver endpoints').includes('security fix'));
      assert(findForbiddenTerms('Apply security-fix for session timeout').includes('security fix'));
      assert(findForbiddenTerms('security advisory draft').includes('advisory'));
      assert(findForbiddenTerms('Security advisory update').includes('advisory'));
      assert(findForbiddenTerms('Contact security@apache.org for details').includes('security@'));
    });

    test('detects vulnerability classes with whitespace and hyphens', () => {
      assert(findForbiddenTerms('Prevent SSRF in HTTP provider').includes('SSRF'));
      assert(findForbiddenTerms('fix: SSRF').includes('SSRF'));
      assert(findForbiddenTerms('Mitigate stored XSS in log view').includes('XSS'));
      assert(findForbiddenTerms('Add CSRF token validation').includes('CSRF'));
      assert(findForbiddenTerms('Prevent SQL injection in search filter').includes('SQL injection'));
      assert(findForbiddenTerms('Mitigate SQL-injection in query filter').includes('SQL injection'));
      assert(findForbiddenTerms('Fix path traversal in file download').includes('path traversal'));
      assert(findForbiddenTerms('Prevent path-traversal in file handler').includes('path traversal'));
      assert(findForbiddenTerms('Prevent remote code execution in worker').includes('remote code execution'));
      assert(findForbiddenTerms('Close RCE vector in serializer').includes('RCE'));
      assert(findForbiddenTerms('Fix remote-code-execution vulnerability').includes('remote code execution'));
      assert(findForbiddenTerms('fix: Remote-Code-Execution bug').includes('remote code execution'));
      assert(findForbiddenTerms('Fix privilege escalation in role mapper').includes('privilege escalation'));
      assert(findForbiddenTerms('Prevent privilege-escalation bug').includes('privilege escalation'));
      assert(findForbiddenTerms('Fix auth bypass in REST API').includes('auth bypass'));
      assert(findForbiddenTerms('Mitigate auth-bypass vulnerability').includes('auth bypass'));
      assert(findForbiddenTerms('auth_bypass').includes('auth bypass'));
      assert(findForbiddenTerms('Buffer overflow in memory reader').includes('buffer overflow'));
      assert(findForbiddenTerms('Use-after-free in parser loop').includes('use-after-free'));
    });

    test('returns multiple matched terms uniquely', () => {
      const terms = findForbiddenTerms('Fix CVE-2026-9999: critical SSRF vulnerability allowing auth-bypass');
      assert(terms.includes('CVE id'));
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

    test('resolveProjectConfig probes in precedence order and sets isTrackerCheckout false for parent dirs', async () => {
      const mockFiles: Record<string, string> = {
        '.apache-magpie-overrides/project.md': '| tracker_repo | overrides-s/tracker |\n| upstream_repo | apache/overrides |',
      };

      const resolved = await resolveProjectConfig(async (p) => mockFiles[p]);
      assertStrictEqual(resolved.trackerRepo, 'overrides-s/tracker');
      assertStrictEqual(resolved.upstreamRepo, 'apache/overrides');
      assertStrictEqual(resolved.isTrackerCheckout, true);

      // Probing via parent/sibling directory (../) must NOT mark current checkout as tracker
      const siblingFiles: Record<string, string> = {
        '../.apache-magpie-local/project.md': '| tracker_repo | tracker-s/tracker-s |\n| upstream_repo | apache/upstream |',
      };
      const siblingResolved = await resolveProjectConfig(async (p) => siblingFiles[p]);
      assertStrictEqual(siblingResolved.trackerRepo, 'tracker-s/tracker-s');
      assertStrictEqual(siblingResolved.isTrackerCheckout, false);
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
      assert(tagM.extractedTexts.includes('v1.0.0'));
      assert(tagM.extractedTexts.includes('Release v1.0.0'));

      const tagF = parseSubcommand('git tag -F tag-notes.txt v1.0.0');
      assertStrictEqual(tagF.isPublicSurfaceCommand, true);
      assert(tagF.extractedTexts.includes('v1.0.0'));
      assertDeepStrictEqual(tagF.referencedFiles, ['tag-notes.txt']);

      // Lightweight tag creation scans the tag name for forbidden disclosure terms
      const bareTag = parseSubcommand('git tag v1.0.0');
      assertStrictEqual(bareTag.isPublicSurfaceCommand, true);
      assertDeepStrictEqual(bareTag.extractedTexts, ['v1.0.0']);
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
      assertStrictEqual(comment.commandType, 'gh issue comment');
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

    test('detects dynamic inputs (heredoc, command substitution, variables, stdin pipe, process substitution)', () => {
      assertStrictEqual(parseSubcommand("git commit -F - << 'EOF'\nEOF").hasDynamicInput, true);
      assertStrictEqual(parseSubcommand('git commit -m "$(cat msg.txt)"').hasDynamicInput, true);
      assertStrictEqual(parseSubcommand('git commit -m "`echo test`"').hasDynamicInput, true);
      assertStrictEqual(parseSubcommand('git commit -m "$COMMIT_MSG"').hasDynamicInput, true);
      assertStrictEqual(parseSubcommand('git commit -F -').hasDynamicInput, true);
      assertStrictEqual(parseSubcommand('git commit -F <(echo test)').hasDynamicInput, true);
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
      assert(res.matchedTerms.includes('CVE id'));
      assert(res.reason?.includes('Apache Magpie Security Guard'));
      assert(res.reason?.includes('Confidentiality Rule'));
    });

    test('blocks git commit with attached -m"..." (no whitespace)', async () => {
      const res = await evaluatePublicSurfaceCommand('git commit -m"Fix CVE-2026-5555"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
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
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('blocks gh pr edit containing forbidden terms', async () => {
      const res = await evaluatePublicSurfaceCommand('gh pr edit 50 -R apache/airflow --title "Fix CVE-2026-9999"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
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
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('per-subcommand isolation: blocks leaking subcommand even if previous targets tracker', async () => {
      const multiCmd = 'gh pr view 1 -R airflow-s/airflow-s; gh pr comment 2 -R apache/airflow -b "Fixes CVE-2026-9999 SSRF"';
      const res = await evaluatePublicSurfaceCommand(multiCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
      assert(res.matchedTerms.includes('SSRF'));
    });

    test('newline separation: detects command separated by newline', async () => {
      const newlineCmd = 'git status\ngit commit -m "Fix CVE-2026-1234 SSRF"';
      const res = await evaluatePublicSurfaceCommand(newlineCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('multi-command sequence: git commit clean && gh pr create leaking', async () => {
      const seqCmd = 'git commit -m "Neutral message" && gh pr create -R apache/airflow -t "Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(seqCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
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

      // Process substitution <(...)
      const procSubCmd = await evaluatePublicSurfaceCommand('git commit -F <(echo test)', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(procSubCmd.blocked, true);
      assert(procSubCmd.matchedTerms.includes('dynamic input'));
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
      assert(leakingAmend.matchedTerms.includes('CVE id'));
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
      assertStrictEqual(docsRes.blocked, false, 'docsRes should not be blocked');

      // Framework repo is not upstreamRepo -> passes unchecked
      const frameworkCmd = 'gh pr comment 1 -R apache/magpie -b "fix(generate-cve-json): CVE parser"';
      const frameworkRes = await evaluatePublicSurfaceCommand(frameworkCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(frameworkRes.blocked, false, 'frameworkRes should not be blocked');

      // Upstream repo is strictly blocked
      const upstreamCmd = 'gh pr comment 45 -R apache/airflow -b "Fix CVE-2026-1234"';
      const upstreamRes = await evaluatePublicSurfaceCommand(upstreamCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(upstreamRes.blocked, true, 'upstreamRes should be blocked');
      assert(upstreamRes.matchedTerms.includes('CVE id'));

      // If upstream_repo happens to contain 'private' or end in '-s', it does NOT fail open on naming
      const upstreamWithPrivate = 'gh pr comment 45 -R myorg/foo-private -b "Fix SSRF"';
      const resPrivate = await evaluatePublicSurfaceCommand(upstreamWithPrivate, {
        projectConfig: { trackerRepo: 'other-s/other-s', upstreamRepo: 'myorg/foo-private' },
      });
      assertStrictEqual(resPrivate.blocked, true, 'resPrivate should be blocked');
      assert(resPrivate.matchedTerms.includes('SSRF'));

      // Custom tracker repo not ending in '-s' is properly exempt
      const customTrackerCmd = 'gh pr comment 1 -R apache/foo-security -b "Investigating CVE-2026-9999"';
      const customTrackerRes = await evaluatePublicSurfaceCommand(customTrackerCmd, {
        projectConfig: { trackerRepo: 'apache/foo-security', upstreamRepo: 'apache/foo' },
      });
      assertStrictEqual(customTrackerRes.blocked, false, 'customTrackerRes should not be blocked');

      // Clean commit in unconfigured repository passes
      const unconfiguredCleanRes = await evaluatePublicSurfaceCommand('git commit -m "refactor(json): handle schema validation"', {
        projectConfig: {},
      });
      assertStrictEqual(unconfiguredCleanRes.blocked, false, 'unconfiguredCleanRes should not be blocked');

      // Leaking commit in unconfigured repository fails closed
      const unconfiguredLeakingRes = await evaluatePublicSurfaceCommand('git commit -m "fix(generate-cve-json): validate CVE schema"', {
        projectConfig: {},
      });
      assertStrictEqual(unconfiguredLeakingRes.blocked, true, 'unconfiguredLeakingRes should be blocked');

      // Commands targeting non-upstream repos pass unchecked
      const magpiePrRes = await evaluatePublicSurfaceCommand('gh pr create -R apache/magpie -t "fix(generate-cve-json): fix vulnerability test"', {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
      });
      assertStrictEqual(magpiePrRes.blocked, false, 'magpiePrRes should not be blocked');

      // git -C in unrelated repo (verified via remote inspection) passes; git -C in upstream repo blocks
      const mockGitConfigs: Record<string, string> = {
        '/home/user/magpie/.git/config': '[remote "origin"]\nurl = https://github.com/apache/magpie.git\n',
        '/home/user/airflow/.git/config': '[remote "origin"]\nurl = https://github.com/apache/airflow.git\n',
      };
      const unrelatedGitCwd = await evaluatePublicSurfaceCommand('git -C /home/user/magpie commit -m "fix: CVE test"', {
        projectConfig: defaultProject,
        readFile: async (p) => mockGitConfigs[p],
      });
      assertStrictEqual(unrelatedGitCwd.blocked, false, 'unrelatedGitCwd should not be blocked');

      const upstreamGitCwd = await evaluatePublicSurfaceCommand('git -C /home/user/airflow commit -m "fix: CVE-2026-1234"', {
        projectConfig: defaultProject,
        readFile: async (p) => mockGitConfigs[p],
      });
      assertStrictEqual(upstreamGitCwd.blocked, true, 'upstreamGitCwd should be blocked');

      // Fork of upstream repo (e.g. contributor/airflow) MUST be blocked — cannot fail open!
      const forkGitConfigs: Record<string, string> = {
        '/home/user/fork/.git/config': '[remote "origin"]\nurl = https://github.com/contributor/airflow.git\n',
      };
      const forkGitCwd = await evaluatePublicSurfaceCommand('git -C /home/user/fork commit -m "Fix CVE-2026-1234 in fork"', {
        projectConfig: defaultProject,
        readFile: async (p) => forkGitConfigs[p],
      });
      assertStrictEqual(forkGitCwd.blocked, true, 'forkGitCwd should be blocked');
      assert(forkGitCwd.matchedTerms.includes('CVE id'));

      // PR creation targeting a fork of upstream MUST be blocked
      const forkPrRes = await evaluatePublicSurfaceCommand('gh pr create -R contributor/airflow -t "Fix CVE-2026-1234"', {
        projectConfig: defaultProject,
      });
      assertStrictEqual(forkPrRes.blocked, true, 'forkPrRes should be blocked');
      assert(forkPrRes.matchedTerms.includes('CVE id'));

      // Git worktree with .git file pointing to gitdir: ... must be inspected and blocked if upstream
      const worktreeConfigs: Record<string, string> = {
        '/home/user/worktree/.git': 'gitdir: /home/user/main-repo/.git/worktrees/fix-branch\n',
        '/home/user/main-repo/.git/worktrees/fix-branch/config': '[remote "origin"]\nurl = https://github.com/apache/airflow.git\n',
      };
      const worktreeRes = await evaluatePublicSurfaceCommand('git -C /home/user/worktree commit -m "Fix CVE-2026-1234"', {
        projectConfig: defaultProject,
        readFile: async (p) => worktreeConfigs[p],
      });
      assertStrictEqual(worktreeRes.blocked, true, 'worktreeRes should be blocked');
      assert(worktreeRes.matchedTerms.includes('CVE id'));
    });

    test('tracks cd across sub-commands and blocks upstream leaks', async () => {
      const mockGitConfigs: Record<string, string> = {
        '/workspace/upstream/.git/config': '[remote "origin"]\nurl = https://github.com/apache/airflow.git\n',
      };
      const chainedCdCmd = 'cd /workspace/upstream && git commit -m "Fix CVE-2026-9999"';
      const res = await evaluatePublicSurfaceCommand(chainedCdCmd, {
        projectConfig: defaultProject,
        readFile: async (p) => mockGitConfigs[p],
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('git -c config option does not collide with -C directory option', async () => {
      const configCmd = 'git -c user.name=bot commit -m "Neutral message"';
      const res = await evaluatePublicSurfaceCommand(configCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, false);
    });

    test('handles escaped quotes in commit messages', async () => {
      const escapedQuoteCmd = 'git commit -m "Refactor \\"parser\\" for CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(escapedQuoteCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('--repo inside a body cannot forge tracker exemption', async () => {
      const fakeRepoBody = 'gh pr create -R apache/airflow -b "--repo airflow-s/airflow-s" -t "Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(fakeRepoBody, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('dynamic input fail-closed reason mentions -F <file> guidance', async () => {
      const dynamicCmd = 'git commit -m "$(cat /tmp/msg.txt)"';
      const res = await evaluatePublicSurfaceCommand(dynamicCmd, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.reason?.includes('-F <file>'));
    });

    test('escape hatch: cannot be bypassed from command-line injection', async () => {
      const cmdWithInlineEnv = 'MAGPIE_ALLOW_EMBARGO_TERMS=1 git commit -m "CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmdWithInlineEnv, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));

      const cmdWithFlag = 'git commit -m "CVE-2026-1234 --allow-embargo-terms"';
      const res2 = await evaluatePublicSurfaceCommand(cmdWithFlag, {
        projectConfig: defaultProject,
      });
      assertStrictEqual(res2.blocked, true);
      assert(res2.matchedTerms.includes('CVE id'));
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

  describe('CLI parser & scoping enhancements (PR #1676 review #3)', () => {
    test('extracts target repo from PR and issue URLs', async () => {
      const mockProject = `
| Key | Value |
| tracker_repo | airflow-s/airflow-s |
| upstream_repo | apache/airflow |
`;
      const res1 = await evaluatePublicSurfaceCommand(
        'gh pr comment https://github.com/apache/airflow/pull/1 -b "Fix CVE-2026-1234 SSRF"',
        { readFile: async () => mockProject }
      );
      assertStrictEqual(res1.blocked, true);
      assert(res1.reason?.includes('CVE id'));

      const res2 = await evaluatePublicSurfaceCommand(
        'gh pr edit https://github.com/apache/airflow/pull/1 --body "Fix CVE-2026-1234 SSRF"',
        { readFile: async () => mockProject }
      );
      assertStrictEqual(res2.blocked, true);
    });

    test('extracts target repo from leading GH_REPO= environment variable', async () => {
      const mockProject = `
| Key | Value |
| tracker_repo | airflow-s/airflow-s |
| upstream_repo | apache/airflow |
`;
      const res = await evaluatePublicSurfaceCommand(
        'GH_REPO=apache/airflow gh pr comment 1 -b "Fix CVE-2026-1234 SSRF"',
        { readFile: async () => mockProject }
      );
      assertStrictEqual(res.blocked, true);
      assert(res.reason?.includes('SSRF'));
    });

    test('inspects referenced file in gh pr review --body-file', async () => {
      const mockProject = `
| Key | Value |
| tracker_repo | airflow-s/airflow-s |
| upstream_repo | apache/airflow |
`;
      const res = await evaluatePublicSurfaceCommand(
        'gh pr review 1 -R apache/airflow --comment --body-file /path/to/review.md',
        {
          readFile: async (p: string) => {
            if (p.includes('project.md')) return mockProject;
            if (p.includes('review.md')) return 'Patch addresses CVE-2026-9999';
            return null;
          },
        }
      );
      assertStrictEqual(res.blocked, true);
      assert(res.reason?.includes('CVE id'));
    });

    test('inspects gh api --input and -F body=@file', async () => {
      const mockProject = `
| Key | Value |
| tracker_repo | airflow-s/airflow-s |
| upstream_repo | apache/airflow |
`;
      const resInput = await evaluatePublicSurfaceCommand(
        'gh api repos/apache/airflow/issues/1/comments --input /path/to/payload.json',
        {
          readFile: async (p: string) => {
            if (p.includes('project.md')) return mockProject;
            if (p.includes('payload.json')) return '{"body": "Fix CVE-2026-1234 SSRF"}';
            return null;
          },
        }
      );
      assertStrictEqual(resInput.blocked, true);

      const resAtFile = await evaluatePublicSurfaceCommand(
        'gh api repos/apache/airflow/issues/1/comments -F body=@msg.md',
        {
          readFile: async (p: string) => {
            if (p.includes('project.md')) return mockProject;
            if (p.includes('msg.md')) return 'Fix CVE-2026-1234 SSRF';
            return null;
          },
        }
      );
      assertStrictEqual(resAtFile.blocked, true);
    });

    test('inspects gh api graphql mutation for forbidden terms', async () => {
      const mockProject = `
| Key | Value |
| tracker_repo | airflow-s/airflow-s |
| upstream_repo | apache/airflow |
`;
      const res = await evaluatePublicSurfaceCommand(
        'gh api graphql -f query="mutation{addComment(input:{body:\\\"CVE-2026-1234 SSRF\\\"})}"',
        { readFile: async () => mockProject }
      );
      assertStrictEqual(res.blocked, true);
    });

    test('splits subcommands on single & separator', async () => {
      const mockProject = `
| Key | Value |
| tracker_repo | airflow-s/airflow-s |
| upstream_repo | apache/airflow |
`;
      const res = await evaluatePublicSurfaceCommand(
        'git -C ../airflow status & git -C ../airflow commit -m "Fix CVE-2026-1234 SSRF"',
        { readFile: async () => mockProject }
      );
      assertStrictEqual(res.blocked, true);
    });

    test('allows literal single-quoted $VAR like -m \'costs $HOME\'', async () => {
      const mockProject = `
| Key | Value |
| tracker_repo | airflow-s/airflow-s |
| upstream_repo | apache/airflow |
`;
      const res = await evaluatePublicSurfaceCommand(
        "git commit -m 'costs $HOME'",
        { readFile: async () => mockProject }
      );
      assertStrictEqual(res.blocked, false);
    });

    test('allows commands in unrelated repository without Magpie config when remote is determined and message is neutral', async () => {
      const gitConfig = `
[remote "origin"]
  url = https://github.com/third-party/utility-lib.git
`;
      // When upstreamRepo is unknown, unconfigured repos fall through to term scan (Blocking #2 fix).
      // Neutral commits pass:
      const res = await evaluatePublicSurfaceCommand(
        'git commit -m "fix(generate-json): tidy"',
        {
          readFile: async (p: string) => {
            if (p.includes('.git/config')) return gitConfig;
            return null;
          },
        }
      );
      assertStrictEqual(res.blocked, false);

      // Verified non-upstream remote (when upstreamRepo is configured) exempts even terms like cve:
      const verifiedRes = await evaluatePublicSurfaceCommand(
        'git commit -m "fix(generate-cve-json): tidy"',
        {
          projectConfig: {
            trackerRepo: 'apache/magpie-tracker',
            upstreamRepo: 'apache/airflow',
          },
          readFile: async (p: string) => {
            if (p.includes('.git/config')) return gitConfig;
            return null;
          },
        }
      );
      assertStrictEqual(verifiedRes.blocked, false);
    });
  });

  describe('Claude Code hook integration (register)', () => {
    test('registers hook with Bash tool filter and allows clean command', async () => {
      let registeredFilter: any = null;
      let registeredHook: any = null;
      const on = (event: string, filterOrHandler: any, handler?: any) => {
        if (event === 'tool.call') {
          if (typeof filterOrHandler === 'function') {
            registeredHook = filterOrHandler;
          } else {
            registeredFilter = filterOrHandler;
            registeredHook = handler;
          }
        }
      };

      register(on);
      assert(registeredHook, 'tool.call hook must be registered');
      assertStrictEqual(registeredFilter?.tool, 'Bash');

      let nextCalled = false;
      const mockEvent = { command: 'git commit -m "Fix asset graph view"' };
      const next = (e: any) => {
        nextCalled = true;
        return { success: true, event: e };
      };

      const result = await registeredHook(
        { fs: { read: async () => '' }, env: { get: async () => undefined } },
        mockEvent,
        next
      );
      assertStrictEqual(nextCalled, true);
      assertStrictEqual(result.success, true);
    });

    test('intercepts and blocks leaking Bash tool call returning deny', async () => {
      let registeredHook: any = null;
      const on = (event: string, filterOrHandler: any, handler?: any) => {
        if (event === 'tool.call') {
          registeredHook = typeof filterOrHandler === 'function' ? filterOrHandler : handler;
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
        command: 'gh pr create -R apache/airflow -t "Fix CVE-2026-1111: SSRF vulnerability"',
      };
      const next = () => {
        nextCalled = true;
      };

      const result = await registeredHook(
        { fs: { read: async () => mockProject }, env: { get: async () => undefined } },
        mockEvent,
        next
      );
      assertStrictEqual(nextCalled, false, 'next() must NOT be called on blocked commands');
      assert(result.deny, 'Deny explanation must be returned');
      assert(result.deny.includes('Apache Magpie Security Guard'));
      assert(result.deny.includes('CVE id'));
      assert(result.deny.includes('SSRF'));
    });

    test('honors MAGPIE_ALLOW_EMBARGO_TERMS=1 via $.env.get in register()', async () => {
      let registeredHook: any = null;
      const on = (event: string, filterOrHandler: any, handler?: any) => {
        if (event === 'tool.call') {
          registeredHook = typeof filterOrHandler === 'function' ? filterOrHandler : handler;
        }
      };

      register(on);

      let nextCalled = false;
      const mockEvent = {
        command: 'gh pr create -R apache/airflow -t "fix(generate-cve-json): handle CVE fields"',
      };
      const next = (e: any) => {
        nextCalled = true;
        return { forwarded: e };
      };

      const result = await registeredHook(
        {
          fs: { read: async () => '' },
          env: { get: async (k: string) => (k === 'MAGPIE_ALLOW_EMBARGO_TERMS' ? '1' : undefined) },
        },
        mockEvent,
        next
      );
      assertStrictEqual(nextCalled, true, 'next() must be called when MAGPIE_ALLOW_EMBARGO_TERMS=1 is set');
      assertStrictEqual(result.forwarded.command, 'gh pr create -R apache/airflow -t "fix(generate-cve-json): handle CVE fields"');
    });

    test('register() blocks leaking command in upstream clone resolved via user.md without project.md', async () => {
      let registeredHook: any = null;
      const on = (event: string, filterOrHandler: any, handler?: any) => {
        if (event === 'tool.call') {
          registeredHook = typeof filterOrHandler === 'function' ? filterOrHandler : handler;
        }
      };

      register(on);

      const mockUserMd = '\n| Key | Value |\n| environment.upstream_clone | /home/dev/upstream-airflow |\n';
      const mockGitConfig = '\n[remote "origin"]\n  url = https://github.com/apache/airflow.git\n';
      let nextCalled = false;
      const mockEvent = {
        command: 'git -C /home/dev/upstream-airflow commit -m "Fix CVE-2026-1234 SSRF"',
      };
      const next = () => {
        nextCalled = true;
      };

      const result = await registeredHook(
        {
          fs: {
            read: async (p: string) => {
              if (p.includes('user.md')) return mockUserMd;
              if (p.includes('/home/dev/upstream-airflow/.git/config')) return mockGitConfig;
              return null;
            },
          },
          env: { get: async () => undefined },
        },
        mockEvent,
        next
      );
      assertStrictEqual(nextCalled, false, 'next() must NOT be called on blocked commands in upstream clone');
      assert(result.deny, 'Deny explanation must be returned');
      assert(result.deny.includes('CVE id'));
      assert(result.deny.includes('SSRF'));
    });

    test('intercepts bare git commit in upstream clone seeded from $.session.root() or e.cwd', async () => {
      let registeredHook: any = null;
      const on = (event: string, filterOrHandler: any, handler?: any) => {
        if (event === 'tool.call') {
          registeredHook = typeof filterOrHandler === 'function' ? filterOrHandler : handler;
        }
      };
      register(on);

      const mockUserMd = '\n| Key | Value |\n| environment.upstream_clone | /home/dev/upstream-airflow |\n';
      const mockGitConfig = '\n[remote "origin"]\n  url = https://github.com/apache/airflow.git\n';
      let nextCalled = false;
      const mockEvent = {
        command: 'git commit -m "Fix CVE-2026-1234 SSRF"',
        cwd: '/home/dev/upstream-airflow',
      };
      const next = () => {
        nextCalled = true;
      };

      const result = await registeredHook(
        {
          fs: {
            read: async (p: string) => {
              if (p.includes('user.md')) return mockUserMd;
              if (p.includes('/home/dev/upstream-airflow/.git/config')) return mockGitConfig;
              return null;
            },
          },
          session: {
            root: async () => '/home/dev/upstream-airflow',
          },
          env: { get: async () => undefined },
        },
        mockEvent,
        next
      );
      assertStrictEqual(nextCalled, false, 'next() must NOT be called on bare commit in upstream clone');
      assert(result.deny, 'Deny explanation must be returned');
      assert(result.deny.includes('CVE id'));
      assert(result.deny.includes('SSRF'));
    });

    test('intercepts bare git commit when only $.session.root() is provided (e.cwd undefined)', async () => {
      let registeredHook: any = null;
      const on = (event: string, filterOrHandler: any, handler?: any) => {
        if (event === 'tool.call') {
          registeredHook = typeof filterOrHandler === 'function' ? filterOrHandler : handler;
        }
      };
      register(on);

      const mockUserMd = '\n| Key | Value |\n| environment.upstream_clone | /home/dev/upstream-airflow |\n';
      const mockGitConfig = '\n[remote "origin"]\n  url = https://github.com/apache/airflow.git\n';
      let nextCalled = false;
      const mockEvent = {
        command: 'git commit -m "Fix CVE-2026-1234 SSRF"',
      };
      const next = () => {
        nextCalled = true;
      };

      const result = await registeredHook(
        {
          fs: {
            read: async (p: string) => {
              if (p.includes('user.md')) return mockUserMd;
              if (p.includes('/home/dev/upstream-airflow/.git/config')) return mockGitConfig;
              return null;
            },
          },
          session: {
            root: async () => '/home/dev/upstream-airflow',
          },
          env: { get: async () => undefined },
        },
        mockEvent,
        next
      );
      assertStrictEqual(nextCalled, false, 'next() must NOT be called on bare commit in upstream clone');
      assert(result.deny, 'Deny explanation must be returned');
      assert(result.deny.includes('CVE id'));
      assert(result.deny.includes('SSRF'));
    });

    test('allows bare git commit on private tracker repo when event provides explicit tracker cwd', async () => {
      let registeredHook: any = null;
      const on = (event: string, filterOrHandler: any, handler?: any) => {
        if (event === 'tool.call') {
          registeredHook = typeof filterOrHandler === 'function' ? filterOrHandler : handler;
        }
      };
      register(on);

      const mockProjectMd = 'tracker_repo: apache/airflow-security\nupstream_repo: apache/airflow\n';
      const mockTrackerGitConfig = '\n[remote "origin"]\n  url = https://github.com/apache/airflow-security.git\n';
      let nextCalled = false;
      const mockEvent = {
        cwd: '/home/dev/tracker',
        command: 'git commit -m "Fix CVE-2026-1234 SSRF in private tracker"',
      };
      const next = (e: any) => {
        nextCalled = true;
        return { success: true };
      };

      const result = await registeredHook(
        {
          fs: {
            read: async (p: string) => {
              if (p.includes('project.md')) return mockProjectMd;
              if (p.includes('/home/dev/tracker/.git/config') || p === '.git/config') return mockTrackerGitConfig;
              return null;
            },
          },
          session: {
            root: async () => '/home/dev/tracker',
          },
          env: { get: async () => undefined },
        },
        mockEvent,
        next
      );
      assertStrictEqual(nextCalled, true, 'next() must be called for verified tracker cwd commit');

      // Under session root fallback (no event cwd), tracker exemption is disabled (Blocking #1 fix)
      let fallbackNextCalled = false;
      const fallbackEvent = {
        command: 'git commit -m "Fix CVE-2026-1234 SSRF in private tracker"',
      };
      const fallbackResult = await registeredHook(
        {
          fs: {
            read: async (p: string) => {
              if (p.includes('project.md')) return mockProjectMd;
              if (p.includes('/home/dev/tracker/.git/config') || p === '.git/config') return mockTrackerGitConfig;
              return null;
            },
          },
          session: {
            root: async () => '/home/dev/tracker',
          },
          env: { get: async () => undefined },
        },
        fallbackEvent,
        () => { fallbackNextCalled = true; }
      );
      assertStrictEqual(fallbackNextCalled, false, 'session root fallback must NOT exempt tracker from term scan');
      assertStrictEqual(typeof fallbackResult?.deny, 'string', 'must deny when session root fallback encounters CVE');
    });

    test('passes non-string command through to next() unchanged', async () => {
      let registeredHook: any = null;
      const on = (event: string, filterOrHandler: any, handler?: any) => {
        if (event === 'tool.call') {
          registeredHook = typeof filterOrHandler === 'function' ? filterOrHandler : handler;
        }
      };

      register(on);

      let nextCalled = false;
      const mockEvent = { command: 12345 };
      const next = (e: any) => {
        nextCalled = true;
        return { forwarded: e };
      };

      const result = await registeredHook(
        { fs: { read: async () => '' }, env: { get: async () => undefined } },
        mockEvent,
        next
      );
      assertStrictEqual(nextCalled, true);
    });
  });

  describe('Review #4 hardening & edge-case prevention', () => {
    test('identifies upstream clone from user.md environment.upstream_clone without project.md', async () => {
      const mockUserMd = `
| Key | Value |
| environment.upstream_clone | /home/dev/upstream-airflow |
`;
      const mockGitConfig = `
[remote "origin"]
  url = https://github.com/apache/airflow.git
`;
      const res = await evaluatePublicSurfaceCommand('git -C /home/dev/upstream-airflow commit -m "Fix CVE-2026-1234 SSRF"', {
        readFile: async (p: string) => {
          if (p.includes('user.md')) return mockUserMd;
          if (p.includes('/home/dev/upstream-airflow/.git/config')) return mockGitConfig;
          return null;
        },
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
      assert(res.matchedTerms.includes('SSRF'));
    });

    test('never exempts gh api graphql mutations even when executed in tracker checkout', async () => {
      const trackerGitConfig = `
[remote "origin"]
  url = https://github.com/airflow-s/airflow-s.git
`;
      const res = await evaluatePublicSurfaceCommand('git -C /tracker status && gh api graphql -f query=\'mutation{addComment(input:{body:"Fix SSRF"})}\'', {
        readFile: async (p: string) => {
          if (p.includes('.git/config')) return trackerGitConfig;
          return null;
        },
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('SSRF'));
    });

    test('inspects custom field names in gh api graphql mutations', async () => {
      const res = await evaluatePublicSurfaceCommand("gh api graphql -f customVar='CVE-2026-9999 SSRF'", {
        readFile: async () => null,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
      assert(res.matchedTerms.includes('SSRF'));
    });

    test('inspects git commit --trailer', async () => {
      const res1 = await evaluatePublicSurfaceCommand('git commit -m "Clean message" --trailer "Fixes: CVE-2026-1234"', {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
      });
      assertStrictEqual(res1.blocked, true);
      assert(res1.matchedTerms.includes('CVE id'));

      const res2 = await evaluatePublicSurfaceCommand('git commit -m "Clean message" --trailer="Fixes: SSRF"', {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
      });
      assertStrictEqual(res2.blocked, true);
      assert(res2.matchedTerms.includes('SSRF'));
    });

    test('marks message reuse flags as dynamic input (-C, -c, --reuse-message, --fixup, --squash)', async () => {
      for (const flag of ['-C HEAD', '-c HEAD', '--reuse-message=HEAD', '--reedit-message=HEAD', '--fixup=HEAD', '--squash=HEAD']) {
        const res = await evaluatePublicSurfaceCommand(`git commit ${flag}`, {
          projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
        });
        assertStrictEqual(res.blocked, true, `Expected ${flag} to be blocked as dynamic input`);
        assert(res.matchedTerms.includes('dynamic input'));
      }
    });

    test('inspects clustered git tag flags like git tag -am', async () => {
      const res = await evaluatePublicSurfaceCommand('git tag -am "Release CVE-2026-1234" v1.0', {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('isolates cd across pipeline separator so pipe does not leak directory context', async () => {
      const pipeCmd = 'cd ../tracker | gh pr comment 1 -R apache/airflow -b "Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(pipeCmd, {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('marks same-command file redirection into message file as dynamic input', async () => {
      const redirstr = 'printf "Fix CVE-2026-1234" > msg.txt; gh pr comment 1 -R apache/airflow -F msg.txt';
      const res = await evaluatePublicSurfaceCommand(redirstr, {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
        readFile: async () => 'stale neutral content',
      });
      assertStrictEqual(res.blocked, true);
    });
  });

  describe('Review #5 hardening & shape fixes', () => {
    test('tracker URL in PR/issue comment body does not exempt upstream command', async () => {
      const cmd =
        'gh pr comment 1 -R apache/airflow -b "Fix CVE-2026-1234, see https://github.com/airflow-s/airflow-s/issues/9"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
      });
      assertStrictEqual(res.blocked, true, 'Must block disclosure text even when body cites tracker issue URL');
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('positional PR/issue URL still correctly sets target repo', async () => {
      // Positional tracker URL is exempt
      const trackerCmd = 'gh pr comment https://github.com/airflow-s/airflow-s/pull/9 -b "Fix CVE-2026-1234"';
      const resTracker = await evaluatePublicSurfaceCommand(trackerCmd, {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
      });
      assertStrictEqual(resTracker.blocked, false);

      // Positional upstream URL is blocked
      const upstreamCmd = 'gh pr comment https://github.com/apache/airflow/pull/9 -b "Fix CVE-2026-1234"';
      const resUpstream = await evaluatePublicSurfaceCommand(upstreamCmd, {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
      });
      assertStrictEqual(resUpstream.blocked, true);
      assert(resUpstream.matchedTerms.includes('CVE id'));
    });

    test('GH_REPO= is ignored for git commands (git ignores GH_REPO)', async () => {
      const cmd = 'GH_REPO=airflow-s/airflow-s git commit -m "Fix CVE-2026-1234 SSRF"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
        readFile: async (p) => (p.includes('.git/config') ? '[remote "origin"]\nurl = https://github.com/apache/airflow.git' : ''),
      });
      assertStrictEqual(res.blocked, true, 'GH_REPO before git must not exempt commit in upstream repo');
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('GH_REPO= does not exempt gh api graphql mutation', async () => {
      const cmd =
        'GH_REPO=airflow-s/airflow-s gh api graphql -f query=\'mutation{addComment(input:{subjectId:"node123",body:"Fix CVE-2026-1234 SSRF"})}\'';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
      });
      assertStrictEqual(res.blocked, true, 'GraphQL mutation must not be exempted by GH_REPO or targetRepo');
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('gh api repos/{owner}/{repo}/... placeholders inherit cwd remote and do not bypass', async () => {
      const cmd = 'gh api repos/{owner}/{repo}/issues/1/comments -f body="Fix CVE-2026-1234 SSRF"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
        readFile: async (p) => (p.includes('.git/config') ? '[remote "origin"]\nurl = https://github.com/apache/airflow.git' : ''),
      });
      assertStrictEqual(res.blocked, true, 'Literal {owner}/{repo} must inherit upstream cwd remote and block disclosure');
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('gh pr create -f and --fill-verbose are recognized as dynamic input', async () => {
      for (const flag of ['-f', '--fill-verbose']) {
        const cmd = `gh pr create -R apache/airflow ${flag}`;
        const res = await evaluatePublicSurfaceCommand(cmd, {
          projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
        });
        assertStrictEqual(res.blocked, true, `Expected ${flag} to be blocked as dynamic input`);
        assert(res.matchedTerms.includes('dynamic input'));
      }
    });

    test('git commit attached reuse flags -CHEAD and -cHEAD are recognized as dynamic input', async () => {
      for (const flag of ['-CHEAD', '-cHEAD']) {
        const cmd = `git commit ${flag}`;
        const res = await evaluatePublicSurfaceCommand(cmd, {
          projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
        });
        assertStrictEqual(res.blocked, true, `Expected ${flag} to be blocked as dynamic input`);
        assert(res.matchedTerms.includes('dynamic input'));
      }
    });

    test('gh api attached field forms -fbody=... and -Fbody=@file are parsed', async () => {
      const inlineCmd = 'gh api repos/apache/airflow/issues/1/comments -fbody="Fix CVE-2026-1234 SSRF"';
      const resInline = await evaluatePublicSurfaceCommand(inlineCmd, {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
      });
      assertStrictEqual(resInline.blocked, true, 'Attached -fbody= must be inspected');
      assert(resInline.matchedTerms.includes('CVE id'));

      const fileCmd = 'gh api repos/apache/airflow/issues/1/comments -Fbody=@cve_msg.txt';
      const resFile = await evaluatePublicSurfaceCommand(fileCmd, {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
        readFile: async () => 'Fix CVE-2026-1234 SSRF',
      });
      assertStrictEqual(resFile.blocked, true, 'Attached -Fbody=@file must read referenced file and block');
      assert(resFile.matchedTerms.includes('CVE id'));
    });

    test('unwraps command wrappers and subshells (command, env, parentheses)', async () => {
      const cmds = [
        '( git commit -m "Fix CVE-2026-1234" )',
        'command git commit -m "Fix CVE-2026-1234"',
        'command -p git commit -m "Fix CVE-2026-1234"',
        'env FOO=bar git commit -m "Fix CVE-2026-1234"',
      ];

      for (const cmd of cmds) {
        const res = await evaluatePublicSurfaceCommand(cmd, {
          projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
          readFile: async (p) => (p.includes('.git/config') ? '[remote "origin"]\nurl = https://github.com/apache/airflow.git' : ''),
        });
        assertStrictEqual(res.blocked, true, `Command wrapper/subshell "${cmd}" must be unwrapped and inspected`);
        assert(res.matchedTerms.includes('CVE id'));
      }
    });

    test('fails closed when git or gh is invoked via unknown wrapper (e.g. sudo git)', async () => {
      const cmd = 'sudo git commit -m "Neutral message"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s', upstreamRepo: 'apache/airflow' },
        readFile: async (p) => (p.includes('.git/config') ? '[remote "origin"]\nurl = https://github.com/apache/airflow.git' : ''),
      });
      assertStrictEqual(res.blocked, true, 'Unknown command wrapper with git must fail closed');
      assert(res.matchedTerms.includes('dynamic input'));
    });
  });

  describe('Review #6 hardening & fail-closed defaults', () => {
    const config = {
      trackerRepo: 'airflow-s/airflow-s',
      upstreamRepo: 'apache/airflow',
      upstreamClonePath: '/home/user/upstream',
    };

    const trackerGitConfig = '[remote "origin"]\nurl = https://github.com/airflow-s/airflow-s.git';
    const upstreamGitConfig = '[remote "origin"]\nurl = https://github.com/apache/airflow.git';

    // 1. Subshell grouping and directory transition tracking
    test('tracks cd across subshell parentheses and blocks leaking commit inside subshell', async () => {
      const cmd = '(cd /home/user/upstream && git commit -m "Fix CVE-2026-1234")';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async (p) => (p.includes('/home/user/upstream') ? upstreamGitConfig : trackerGitConfig),
      });
      assertStrictEqual(res.blocked, true, 'Subshell group with cd to upstream must update directory and block commit');
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('tracks cd across brace grouping { ... } and blocks leaking commit', async () => {
      const cmd = '{ cd /home/user/upstream; git commit -m "Fix CVE-2026-1234"; }';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async (p) => (p.includes('/home/user/upstream') ? upstreamGitConfig : trackerGitConfig),
      });
      assertStrictEqual(res.blocked, true, 'Brace group with cd to upstream must update directory and block commit');
      assert(res.matchedTerms.includes('CVE id'));
    });

    // 2. Binary basename matching (/usr/bin/git, ~/bin/gh, ./git)
    test('recognizes absolute and relative binary paths as git and gh commands', async () => {
      const testCases = [
        '/usr/bin/git commit -m "Fix CVE-2026-1234"',
        '~/bin/gh pr comment 1 -R apache/airflow -b "Fix CVE-2026-1234"',
        './git commit -m "Fix CVE-2026-1234"',
      ];

      for (const cmd of testCases) {
        const res = await evaluatePublicSurfaceCommand(cmd, {
          projectConfig: config,
          readFile: async () => upstreamGitConfig,
        });
        assertStrictEqual(res.blocked, true, `Binary path invocation "${cmd}" must be recognized and scrubbed`);
        assert(res.matchedTerms.includes('CVE id'));
      }
    });

    // 3. Command-position checking: arguments to non-wrappers are allowed
    test('allows git and gh as plain arguments to non-wrapper commands', async () => {
      const allowedCmds = [
        'grep git notes.md',
        'which gh',
        'brew upgrade gh',
        'cat git_guide.txt',
      ];

      for (const cmd of allowedCmds) {
        const res = await evaluatePublicSurfaceCommand(cmd, {
          projectConfig: config,
          readFile: async () => upstreamGitConfig,
        });
        assertStrictEqual(res.blocked, false, `Command "${cmd}" with git/gh argument must not be blocked`);
      }
    });

    test('wrapped git/gh command gives specific wrapped-command blocking message', async () => {
      const cmd = 'sudo git commit -m "Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.reason?.includes('sudo') || res.reason?.includes('wrapped'));
    });

    // 4. Git repository redirection flags (--git-dir, --work-tree, GIT_DIR, GIT_WORK_TREE)
    test('fails closed on --git-dir and --work-tree redirection flags', async () => {
      const redirectionCmds = [
        'git --git-dir=/up/.git --work-tree=/up commit -m "Fix CVE-2026-1234"',
        'git --git-dir /up/.git commit -m "Fix CVE-2026-1234"',
        'GIT_DIR=/up/.git git commit -m "Fix CVE-2026-1234"',
        'GIT_WORK_TREE=/up git commit -m "Fix CVE-2026-1234"',
      ];

      for (const cmd of redirectionCmds) {
        const res = await evaluatePublicSurfaceCommand(cmd, {
          projectConfig: config,
          readFile: async () => trackerGitConfig,
        });
        assertStrictEqual(res.blocked, true, `Git redirection command "${cmd}" must fail closed`);
      }
    });

    // 5. Option values in gh api are skipped when extracting target repository
    test('skips gh api option values before extracting target repository', async () => {
      const files: Record<string, string> = {
        'payloads/comment.json': JSON.stringify({ body: 'Fix CVE-2026-1234 vulnerability' }),
      };
      const cmd = 'gh api --input payloads/comment.json repos/apache/airflow/issues/1/comments';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async (p) => {
          for (const [k, v] of Object.entries(files)) {
            if (p.endsWith(k) || p === k) return v;
          }
          return trackerGitConfig;
        },
      });
      assertStrictEqual(res.blocked, true, 'gh api with --input must extract real endpoint and scrub payload');
      assert(res.matchedTerms.includes('CVE id'));
    });

    // 6. GraphQL mutation in --input or @file treated as mutation (never exempt)
    test('treats gh api graphql with --input as mutation and blocks on forbidden terms from tracker', async () => {
      const files: Record<string, string> = {
        'query.json': JSON.stringify({ query: 'mutation { addComment(input: { body: "Fix CVE-2026-1234" }) { clientMutationId } }' }),
      };
      const cmd = 'gh api graphql --input query.json';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async (p) => {
          if (p.endsWith('query.json') || p === 'query.json') return files['query.json'];
          return trackerGitConfig;
        },
      });
      assertStrictEqual(res.blocked, true, 'GraphQL query in --input file must be treated as mutation and scrubbed');
      assert(res.matchedTerms.includes('CVE id'));
    });

    // 7. Git remote URL parsing in inspectDirectoryRemote
    test('inspectDirectoryRemote handles quoted URLs, trailing slashes, and comments', async () => {
      const configs = [
        '[remote "origin"]\nurl = "https://github.com/apache/airflow.git"',
        '[remote "origin"]\nurl = https://github.com/apache/airflow/',
        '[remote "origin"]\nurl = https://github.com/apache/airflow.git # primary remote',
      ];

      for (const cfg of configs) {
        const cmd = 'git commit -m "Fix CVE-2026-1234"';
        const res = await evaluatePublicSurfaceCommand(cmd, {
          projectConfig: config,
          readFile: async () => cfg,
        });
        assertStrictEqual(res.blocked, true, `Commit with config "${cfg}" must match upstream and be blocked`);
      }
    });

    test('inspectDirectoryRemote returns determined: false for unparsable remote URLs', async () => {
      const cmd = 'git commit -m "Clean commit message"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: { trackerRepo: 'airflow-s/airflow-s' },
        readFile: async () => '[remote "origin"]\nurl = invalid-remote-url-without-slug',
      });
      // In unparsable remote without project.md upstream, clean commit passes without false positive
      assertStrictEqual(res.blocked, false);
    });

    // 8. Fails closed when public surface command reads file modified earlier on same line
    test('fails closed when file read via -F was written earlier on the same line', async () => {
      const files: Record<string, string> = {
        'msg.md': 'Neutral text initially',
      };

      const cmd = 'cp private.md msg.md; gh pr comment 1 -R apache/airflow -F msg.md';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async (p) => {
          if (p.endsWith('msg.md') || p === 'msg.md') return files['msg.md'];
          return trackerGitConfig;
        },
      });
      assertStrictEqual(res.blocked, true, 'cp before gh -F on same line must fail closed as dynamic input');
      assert(res.matchedTerms.includes('dynamic input'));
    });

    test('allows safe read-only commands before file read on same line', async () => {
      const files: Record<string, string> = {
        'msg.md': 'Safe functional fix description',
      };

      const cmd = 'echo "Logging step"; gh pr comment 1 -R apache/airflow -F msg.md';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async (p) => {
          if (p.endsWith('msg.md') || p === 'msg.md') return files['msg.md'];
          return trackerGitConfig;
        },
      });
      assertStrictEqual(res.blocked, false, 'echo before gh -F with neutral message should be allowed');
    });

    // 9. Unresolved target repo (-R "$REPO") falls through to dynamic input check
    test('fails closed when target repository is dynamic variable -R "$REPO"', async () => {
      const cmd = 'gh pr comment 1 -R "$REPO" -b "Neutral text"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => trackerGitConfig,
      });
      assertStrictEqual(res.blocked, true, 'Dynamic target -R "$REPO" must fail closed');
      assert(res.matchedTerms.includes('dynamic input'));
    });

    test('blocks forbidden terms even when target repo is dynamic -R "$REPO"', async () => {
      const cmd = 'gh pr comment 1 -R "$REPO" -b "Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => trackerGitConfig,
      });
      assertStrictEqual(res.blocked, true, 'Dynamic target with CVE must block on CVE');
      assert(res.matchedTerms.includes('CVE id'));
    });

    // 10. Accidental-leak framing in blocking reason
    test('blocking reason includes accidental-leak non-perimeter framing', async () => {
      const cmd = 'git commit -m "Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.reason?.includes('guard against accidental public disclosure'));
    });
  });

  describe('Review #7 maintainer feedback & edge-case hardening', () => {
    const config = {
      trackerRepo: 'airflow-s/airflow-s',
      upstreamRepo: 'apache/airflow',
      upstreamClonePath: '/home/user/upstream',
    };

    const trackerGitConfig = '[remote "origin"]\nurl = https://github.com/airflow-s/airflow-s.git';
    const upstreamGitConfig = '[remote "origin"]\nurl = https://github.com/apache/airflow.git';

    // 1. Bare commands with seeded cwd
    test('bare git commit in upstream clone with no project.md blocks on CVE using options.cwd', async () => {
      const cmd = 'git commit -m "Fix CVE-2026-1234 SSRF"';
      const mockUserMd = '\n| Key | Value |\n| environment.upstream_clone | /home/dev/upstream-airflow |\n';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        cwd: '/home/dev/upstream-airflow',
        readFile: async (p) => {
          if (p.includes('user.md')) return mockUserMd;
          if (p.includes('/home/dev/upstream-airflow/.git/config')) return upstreamGitConfig;
          return null;
        },
      });
      assertStrictEqual(res.blocked, true, 'Bare git commit in upstream clone must be evaluated against upstream');
      assert(res.matchedTerms.includes('CVE id'));
    });

    // 2. Subshell ( ... ) vs brace group { ...; } cwd persistence
    test('restores virtualCwd after subshell group (cd ...) so subsequent command is evaluated in upstream', async () => {
      const cmd = '(cd ../tracker && gh issue view 1); git commit -m "Fix CVE-2026-1234 SSRF"';
      const mockUserMd = '\n| Key | Value |\n| environment.upstream_clone | /home/dev/upstream-airflow |\n';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        cwd: '/home/dev/upstream-airflow',
        readFile: async (p) => {
          if (p.includes('user.md')) return mockUserMd;
          if (p.includes('/home/dev/upstream-airflow/.git/config')) return upstreamGitConfig;
          if (p.includes('tracker/.git/config')) return trackerGitConfig;
          return null;
        },
      });
      assertStrictEqual(res.blocked, true, 'Subshell cd must not carry over; subsequent commit runs in upstream and blocks');
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('preserves virtualCwd across brace group { cd ...; } so subsequent command runs in tracker', async () => {
      const cmd = '{ cd ../tracker; gh issue view 1; }; git commit -m "Fix CVE-2026-1234 SSRF"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        cwd: '/home/dev/upstream-airflow',
        projectConfig: config,
        readFile: async (p) => {
          if (p.includes('tracker/.git/config')) return trackerGitConfig;
          return upstreamGitConfig;
        },
      });
      assertStrictEqual(res.blocked, false, 'Brace group cd must carry over; subsequent commit runs in tracker and is allowed');
    });

    // 3. Wrapper arguments (timeout 30 git, nice -n 10 git, sudo -u x git)
    test('treats line as wrapped when git appears after wrapper arguments (timeout 30 git)', async () => {
      const cmd = 'timeout 30 git commit -m "Neutral functional change"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('wrapped command'));
    });

    test('treats line as wrapped when git appears after nice options (nice -n 10 git)', async () => {
      const cmd = 'nice -n 10 git commit -m "Neutral functional change"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('wrapped command'));
    });

    test('treats line as wrapped when git appears after sudo flags (sudo -u dev git)', async () => {
      const cmd = 'sudo -u dev git commit -m "Neutral functional change"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('wrapped command'));
    });

    test('treats line as wrapped when gh appears after timeout options (timeout 30 gh pr comment)', async () => {
      const cmd = 'timeout 30 gh pr comment 1 -R apache/airflow -b "Neutral comment"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('wrapped command'));
    });

    // 4. Shell control transparent prefixes and eval / bash -c
    test('inspects git commit following shell control prefix (if ... then git commit)', async () => {
      const cmd = 'if true; then git commit -m "Fix CVE-2026-1234"; fi';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('inspects gh following shell loop prefix (for ... do gh pr comment)', async () => {
      const cmd = 'for x in 1; do gh pr comment 1 -R apache/airflow -b "Fix CVE-2026-1234"; done';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('inspects git commit following negation prefix (! git commit)', async () => {
      const cmd = '! git commit -m "Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('fails closed on bash -c invoking git', async () => {
      const cmd = 'bash -c "git commit -m \\"Routine functional change\\""';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('dynamic input'));
    });

    test('fails closed on eval invoking git', async () => {
      const cmd = 'eval "git commit -m \\"Routine functional change\\""';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('dynamic input'));
    });

    // 5. gh api leading slash and API host normalization
    test('normalizes gh api leading slash (/repos/apache/airflow/...) and blocks on CVE', async () => {
      const cmd = 'gh api /repos/apache/airflow/issues/1/comments -f body="Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('normalizes gh api full URL (https://api.github.com/repos/apache/airflow/...) and blocks on CVE', async () => {
      const cmd = 'gh api https://api.github.com/repos/apache/airflow/issues/1/comments -f body="Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('scans, not exempts, literal gh api endpoint without owner/repo placeholders from tracker checkout', async () => {
      const cmd = 'gh api /user -f note="Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => trackerGitConfig,
      });
      assertStrictEqual(res.blocked, true, 'Literal unparsed endpoint must not be exempted by tracker cwd');
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('allows neutral literal gh api endpoint without owner/repo placeholders', async () => {
      const cmd = 'gh api /user -f note="Routine status update"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => trackerGitConfig,
      });
      assertStrictEqual(res.blocked, false, 'Neutral literal endpoint should pass');
    });

    test('does not misparse /orgs/... as target repository and blocks on CVE', async () => {
      const cmd = 'gh api /orgs/apache/teams -f note="Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => trackerGitConfig,
      });
      assertStrictEqual(res.blocked, true, 'Literal orgs endpoint must not be exempted as a third-party repo');
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('allows neutral /orgs/... endpoint call', async () => {
      const cmd = 'gh api /orgs/apache/teams -f note="Routine team setup"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => trackerGitConfig,
      });
      assertStrictEqual(res.blocked, false, 'Neutral orgs endpoint should pass');
    });

    // 6. REST calls scan all field names
    test('scans non-body/title REST field (-f summary=...) and blocks on CVE', async () => {
      const cmd = 'gh api repos/apache/airflow/issues -f summary="Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('scans attached non-body/title REST field (-fnote=...) and blocks on CVE', async () => {
      const cmd = 'gh api repos/apache/airflow/issues -fnote="Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true);
      assert(res.matchedTerms.includes('CVE id'));
    });

    // 7. Heredoc bodies and unclosed quotes
    test('consumes heredoc body with internal quote and checks subsequent file-reading command', async () => {
      const files: Record<string, string> = { 'msg.md': 'Body content' };
      const cmd = "cat > msg.md <<'EOF'\nIt doesn't matter\nEOF\ngh pr create -t ok --body-file msg.md -R apache/airflow";
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async (p) => {
          if (p.endsWith('msg.md') || p === 'msg.md') return files['msg.md'];
          return upstreamGitConfig;
        },
      });
      assertStrictEqual(res.blocked, true, 'Heredoc write to file on same line must fail closed as dynamic input');
      assert(res.matchedTerms.includes('dynamic input'));
    });

    test('consumes heredoc body with internal quote and evaluates subsequent git commit', async () => {
      const cmd = "cat > msg.md <<'EOF'\nIt doesn't matter\nEOF\ngit commit -m \"Fix CVE-2026-1234 SSRF\"";
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true, 'Subsequent git commit must be parsed and blocked on CVE');
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('consumes heredoc body with backslash-escaped delimiter <<\\EOF and evaluates subsequent git commit', async () => {
      const cmd = "cat > msg.md <<\\EOF\nIt doesn't matter\nEOF\ngit commit -m \"Fix CVE-2026-1234 SSRF\"";
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true, 'Subsequent git commit after <<\\EOF must be parsed and blocked on CVE');
      assert(res.matchedTerms.includes('CVE id'));
    });

    test('fails closed on unclosed quote when git appears on command line', async () => {
      const cmd = 'git commit -m "Fix CVE-2026-1234';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => upstreamGitConfig,
      });
      assertStrictEqual(res.blocked, true, 'Unclosed quote with git binary must fail closed');
      assert(res.matchedTerms.includes('unclosed quote'));
    });

    // 8. Repository without Magpie config (unknown upstream)
    test('in unconfigured repository, gh command with neutral message passes term scan', async () => {
      const cmd = 'gh pr comment 1 -R someone/other -b "thanks"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: {}, // No upstreamRepo configured
        readFile: async () => null,
      });
      assertStrictEqual(res.blocked, false, 'Neutral comment in unconfigured repo should pass');
    });

    test('in unconfigured repository, gh command with CVE is blocked by term scan', async () => {
      const cmd = 'gh pr comment 1 -R someone/other -b "Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: {}, // No upstreamRepo configured
        readFile: async () => null,
      });
      assertStrictEqual(res.blocked, true, 'CVE in unconfigured repo should be caught by term scan');
      assert(res.matchedTerms.includes('CVE id'));
    });

    // 9. Scope-restricted --git-dir and GIT_DIR
    test('allows non-public-surface git command using --git-dir (git --git-dir=.git status)', async () => {
      const cmd = 'git --git-dir=.git status';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => trackerGitConfig,
      });
      assertStrictEqual(res.blocked, false, 'git status is not a public-surface command and should pass');
    });

    test('allows neutral git commit using --git-dir', async () => {
      const cmd = 'git --git-dir=.git commit -m "Refactor parser utilities"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => trackerGitConfig,
      });
      assertStrictEqual(res.blocked, false, 'Neutral commit with --git-dir should pass term scan');
    });

    test('blocks git commit using --git-dir when commit message contains forbidden term', async () => {
      const cmd = 'git --git-dir=.git commit -m "Fix CVE-2026-1234 SSRF"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        projectConfig: config,
        readFile: async () => trackerGitConfig,
      });
      assertStrictEqual(res.blocked, true, 'Commit with --git-dir must be checked and blocked on CVE');
      assert(res.matchedTerms.includes('CVE id'));
    });
  });

  describe('Proactive Maintainer Hardening (Round 8)', () => {
    const config = {
      trackerRepo: 'apache/magpie-tracker',
      upstreamRepo: 'apache/airflow',
      upstreamClonePath: '/home/dev/upstream',
    };
    const trackerGitConfig = '[remote "origin"]\nurl = https://github.com/apache/magpie-tracker\n';
    const upstreamGitConfig = '[remote "origin"]\nurl = https://github.com/apache/airflow\n';

    const mockFs: Record<string, string> = {
      '/tracker/.git/config': trackerGitConfig,
      '/home/dev/upstream/.git/config': upstreamGitConfig,
    };
    const mockReadFile = async (p: string) => mockFs[p] || null;

    test('1. cd <upstream> || exit 1 updates virtualCwd and blocks CVE commit', async () => {
      const cmd = 'cd /home/dev/upstream || exit 1; git commit -m "Fix CVE-2026-1234 SSRF"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        cwd: '/tracker',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(res.blocked, true, 'cd || exit 1 must update virtualCwd to upstream and block CVE commit');
    });

    test('2. gh api /v3/repos/... normalizes endpoint and blocks CVE comment', async () => {
      const cmd = 'gh api /v3/repos/apache/airflow/issues/1/comments -f body="Fix CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        cwd: '/tracker',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(res.blocked, true, 'gh api /v3/repos/ must normalize to upstream and block CVE');
    });

    test('3. env -C <upstream> updates directory and blocks CVE commit', async () => {
      const cmd = 'env -C /home/dev/upstream git commit -m "Fix CVE-2026-1234 SSRF"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        cwd: '/tracker',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(res.blocked, true, 'env -C must update directory context or fail closed');
    });

    test('4. git merge -m with CVE is classified and blocked', async () => {
      const cmd = 'git merge --no-ff feature/fix -m "Merge security fix for CVE-2026-1234"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        cwd: '/home/dev/upstream',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(res.blocked, true, 'git merge -m must be inspected and blocked on CVE');
    });

    test('5. git -C with .. path segments collapses and matches upstreamClonePath', async () => {
      const cmd = 'git -C /home/dev/tracker/../upstream commit -m "Fix CVE-2026-1234 SSRF"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        cwd: '/home/dev/tracker',
        projectConfig: {
          trackerRepo: 'apache/magpie-tracker',
          upstreamRepo: 'apache/airflow',
          upstreamClonePath: '/home/dev/upstream',
        },
        readFile: async () => null,
      });
      assertStrictEqual(res.blocked, true, 'Relative path with .. must collapse and match upstreamClonePath');
    });
  });

  describe('Review #8 maintainer feedback & edge-case hardening', () => {
    const config = {
      trackerRepo: 'apache/magpie-tracker',
      upstreamRepo: 'apache/airflow',
      upstreamClonePath: '/home/dev/upstream',
    };

    const mockReadFile = async (p: string) => {
      if (p.includes('/tracker/.git/config') || p === '.git/config') {
        return '[remote "origin"]\nurl = https://github.com/apache/magpie-tracker.git\n';
      }
      if (p.includes('/upstream/.git/config')) {
        return '[remote "origin"]\nurl = https://github.com/apache/airflow.git\n';
      }
      return null;
    };

    // 1. Blocking #1: Session root fallback disables tracker exemption and runs term scan
    test('1. session root fallback bare commit runs term scan and blocks on CVE', async () => {
      const cmd = 'git commit -m "Fix CVE-2026-1111 in auth module"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        cwd: '/tracker',
        isSessionRootFallback: true,
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(res.blocked, true, 'Fallback session root must NOT exempt tracker remote from term scan');
      assert(res.matchedTerms.includes('CVE id') || res.matchedTerms.includes('CVE'));

      // Neutral commit passes term scan even under session root fallback
      const neutral = await evaluatePublicSurfaceCommand('git commit -m "Refactor auth module"', {
        cwd: '/tracker',
        isSessionRootFallback: true,
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(neutral.blocked, false, 'Neutral commit under fallback session root must pass term scan');

      // Verified explicit tracker cwd (non-fallback) exempts
      const verified = await evaluatePublicSurfaceCommand('git commit -m "Fix CVE-2026-1111 in auth module"', {
        cwd: '/tracker',
        isSessionRootFallback: false,
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(verified.blocked, false, 'Verified tracker cwd exempts commit');
    });

    // 2. Blocking #2: Missing or placeholder upstreamRepo falls through to term scan
    test('2. missing upstreamRepo falls through to term scan on bare commit', async () => {
      const unconfiguredReadFile = async (p: string) => {
        if (p.includes('.git/config')) {
          return '[remote "origin"]\nurl = https://github.com/some-fork/airflow.git\n';
        }
        return null;
      };

      const res = await evaluatePublicSurfaceCommand('git commit -m "Fix CVE-2026-1234 vulnerability"', {
        cwd: '/some-fork',
        projectConfig: {
          trackerRepo: 'apache/magpie-tracker',
          // upstreamRepo is undefined/unconfigured!
        },
        readFile: unconfiguredReadFile,
      });
      assertStrictEqual(res.blocked, true, 'Unknown upstream repo must fail closed to term scan');
      assert(res.matchedTerms.includes('CVE id') || res.matchedTerms.includes('CVE'));

      // Neutral commit passes term scan
      const neutral = await evaluatePublicSurfaceCommand('git commit -m "Neutral refactor"', {
        cwd: '/some-fork',
        projectConfig: {
          trackerRepo: 'apache/magpie-tracker',
        },
        readFile: unconfiguredReadFile,
      });
      assertStrictEqual(neutral.blocked, false, 'Neutral commit must pass when upstream is unknown');
    });

    // 3. Edge Case #3: pushd and builtin cd directory tracking and safe read-only commands
    test('3. pushd and builtin cd track directory changes across sequential operators', async () => {
      const pushdCmd = 'pushd /home/dev/upstream && git commit -m "Fix CVE-2026-2222"';
      const pushdRes = await evaluatePublicSurfaceCommand(pushdCmd, {
        cwd: '/tracker',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(pushdRes.blocked, true, 'pushd must update virtual directory to upstream');

      const builtinCmd = 'builtin cd /home/dev/upstream && git commit -m "Fix CVE-2026-2222"';
      const builtinRes = await evaluatePublicSurfaceCommand(builtinCmd, {
        cwd: '/tracker',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(builtinRes.blocked, true, 'builtin cd must update virtual directory to upstream');

      // pushd is in SAFE_READONLY_COMMANDS so subsequent -F file read does not fail closed as dynamic input
      const safeReadFile = async (p: string) => {
        if (p.includes('msg.txt')) return 'Clean commit description';
        return mockReadFile(p);
      };
      const safePushd = await evaluatePublicSurfaceCommand('pushd /home/dev/upstream && git commit -F msg.txt', {
        cwd: '/tracker',
        projectConfig: config,
        readFile: safeReadFile,
      });
      assertStrictEqual(safePushd.blocked, false, 'pushd should be safe read-only and allow neutral -F file read');
    });

    // 4. Edge Case #4: missing gh write subcommands (issue create/edit, pr merge, release create, pr/issue close)
    test('4. inspects gh write subcommands and blocks on forbidden terms', async () => {
      // gh issue create -t / -b
      const issCreate = await evaluatePublicSurfaceCommand('gh issue create -R apache/airflow -t "Security vulnerability in webserver" -b "Details on CVE-2026-3333"');
      assertStrictEqual(issCreate.blocked, true, 'gh issue create must inspect title and body');

      // gh issue edit -b
      const issEdit = await evaluatePublicSurfaceCommand('gh issue edit 42 -R apache/airflow -b "Updated advisory for CVE-2026-3333"');
      assertStrictEqual(issEdit.blocked, true, 'gh issue edit must inspect body');

      // gh pr merge --subject / --body
      const prMergeSub = await evaluatePublicSurfaceCommand('gh pr merge 101 -R apache/airflow --subject "Merge CVE-2026-3333 security fix"');
      assertStrictEqual(prMergeSub.blocked, true, 'gh pr merge --subject must be inspected');

      const prMergeBody = await evaluatePublicSurfaceCommand('gh pr merge 101 -R apache/airflow --body "Addresses CVE-2026-3333"');
      assertStrictEqual(prMergeBody.blocked, true, 'gh pr merge --body must be inspected');

      // gh release create <tag> -t / --notes
      const relNotes = await evaluatePublicSurfaceCommand('gh release create v2.1.0 -R apache/airflow -t "Release 2.1.0" --notes "Fixes CVE-2026-3333"');
      assertStrictEqual(relNotes.blocked, true, 'gh release create --notes must be inspected');

      const relTag = await evaluatePublicSurfaceCommand('gh release create v2.1.0-cve-2026-3333 -R apache/airflow --notes "Clean notes"');
      assertStrictEqual(relTag.blocked, true, 'gh release create tag name must be inspected');

      // gh pr close -c / --comment
      const prClose = await evaluatePublicSurfaceCommand('gh pr close 101 -R apache/airflow --comment "Closed in favor of CVE-2026-3333 patch"');
      assertStrictEqual(prClose.blocked, true, 'gh pr close --comment must be inspected');

      // gh issue close -c / --comment
      const issClose = await evaluatePublicSurfaceCommand('gh issue close 42 -R apache/airflow -c "Resolved via CVE-2026-3333 fix"');
      assertStrictEqual(issClose.blocked, true, 'gh issue close -c must be inspected');

      // Neutral versions pass
      const neutralIss = await evaluatePublicSurfaceCommand('gh issue create -R apache/airflow -t "Improve logging" -b "More debug logs"');
      assertStrictEqual(neutralIss.blocked, false, 'Neutral gh issue create passes');

      const neutralMerge = await evaluatePublicSurfaceCommand('gh pr merge 101 -R apache/airflow --subject "Clean feature merge"');
      assertStrictEqual(neutralMerge.blocked, false, 'Neutral gh pr merge passes');

      const neutralRel = await evaluatePublicSurfaceCommand('gh release create v2.1.0 -R apache/airflow -t "Release 2.1.0" -n "Release notes"');
      assertStrictEqual(neutralRel.blocked, false, 'Neutral gh release create passes');
    });

    // 5. Edge Case #5: env -C composition and resolvePath argument order
    test('5. env -C composes with git -C without overwriting directory context', async () => {
      const cmd = 'env -C /home/dev/upstream git -C . commit -m "Fix CVE-2026-4444"';
      const res = await evaluatePublicSurfaceCommand(cmd, {
        cwd: '/tracker',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(res.blocked, true, 'env -C composed with git -C . must preserve upstream directory');
    });

    // 6. Edge Case #6: resolveProjectConfig reads user.md upstreamClonePath even when project.md defines both repos
    test('6. resolveProjectConfig reads user.md upstream_clone when project.md defines both repos', async () => {
      const mockConfigStore: Record<string, string> = {
        '.apache-magpie-overrides/project.md': '| tracker_repo | apache/magpie-tracker |\n| upstream_repo | apache/airflow |',
        '/home/user/.config/apache-magpie/user.md': '| upstream_clone | /home/user/workspace/airflow |',
      };
      const resolved = await resolveProjectConfig(
        async (p) => mockConfigStore[p],
        '/home/user/workspace/tracker',
        { HOME: '/home/user' }
      );
      assertStrictEqual(resolved.trackerRepo, 'apache/magpie-tracker');
      assertStrictEqual(resolved.upstreamRepo, 'apache/airflow');
      assertStrictEqual(resolved.upstreamClonePath, '/home/user/workspace/airflow');
    });

    // 7. Edge Case #7: inspectDirectoryRemote reads commondir config for linked worktrees
    test('7. inspectDirectoryRemote reads remotes from worktree common dir config', async () => {
      const worktreeFs: Record<string, string> = {
        '/worktree/branch-fix/.git': 'gitdir: /repo/main/.git/worktrees/branch-fix',
        '/repo/main/.git/worktrees/branch-fix/config': '[core]\n\tbare = false\n',
        '/repo/main/.git/config': '[remote "origin"]\n\turl = https://github.com/apache/airflow.git\n',
      };
      const res = await inspectDirectoryRemote(
        '/worktree/branch-fix',
        { upstreamRepo: 'apache/airflow' },
        async (p) => worktreeFs[p]
      );
      assertStrictEqual(res.determined, true, 'Must resolve remote from worktree common dir config');
      assertStrictEqual(res.isUpstream, true, 'Must detect upstream repository in worktree');
    });

    // 8. Nit #8: Scan git tag names and git merge branch refs
    test('8. scans git tag names and git merge branch refs for forbidden terms', async () => {
      // Lightweight tag with CVE name
      const tagRes = await evaluatePublicSurfaceCommand('git tag CVE-2026-5555-fix', {
        cwd: '/home/dev/upstream',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(tagRes.blocked, true, 'Tag name containing CVE must be blocked');

      // Annotated tag with CVE in name
      const annoTagRes = await evaluatePublicSurfaceCommand('git tag -a CVE-2026-5555-fix -m "Release"', {
        cwd: '/home/dev/upstream',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(annoTagRes.blocked, true, 'Annotated tag with CVE in name must be blocked');

      // Bare git merge of branch containing CVE
      const mergeRes = await evaluatePublicSurfaceCommand('git merge cve-2026-5555-patch', {
        cwd: '/home/dev/upstream',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(mergeRes.blocked, true, 'git merge with CVE branch ref must be blocked');

      // Neutral tag and merge pass
      const neutralTag = await evaluatePublicSurfaceCommand('git tag v1.0.0', {
        cwd: '/home/dev/upstream',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(neutralTag.blocked, false, 'Neutral tag must pass');

      const neutralMerge = await evaluatePublicSurfaceCommand('git merge feature/new-dashboard', {
        cwd: '/home/dev/upstream',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(neutralMerge.blocked, false, 'Neutral merge must pass');
    });

    // 9. Nit #9: git commit -am ... --amend is not falsely flagged
    test('9. git commit -am with --amend is not falsely flagged as dynamic reuse', async () => {
      // Neutral commit message with -am and --amend passes
      const neutralAmend = await evaluatePublicSurfaceCommand('git commit -am "Neutral amend message" --amend', {
        cwd: '/home/dev/upstream',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(neutralAmend.blocked, false, '-am with --amend provides explicit message and must pass');

      // Message with CVE is still blocked
      const cveAmend = await evaluatePublicSurfaceCommand('git commit -am "Fix CVE-2026-6666" --amend', {
        cwd: '/home/dev/upstream',
        projectConfig: config,
        readFile: mockReadFile,
      });
      assertStrictEqual(cveAmend.blocked, true, '-am with CVE must be blocked');
    });

    // 10. Nit #10: Shared helpers verify clustered flags and message/body flags
    test('10. shared helpers parse attached and clustered message and body flags', () => {
      // commit clustered -sam
      const sam = parseSubcommand('git commit -sam "Signed commit"');
      assertDeepStrictEqual(sam.extractedTexts, ['Signed commit']);

      // pr merge attached -b
      const prMerge = parseSubcommand('gh pr merge 123 --subject "Subject" -b"Attached body"');
      assert(prMerge.extractedTexts.includes('Subject'));
      assert(prMerge.extractedTexts.includes('Attached body'));

      // issue create attached -t and -b
      const iss = parseSubcommand('gh issue create -t"Title" -b"Body"');
      assert(iss.extractedTexts.includes('Title'));
      assert(iss.extractedTexts.includes('Body'));
    });
  });

  describe('register() with no cwd in the event (session-root fallback)', () => {
    const trackerProject = '\n| Key | Value |\n| tracker_repo | airflow-s/airflow-s |\n| upstream_repo | apache/airflow |\n';
    const trackerGitConfig = '\n[remote "origin"]\n  url = https://github.com/airflow-s/airflow-s.git\n';

    async function runInTracker(command: string): Promise<{ result: any; nextCalled: boolean }> {
      let registeredHook: any = null;
      register((event: string, filterOrHandler: any, handler?: any) => {
        if (event === 'tool.call') {
          registeredHook = typeof filterOrHandler === 'function' ? filterOrHandler : handler;
        }
      });
      let nextCalled = false;
      // The Bash tool call carries only `command` (and timeout/description), never a cwd.
      const result = await registeredHook(
        {
          session: { root: async () => '/home/dev/airflow-s' },
          fs: {
            read: async (p: string) => {
              if (p === '/home/dev/airflow-s/.apache-magpie-overrides/project.md') return trackerProject;
              if (p === '/home/dev/airflow-s/.git/config') return trackerGitConfig;
              return null;
            },
          },
          env: { get: async () => undefined },
        },
        { command },
        () => {
          nextCalled = true;
        }
      );
      return { result, nextCalled };
    }

    test('a bare tracker comment with a CVE id is blocked and told to name the tracker', async () => {
      const { result, nextCalled } = await runInTracker('gh issue comment 12 -b "Allocated CVE-2026-1234"');
      assertStrictEqual(nextCalled, false);
      assert(result.deny.includes('--repo airflow-s/airflow-s'), result.deny);
    });

    test('the same comment with an explicit tracker --repo passes', async () => {
      const { nextCalled } = await runInTracker('gh issue comment 12 --repo airflow-s/airflow-s -b "Allocated CVE-2026-1234"');
      assertStrictEqual(nextCalled, true);
    });
  });

});
