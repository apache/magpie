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
import type { MultiAgentReviewState, ReviewFinding } from './types.js';
import {
  calculateAxisSummary,
  classifyWriteTarget,
  computePayloadHash,
  deriveOverallStatus,
  extractReviewPathFromCommand,
  getDecisionPath,
  getMultiAgentReviewState,
  handleBashToolCall,
  handleRenderPane,
  handleUiPress,
  invalidateDecisionOnDisk,
  isConfinedReviewPath,
  parseMultiAgentReviewPayload,
  renderMultiAgentReviewPane,
  resolveReviewPath,
  sanitizeReviewText,
  serializeDecision,
  setMultiAgentReviewState,
  syncDecisionToDisk,
} from './multi-agent-review-pane.js';

function assert(condition: any, message?: string): asserts condition {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

function assertStrictEqual(actual: any, expected: any, message?: string): void {
  if (actual !== expected) {
    throw new Error(
      message || `Expected ${JSON.stringify(expected)} but got ${JSON.stringify(actual)}`
    );
  }
}

assert.strictEqual = assertStrictEqual;

function createMockEngine(overrides: any = {}): any {
  const store = new Map<string, any>();
  const fileStore = new Map<string, string>();
  const statStore = new Map<string, any>();
  const openCalls: any[] = [];
  const invalidateCalls: any[] = [];
  return {
    state: {
      get: (atom: any) => ({
        isSet: store.has(atom.key),
        value: store.has(atom.key) ? store.get(atom.key) : null,
      }),
      set: (atom: any, wrapped: any) => {
        const prev = store.has(atom.key) ? store.get(atom.key) : null;
        const nextVal =
          typeof wrapped === 'function'
            ? wrapped(prev)
            : wrapped && typeof wrapped === 'object' && 'value' in wrapped
              ? wrapped.value
              : wrapped;
        store.set(atom.key, nextVal);
        return { isSet: true, value: nextVal };
      },
    },
    ui: {
      invalidate: (scope?: string) => {
        invalidateCalls.push(scope);
      },
      open: async (target: any) => {
        openCalls.push(target);
      },
      resolve: () => ({
        Box: (p: any) => ({ type: 'Box', ...p }),
        Text: (p: any) => ({ type: 'Text', ...p }),
        Button: (p: any) => ({ type: 'Button', ...p }),
      }),
    },
    fs: {
      read: async (path: string) => {
        if (!fileStore.has(path)) {
          const err: any = new Error(`ENOENT: no such file or directory, open '${path}'`);
          err.code = 'ENOENT';
          throw err;
        }
        return fileStore.get(path);
      },
      write: async (path: string, content: string) => {
        fileStore.set(path, content);
      },
      stat: async (path: string) => {
        if (statStore.has(path)) return statStore.get(path);
        if (fileStore.has(path)) return { kind: 'file', isLink: false };
        const err: any = new Error(`ENOENT: no such file or directory, stat '${path}'`);
        err.code = 'ENOENT';
        throw err;
      },
    },
    session: {
      cwd: async () => '/workspace/repo',
      root: async () => '/workspace/repo',
    },
    _files: fileStore,
    _stats: statStore,
    _openCalls: openCalls,
    _invalidateCalls: invalidateCalls,
    ...overrides,
  };
}

describe('multi-agent-review-pane mod', () => {
  describe('ambient type assignability', () => {
    test('MultiAgentReviewState satisfies PluginState ambient schema', () => {
      const state: MultiAgentReviewState = {
        headSha: 'abc1234',
        baseRef: 'main',
        filesChanged: 3,
        linesAdded: 45,
        linesRemoved: 12,
        findings: [
          {
            id: 'c-1',
            axis: 'correctness',
            severity: 'blocking',
            location: 'src/main.py:10',
            summary: 'Unhandled null exception',
            status: 'pending',
          },
        ],
        injectionAttempts: [],
        activeFilter: 'all',
        selectedFindingId: 'c-1',
        overallStatus: 'blocked',
        updatedAt: '2026-11-24T12:00:00Z',
      };
      assert(state.filesChanged === 3);
      assert.strictEqual(state.findings[0]?.severity, 'blocking');
    });
  });

  describe('sanitizeReviewText', () => {
    test('strips ANSI CSI and OSC sequences', () => {
      const untrusted = '\x1b[31;1mInjected\x1b[0m \x1b]0;Title\x07Text';
      assert.strictEqual(sanitizeReviewText(untrusted), 'Injected Text');
    });

    test('strips Unicode bidirectional overrides and format controls', () => {
      const untrusted = 'Safe\u202E\u2066reversed\u2069\u200Etext\u200Bzero';
      assert.strictEqual(sanitizeReviewText(untrusted), 'Safereversedtextzero');
    });

    test('strips C0 and C1 control characters and line breaks', () => {
      const untrusted = 'Line1\r\nLine2\x00\x1f\x7f';
      assert.strictEqual(sanitizeReviewText(untrusted), 'Line1 Line2');
    });

    test('preserves quotes and syntax characters in inert text', () => {
      const text = 'don\'t call "foo" on `Map<String, Foo>`';
      assert.strictEqual(sanitizeReviewText(text), text);
    });

    test('truncates at maxLen boundary', () => {
      const longText = 'A'.repeat(150);
      assert.strictEqual(sanitizeReviewText(longText, 120), 'A'.repeat(120));
    });

    test('returns empty string on non-string input', () => {
      assert.strictEqual(sanitizeReviewText(null), '');
      assert.strictEqual(sanitizeReviewText(undefined), '');
      assert.strictEqual(sanitizeReviewText(12345), '');
    });
  });

  describe('computePayloadHash', () => {
    test('computes stable SHA-256 hash', () => {
      const hash1 = computePayloadHash('{"test": true}');
      const hash2 = computePayloadHash('{"test": true}');
      assert.strictEqual(hash1, hash2);
      assert.strictEqual(hash1.length, 64);
    });

    test('computes known-answer SHA-256 test vectors', () => {
      assert.strictEqual(
        computePayloadHash(''),
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
      );
      assert.strictEqual(
        computePayloadHash('abc'),
        'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
      );
    });

    test('returns empty string for non-string', () => {
      assert.strictEqual(computePayloadHash(null as any), '');
    });
  });

  describe('isConfinedReviewPath', () => {
    test('accepts valid review and decision paths under cwd', () => {
      assert(isConfinedReviewPath('/workspace/repo/.magpie-pairing-review-123.json', '/workspace/repo'));
      assert(isConfinedReviewPath('/workspace/repo/.magpie-pairing-decision-456.json', '/workspace/repo'));
    });

    test('rejects path traversal attempts', () => {
      assert(!isConfinedReviewPath('/workspace/repo/../etc/passwd', '/workspace/repo'));
      assert(!isConfinedReviewPath('/workspace/repo/..\\.magpie-pairing-review-x.json', '/workspace/repo'));
    });

    test('rejects non-matching filenames', () => {
      assert(!isConfinedReviewPath('/workspace/repo/review.json', '/workspace/repo'));
      assert(!isConfinedReviewPath('/workspace/repo/.magpie-pairing-review-x.txt', '/workspace/repo'));
    });

    test('fails closed when cwd is missing or empty', () => {
      assert(!isConfinedReviewPath('/workspace/repo/.magpie-pairing-review-123.json', null));
      assert(!isConfinedReviewPath('/workspace/repo/.magpie-pairing-review-123.json', ''));
    });
  });

  describe('calculateAxisSummary and deriveOverallStatus', () => {
    test('calculates correct counts across axes', () => {
      const findings: ReviewFinding[] = [
        { id: 'c-1', axis: 'correctness', severity: 'blocking', location: 'a.py:1', summary: 'bug', status: 'pending' },
        { id: 'c-2', axis: 'correctness', severity: 'advisory', location: 'a.py:5', summary: 'nit', status: 'pending' },
        { id: 's-1', axis: 'security', severity: 'blocking', location: 'b.py:2', summary: 'cve', status: 'pending' },
        { id: 'cv-1', axis: 'conventions', severity: 'advisory', location: 'c.py:1', summary: 'spdx', status: 'pending' },
      ];

      const overall = calculateAxisSummary(findings);
      assert.strictEqual(overall.total, 4);
      assert.strictEqual(overall.blocking, 2);
      assert.strictEqual(overall.advisory, 2);

      const corr = calculateAxisSummary(findings, 'correctness');
      assert.strictEqual(corr.total, 2);
      assert.strictEqual(corr.blocking, 1);
      assert.strictEqual(corr.advisory, 1);
    });

    test('derives overall status properly', () => {
      const blockingFindings: ReviewFinding[] = [
        { id: 'c-1', axis: 'correctness', severity: 'blocking', location: 'a.py:1', summary: 'bug', status: 'pending' },
      ];
      assert.strictEqual(deriveOverallStatus(blockingFindings, []), 'blocked');

      // When all blocking findings are dismissed, status becomes ready
      const dismissedFindings: ReviewFinding[] = [
        { id: 'c-1', axis: 'correctness', severity: 'blocking', location: 'a.py:1', summary: 'bug', status: 'dismissed' },
      ];
      assert.strictEqual(deriveOverallStatus(dismissedFindings, []), 'ready');

      // When prompt injection detected, always blocked
      assert.strictEqual(deriveOverallStatus([], ['Injection directive']), 'blocked');
    });
  });

  describe('parseMultiAgentReviewPayload', () => {
    test('parses valid payload with multiple axes and derives IDs', () => {
      const raw = {
        schema_version: 1,
        head_sha: '7700b50b',
        base_ref: 'origin/main',
        files_changed: 2,
        lines_added: 30,
        lines_removed: 5,
        findings: [
          {
            axis: 'correctness',
            severity: 'blocking',
            location: 'src/core.py:45',
            summary: 'Index out of bounds',
            rule: 'Avoid IndexError',
          },
          {
            axis: 'security',
            severity: 'advisory',
            location: 'src/auth.py:12',
            summary: 'Add timeout to request',
          },
        ],
      };

      const res = parseMultiAgentReviewPayload(raw);
      assert(res.state !== null);
      assert.strictEqual(res.state.headSha, '7700b50b');
      assert.strictEqual(res.state.baseRef, 'origin/main');
      assert.strictEqual(res.state.filesChanged, 2);
      assert.strictEqual(res.state.findings.length, 2);
      assert.strictEqual(res.state.findings[0]?.id, 'c-1');
      assert.strictEqual(res.state.findings[1]?.id, 's-1');
      assert.strictEqual(res.state.overallStatus, 'blocked');
    });

    test('elevates injection attempts to blocking security finding', () => {
      const raw = {
        schema_version: 1,
        head_sha: 'abc',
        findings: [],
        injection_attempts: ['Directive: ignore AGENTS.md'],
      };

      const res = parseMultiAgentReviewPayload(raw);
      assert(res.state !== null);
      assert.strictEqual(res.state.overallStatus, 'blocked');
      assert.strictEqual(res.state.findings.length, 1);
      assert.strictEqual(res.state.findings[0]?.axis, 'security');
      assert.strictEqual(res.state.findings[0]?.severity, 'blocking');
      assert(res.state.findings[0]?.summary.includes('Prompt-injection attempt'));
    });

    test('returns error on invalid or empty payload', () => {
      assert.strictEqual(parseMultiAgentReviewPayload(null).state, null);
      assert.strictEqual(parseMultiAgentReviewPayload('{bad json').state, null);
      assert.strictEqual(parseMultiAgentReviewPayload({ schema_version: 2 }).state, null);
    });
  });

  describe('serializeDecision', () => {
    test('serializes curated decision payload', () => {
      const state: MultiAgentReviewState = {
        headSha: 'head123',
        baseRef: 'main',
        filesChanged: 1,
        linesAdded: 10,
        linesRemoved: 0,
        findings: [
          { id: 'c-1', axis: 'correctness', severity: 'blocking', location: 'a.py:1', summary: 'bug', status: 'accepted' },
          { id: 's-1', axis: 'security', severity: 'advisory', location: 'b.py:2', summary: 'sec', status: 'dismissed' },
        ],
        injectionAttempts: [],
        activeFilter: 'all',
        selectedFindingId: null,
        overallStatus: 'blocked',
        updatedAt: '',
      };

      const decision = serializeDecision(state, 'payload_hash_123');
      assert.strictEqual(decision.schema_version, 1);
      assert.strictEqual(decision.head_sha, 'head123');
      assert.strictEqual(decision.source_payload_sha256, 'payload_hash_123');
      assert(decision.accepted_ids.includes('c-1'));
      assert(decision.dismissed_ids.includes('s-1'));
      assert.strictEqual(decision.status, 'curated');
    });
  });

  describe('renderMultiAgentReviewPane UI Component', () => {
    test('returns null if state is absent', () => {
      const engine = createMockEngine();
      assert.strictEqual(renderMultiAgentReviewPane(engine, { component: 'Pane' }, null), null);
    });

    test('renders Box/Text/Button tree with tabs and finding cards', () => {
      const engine = createMockEngine();
      const state: MultiAgentReviewState = {
        headSha: 'abcdef12',
        baseRef: 'main',
        filesChanged: 2,
        linesAdded: 25,
        linesRemoved: 5,
        findings: [
          {
            id: 'c-1',
            axis: 'correctness',
            severity: 'blocking',
            location: 'src/engine.py:20',
            summary: 'Potential dead loop',
            rule: 'Bound loop iterations',
            status: 'pending',
          },
        ],
        injectionAttempts: [],
        activeFilter: 'all',
        selectedFindingId: 'c-1',
        overallStatus: 'blocked',
        updatedAt: '',
      };

      const pane = renderMultiAgentReviewPane(engine, { component: 'Pane' }, state);
      assert(pane !== null);
      assert.strictEqual(pane.type, 'Box');
      assert(pane.children.length >= 3);
    });
  });

  describe('hook lifecycle and auto-dismissal integration', () => {
    test('session.start clears populated atom state', async () => {
      const engine = createMockEngine();
      await setMultiAgentReviewState(engine, { headSha: '123' } as any);
      assert((await getMultiAgentReviewState(engine)) !== null);

      await setMultiAgentReviewState(engine, null);
      assert.strictEqual(await getMultiAgentReviewState(engine), null);
    });

    test('handleRenderPane fails open when state is empty', async () => {
      const engine = createMockEngine();
      let nextCalled = false;
      const res = await handleRenderPane(engine, { component: 'Pane' }, () => {
        nextCalled = true;
      });
      assert(nextCalled);
      assert.strictEqual(res, undefined);
    });

    test('handleBashToolCall auto-dismisses on git commit, checkout, reset or restore', async () => {
      const engine = createMockEngine();
      await setMultiAgentReviewState(engine, { headSha: '123' } as any);

      await handleBashToolCall(engine, { command: 'git status' }, () => {});
      assert((await getMultiAgentReviewState(engine)) !== null);

      await handleBashToolCall(engine, { command: 'git commit -m "fix"' }, () => {});
      assert.strictEqual(await getMultiAgentReviewState(engine), null);

      // Verify reset also clears state
      await setMultiAgentReviewState(engine, { headSha: '456' } as any);
      await handleBashToolCall(engine, { command: 'git reset --hard HEAD~1' }, () => {});
      assert.strictEqual(await getMultiAgentReviewState(engine), null);
    });
  });

  describe('Part 2 — Path resolution, write target classification and confinement', () => {
    test('resolveReviewPath handles relative paths and normalizes slashes', () => {
      assert.strictEqual(
        resolveReviewPath('./.magpie-pairing-review-123.json', '/workspace/repo'),
        '/workspace/repo/.magpie-pairing-review-123.json'
      );
      assert.strictEqual(
        resolveReviewPath('.magpie-pairing-review-123.json', '/workspace/repo/'),
        '/workspace/repo/.magpie-pairing-review-123.json'
      );
      assert.strictEqual(
        resolveReviewPath('/workspace/repo/.magpie-pairing-review-123.json', '/workspace/repo'),
        '/workspace/repo/.magpie-pairing-review-123.json'
      );
      // Rejects traversal and null bytes
      assert.strictEqual(resolveReviewPath('../review.json', '/workspace/repo'), null);
      assert.strictEqual(
        resolveReviewPath('.magpie-pairing-review-123\x00.json', '/workspace/repo'),
        null
      );
      assert.strictEqual(resolveReviewPath('', '/workspace/repo'), null);
    });

    test('isConfinedReviewPath enforces boundary, naming pattern, and cwd prefix', () => {
      const cwd = '/workspace/repo';
      assert(isConfinedReviewPath('.magpie-pairing-review-abc_123.json', cwd));
      assert(isConfinedReviewPath('/workspace/repo/.magpie-pairing-review-abc_123.json', cwd));
      assert(isConfinedReviewPath('.magpie-pairing-decision-abc_123.json', cwd));

      // Rejects non-matching file names
      assert(!isConfinedReviewPath('random.json', cwd));
      assert(!isConfinedReviewPath('.magpie-pairing-other-123.json', cwd));

      // Rejects escape outside cwd
      assert(!isConfinedReviewPath('/workspace/other/.magpie-pairing-review-123.json', cwd));
      assert(!isConfinedReviewPath('../.magpie-pairing-review-123.json', cwd));
    });

    test('classifyWriteTarget identifies regular file, missing, and unsafe targets', async () => {
      const engine = createMockEngine();
      engine._files.set('/workspace/repo/.magpie-pairing-decision-abc.json', '{}');
      engine._stats.set('/workspace/repo/symlink.json', { kind: 'file', isLink: true });
      engine._stats.set('/workspace/repo/directory', { kind: 'directory', isLink: false });

      assert.strictEqual(
        await classifyWriteTarget(engine, '/workspace/repo/.magpie-pairing-decision-abc.json'),
        'regular'
      );
      assert.strictEqual(
        await classifyWriteTarget(engine, '/workspace/repo/.magpie-pairing-decision-missing.json'),
        'missing'
      );
      assert.strictEqual(
        await classifyWriteTarget(engine, '/workspace/repo/symlink.json'),
        'unsafe'
      );
      assert.strictEqual(
        await classifyWriteTarget(engine, '/workspace/repo/directory'),
        'unsafe'
      );
      // Missing engine or $.fs fails safe as 'unsafe'
      assert.strictEqual(await classifyWriteTarget(null, '/any/path'), 'unsafe');
      assert.strictEqual(await classifyWriteTarget({}, '/any/path'), 'unsafe');
    });

    test('getDecisionPath derives decision path from review path', () => {
      assert.strictEqual(
        getDecisionPath('/workspace/repo/.magpie-pairing-review-deadbeef.json'),
        '/workspace/repo/.magpie-pairing-decision-deadbeef.json'
      );
      assert.strictEqual(
        getDecisionPath('.magpie-pairing-review-123.json'),
        '.magpie-pairing-decision-123.json'
      );
      assert.strictEqual(getDecisionPath('random.json'), null);
      assert.strictEqual(getDecisionPath(''), null);
    });

    test('extractReviewPathFromCommand parses review target from bash commands', () => {
      assert.strictEqual(
        extractReviewPathFromCommand('test -f .magpie-pairing-review-abc.json'),
        '.magpie-pairing-review-abc.json'
      );
      assert.strictEqual(
        extractReviewPathFromCommand('cat /workspace/repo/.magpie-pairing-review-def456.json'),
        '/workspace/repo/.magpie-pairing-review-def456.json'
      );
      assert.strictEqual(extractReviewPathFromCommand('git status'), null);
    });
  });

  describe('Part 2 — syncDecisionToDisk & invalidateDecisionOnDisk', () => {
    test('syncDecisionToDisk writes decision JSON to confined disk location', async () => {
      const engine = createMockEngine();
      const reviewPath = '/workspace/repo/.magpie-pairing-review-test1.json';
      const decisionPath = '/workspace/repo/.magpie-pairing-decision-test1.json';
      const state: MultiAgentReviewState = {
        headSha: 'sha1',
        baseRef: 'main',
        filesChanged: 1,
        linesAdded: 5,
        linesRemoved: 1,
        findings: [
          {
            id: 'c-1',
            axis: 'correctness',
            severity: 'blocking',
            location: 'a.py:1',
            summary: 'bug',
            status: 'accepted',
          },
        ],
        injectionAttempts: [],
        activeFilter: 'all',
        selectedFindingId: null,
        overallStatus: 'ready',
        updatedAt: '',
      };

      await syncDecisionToDisk(engine, state, reviewPath, 'hash123');
      assert(engine._files.has(decisionPath));
      const written = JSON.parse(engine._files.get(decisionPath));
      assert.strictEqual(written.schema_version, 1);
      assert.strictEqual(written.head_sha, 'sha1');
      assert.strictEqual(written.source_payload_sha256, 'hash123');
      assert(written.accepted_ids.includes('c-1'));
    });

    test('syncDecisionToDisk aborts write if destination is a symlink or unsafe', async () => {
      const engine = createMockEngine();
      const reviewPath = '/workspace/repo/.magpie-pairing-review-sym.json';
      const decisionPath = '/workspace/repo/.magpie-pairing-decision-sym.json';
      engine._stats.set(decisionPath, { kind: 'file', isLink: true }); // Symlink target!

      const state: MultiAgentReviewState = {
        headSha: 'symsha',
        baseRef: 'main',
        filesChanged: 1,
        linesAdded: 1,
        linesRemoved: 0,
        findings: [],
        injectionAttempts: [],
        activeFilter: 'all',
        selectedFindingId: null,
        overallStatus: 'ready',
        updatedAt: '',
      };

      await syncDecisionToDisk(engine, state, reviewPath, 'hash');
      assert(!engine._files.has(decisionPath)); // Write was blocked
    });

    test('invalidateDecisionOnDisk marks decision as invalidated on mutating actions', async () => {
      const engine = createMockEngine();
      const reviewPath = '/workspace/repo/.magpie-pairing-review-inv.json';
      const decisionPath = '/workspace/repo/.magpie-pairing-decision-inv.json';
      engine._files.set(decisionPath, JSON.stringify({ schema_version: 1, head_sha: 'inv' }));

      await invalidateDecisionOnDisk(engine, reviewPath);
      assert(engine._files.has(decisionPath));
      const content = JSON.parse(engine._files.get(decisionPath));
      assert.strictEqual(content.invalidated, true);
      assert.strictEqual(content.head_sha, null);
    });
  });

  describe('Part 2 — handleBashToolCall IPC & Pane Ingestion', () => {
    test('intercepts review command, reads payload via $.fs.read, sets atom and opens Pane', async () => {
      const engine = createMockEngine();
      const reviewPath = '/workspace/repo/.magpie-pairing-review-ipc.json';
      const payload = {
        schema_version: 1,
        head_sha: 'sha-ipc',
        base_ref: 'main',
        files_changed: 2,
        lines_added: 20,
        lines_removed: 5,
        findings: [
          {
            id: 'c-10',
            axis: 'correctness',
            severity: 'blocking',
            location: 'src/main.py:10',
            summary: 'Null pointer dereference',
          },
        ],
        injection_attempts: [],
      };
      const rawContent = JSON.stringify(payload);
      engine._files.set(reviewPath, rawContent);

      await handleBashToolCall(engine, { command: `test -f ${reviewPath}` }, () => {});

      const state = await getMultiAgentReviewState(engine);
      assert(state !== null);
      assert.strictEqual(state.headSha, 'sha-ipc');
      assert.strictEqual(state.findings.length, 1);
      assert.strictEqual(state.findings[0].id, 'c-10');
      assert.strictEqual(state.payloadPath, reviewPath);
      assert.strictEqual(state.payloadHash, computePayloadHash(rawContent));

      // Verifies Pane was opened and UI invalidated
      assert(engine._openCalls.some((c: any) => c.component === 'Pane'));
      assert(engine._invalidateCalls.includes('ui.render'));
    });

    test('reconciles existing curated decision from disk on ingestion', async () => {
      const engine = createMockEngine();
      const reviewPath = '/workspace/repo/.magpie-pairing-review-recon.json';
      const decisionPath = '/workspace/repo/.magpie-pairing-decision-recon.json';

      const payload = {
        schema_version: 1,
        head_sha: 'recon-sha',
        base_ref: 'main',
        files_changed: 1,
        lines_added: 10,
        lines_removed: 0,
        findings: [
          { id: 'f-1', axis: 'correctness', severity: 'blocking', location: 'a.py:1', summary: 'bug1' },
          { id: 'f-2', axis: 'security', severity: 'advisory', location: 'b.py:2', summary: 'sec1' },
        ],
        injection_attempts: [],
      };
      const rawPayload = JSON.stringify(payload);
      const hash = computePayloadHash(rawPayload);

      const decision = {
        schema_version: 1,
        head_sha: 'recon-sha',
        source_payload_sha256: hash,
        accepted_ids: ['f-1'],
        dismissed_ids: ['f-2'],
        status: 'curated',
        updated_at: new Date().toISOString(),
      };

      engine._files.set(reviewPath, rawPayload);
      engine._files.set(decisionPath, JSON.stringify(decision));

      await handleBashToolCall(engine, { command: `test -f ${reviewPath}` }, () => {});

      const state = await getMultiAgentReviewState(engine);
      assert(state !== null);
      const f1 = state.findings.find((f: any) => f.id === 'f-1');
      const f2 = state.findings.find((f: any) => f.id === 'f-2');
      assert.strictEqual(f1?.status, 'accepted');
      assert.strictEqual(f2?.status, 'dismissed');
    });

    test('fails open and does not crash when payload file is unreadable or malformed', async () => {
      const engine = createMockEngine();
      const reviewPath = '/workspace/repo/.magpie-pairing-review-corrupt.json';
      engine._files.set(reviewPath, 'NOT_VALID_JSON{');

      let nextCalled = false;
      await handleBashToolCall(engine, { command: `test -f ${reviewPath}` }, () => {
        nextCalled = true;
      });
      assert(nextCalled);
      assert.strictEqual(await getMultiAgentReviewState(engine), null);
    });
  });

  describe('Part 2 — handleUiPress Interaction Routing', () => {
    test('routes accept-<id>, dismiss-<id>, and restore-<id> button clicks and writes decision', async () => {
      const engine = createMockEngine();
      const reviewPath = '/workspace/repo/.magpie-pairing-review-press.json';
      const decisionPath = '/workspace/repo/.magpie-pairing-decision-press.json';

      const initialState: MultiAgentReviewState = {
        headSha: 'press-sha',
        baseRef: 'main',
        filesChanged: 1,
        linesAdded: 5,
        linesRemoved: 1,
        payloadPath: reviewPath,
        payloadHash: 'hash-press',
        findings: [
          {
            id: 'p-1',
            axis: 'correctness',
            severity: 'blocking',
            location: 'a.py:1',
            summary: 'bug',
            status: 'pending',
          },
          {
            id: 'p-2',
            axis: 'security',
            severity: 'advisory',
            location: 'b.py:2',
            summary: 'sec',
            status: 'pending',
          },
        ],
        injectionAttempts: [],
        activeFilter: 'all',
        selectedFindingId: null,
        overallStatus: 'blocked',
        updatedAt: '',
      };
      await setMultiAgentReviewState(engine, initialState);

      // 1. Accept finding p-1
      await handleUiPress(engine, { element: 'accept-p-1' });
      let state = await getMultiAgentReviewState(engine);
      assert.strictEqual(state?.findings[0].status, 'accepted');
      assert(engine._files.has(decisionPath));
      let decision = JSON.parse(engine._files.get(decisionPath));
      assert(decision.accepted_ids.includes('p-1'));

      // 2. Dismiss finding p-2
      await handleUiPress(engine, { element: 'dismiss-p-2' });
      state = await getMultiAgentReviewState(engine);
      assert.strictEqual(state?.findings[1].status, 'dismissed');
      decision = JSON.parse(engine._files.get(decisionPath));
      assert(decision.dismissed_ids.includes('p-2'));

      // 3. Restore finding p-1
      await handleUiPress(engine, { element: 'restore-p-1' });
      state = await getMultiAgentReviewState(engine);
      assert.strictEqual(state?.findings[0].status, 'pending');

      // 4. Filter tab navigation
      await handleUiPress(engine, { element: 'filter-correctness' });
      state = await getMultiAgentReviewState(engine);
      assert.strictEqual(state?.activeFilter, 'correctness');
    });

    test('handleUiPress ignores unknown elements or null state safely', async () => {
      const engine = createMockEngine();
      await handleUiPress(engine, { element: 'unknown-btn' });
      assert.strictEqual(await getMultiAgentReviewState(engine), null);
    });
  });
});
