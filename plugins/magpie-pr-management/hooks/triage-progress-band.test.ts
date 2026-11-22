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
import type { TriageProgressState } from './types.js';
import {
  computeRemainingCount,
  extractPrNumberFromCommand,
  formatTriageSummary,
  isConfinedProgressPath,
  parseTriageProgressPayload,
  processTriageCommand,
  renderTriageProgressBandComponent,
  sanitizePrTitle,
} from './triage-progress-band.js';
import {
  getTriageProgressState,
  handleBashToolCall,
  handleRenderAbovePrompt,
  setTriageProgressState,
} from './review-findings.js';

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
assert.ok = assert;

function createMockEngine(overrides: any = {}): any {
  const store = new Map<string, any>();
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
      invalidate: () => {},
      resolve: () => ({
        Box: (p: any) => ({ type: 'Box', ...p }),
        Text: (p: any) => ({ type: 'Text', ...p }),
      }),
    },
    session: {
      cwd: async () => '/workspace/repo',
      root: async () => '/workspace/repo',
    },
    ...overrides,
  };
}

describe('triage-progress-band mod', () => {
  describe('ambient type assignability', () => {
    test('TriageProgressState satisfies PluginState ambient schema', () => {
      const state: TriageProgressState = {
        skill: 'pr-triage',
        total: 10,
        evaluated: 2,
        dispositions: { labeled: 1, nudged: 1, closed: 0, drafted: 0, approved: 0 },
        remaining: 8,
        currentPr: { number: 42, title: 'fix: edge case' },
        processedPrs: [42],
        status: 'running',
        updatedAt: '2026-11-22T00:00:00.000Z',
        renderCount: 0,
      };
      assert.strictEqual(state.skill, 'pr-triage');
      assert.strictEqual(state.processedPrs?.length, 1);
    });
  });

  describe('sanitizePrTitle', () => {
    test('strips ANSI CSI and OSC escape sequences', () => {
      const malicious = '\x1b[31;1mRed Alert\x1b[0m \x1b]50;SetTitle\x07Fix Core';
      const clean = sanitizePrTitle(malicious);
      assert.strictEqual(clean, 'Red Alert Fix Core');
    });

    test('strips Unicode bidirectional overrides, format marks, and paragraph/line separators', () => {
      const spoofed = 'Fix\u202Ereversed\u200B\uFEFF\u061C\u2028line\u2029title';
      const clean = sanitizePrTitle(spoofed);
      assert.strictEqual(clean, 'Fixreversedlinetitle');
    });

    test('strips C0/C1 control characters and HTML/markdown characters', () => {
      const dirty = '`Fix` <script>alert("xss")</script>\x00\x1f\x7f';
      const clean = sanitizePrTitle(dirty);
      assert.strictEqual(clean, 'Fix scriptalert(xss)/script');
    });

    test('truncates strings exceeding maxLen', () => {
      const longTitle = 'A'.repeat(80);
      const clean = sanitizePrTitle(longTitle, 40);
      assert.strictEqual(clean.length, 40);
      assert.strictEqual(clean, 'A'.repeat(40));
    });

    test('returns empty string for non-string or null inputs', () => {
      assert.strictEqual(sanitizePrTitle(null), '');
      assert.strictEqual(sanitizePrTitle(undefined), '');
      assert.strictEqual(sanitizePrTitle(12345), '');
      assert.strictEqual(sanitizePrTitle({}), '');
    });
  });

  describe('computeRemainingCount', () => {
    test('computes remaining PRs accurately', () => {
      assert.strictEqual(computeRemainingCount(24, 8), 16);
      assert.strictEqual(computeRemainingCount(10, 10), 0);
    });

    test('clamps remaining at 0 when evaluated exceeds total', () => {
      assert.strictEqual(computeRemainingCount(10, 15), 0);
    });

    test('handles negative and non-finite values safely', () => {
      assert.strictEqual(computeRemainingCount(-5, 2), 0);
      assert.strictEqual(computeRemainingCount(10, -3), 10);
      assert.strictEqual(computeRemainingCount(NaN, 5), 0);
    });

    test('floors non-integer numbers', () => {
      assert.strictEqual(computeRemainingCount(20.8, 5.2), 15);
    });
  });

  describe('extractPrNumberFromCommand', () => {
    test('extracts PR number when it immediately follows the subcommand', () => {
      assert.strictEqual(extractPrNumberFromCommand('gh pr view 101'), 101);
      assert.strictEqual(extractPrNumberFromCommand('gh pr checkout 202'), 202);
      assert.strictEqual(extractPrNumberFromCommand('gh pr close 303'), 303);
    });

    test('extracts PR number when flags precede the positional argument', () => {
      assert.strictEqual(extractPrNumberFromCommand('gh pr close -c "stale" 404'), 404);
      assert.strictEqual(extractPrNumberFromCommand('gh pr close --comment "not reproducible" 505'), 505);
      assert.strictEqual(extractPrNumberFromCommand('gh pr edit --add-label "area:core" 606'), 606);
      assert.strictEqual(extractPrNumberFromCommand('gh pr comment --body "Please rebase" 707'), 707);
    });

    test('extracts quoted PR numbers, quoted URLs, and handles global repo flags', () => {
      assert.strictEqual(extractPrNumberFromCommand('gh pr view "404"'), 404);
      assert.strictEqual(extractPrNumberFromCommand("gh pr view '505'"), 505);
      assert.strictEqual(
        extractPrNumberFromCommand('gh pr view "https://github.com/apache/magpie/pull/606"'),
        606
      );
      assert.strictEqual(
        extractPrNumberFromCommand('gh -R apache/magpie pr view 707'),
        707
      );
      assert.strictEqual(
        extractPrNumberFromCommand('gh --repo apache/magpie pr close 808'),
        808
      );
    });

    test('respects subcommand-specific boolean flags like -c in gh pr view', () => {
      // In gh pr view, -c is --comments (boolean flag, does not take argument)
      assert.strictEqual(extractPrNumberFromCommand('gh pr view -c 909'), 909);
      assert.strictEqual(extractPrNumberFromCommand('gh pr view --comments 1010'), 1010);
      assert.strictEqual(extractPrNumberFromCommand('gh pr view -w 1111'), 1111);
    });

    test('returns null for non-PR commands or missing number', () => {
      assert.strictEqual(extractPrNumberFromCommand('gh issue view 101'), null);
      assert.strictEqual(extractPrNumberFromCommand('gh pr list'), null);
      assert.strictEqual(extractPrNumberFromCommand(''), null);
      assert.strictEqual(extractPrNumberFromCommand(null as any), null);
    });
  });

  describe('parseTriageProgressPayload', () => {
    test('parses a valid JSON payload string', () => {
      const raw = JSON.stringify({
        skill: 'pr-triage',
        total: 20,
        evaluated: 5,
        dispositions: { labeled: 3, nudged: 1, closed: 1, drafted: 0, approved: 0 },
        currentPr: { number: 101, title: 'fix(core): parser bug' },
        processedPrs: [101],
        status: 'running',
      });
      const result = parseTriageProgressPayload(raw);
      assert.ok(result.state);
      assert.strictEqual(result.state.total, 20);
      assert.strictEqual(result.state.evaluated, 5);
      assert.strictEqual(result.state.remaining, 15);
      assert.strictEqual(result.state.dispositions.labeled, 3);
      assert.strictEqual(result.state.currentPr?.number, 101);
      assert.strictEqual(result.state.currentPr?.title, 'fix(core): parser bug');
      assert.strictEqual(result.state.processedPrs?.length, 1);
      assert.strictEqual(result.state.status, 'running');
    });

    test('handles parsed object directly', () => {
      const obj = {
        skill: 'pr-stale-sweep',
        total: 12,
        evaluated: 12,
        dispositions: { labeled: 0, nudged: 8, closed: 4, drafted: 0, approved: 0 },
      };
      const result = parseTriageProgressPayload(obj);
      assert.ok(result.state);
      assert.strictEqual(result.state.skill, 'pr-stale-sweep');
      assert.strictEqual(result.state.total, 12);
      assert.strictEqual(result.state.evaluated, 12);
      assert.strictEqual(result.state.remaining, 0);
      assert.strictEqual(result.state.status, 'completed');
    });

    test('rejects empty or malformed inputs', () => {
      assert.strictEqual(parseTriageProgressPayload('').state, null);
      assert.strictEqual(parseTriageProgressPayload(null).state, null);
      assert.strictEqual(parseTriageProgressPayload('{invalid json').state, null);
      assert.strictEqual(parseTriageProgressPayload(12345).state, null);
    });

    test('sanitizes malicious PR titles within currentPr payload', () => {
      const payload = {
        total: 10,
        evaluated: 1,
        currentPr: { number: 42, title: '\x1b[31mInjected\x1b[0m <script>' },
      };
      const result = parseTriageProgressPayload(payload);
      assert.ok(result.state?.currentPr);
      assert.strictEqual(result.state.currentPr.title, 'Injected script');
    });

    test('enforces defensive bound on processedPrs array length', () => {
      const largeArray = Array.from({ length: 1500 }, (_, i) => i + 1);
      const payload = {
        total: 2000,
        evaluated: 1000,
        processedPrs: largeArray,
      };
      const result = parseTriageProgressPayload(payload);
      assert.ok(result.state?.processedPrs);
      assert.strictEqual(result.state.processedPrs.length, 1000);
    });
  });

  describe('formatTriageSummary', () => {
    test('formats evaluated, active dispositions, and remaining count', () => {
      const state: TriageProgressState = {
        skill: 'pr-triage',
        total: 24,
        evaluated: 8,
        dispositions: { labeled: 4, nudged: 2, closed: 1, drafted: 1, approved: 0 },
        remaining: 16,
        status: 'running',
      };
      const summary = formatTriageSummary(state);
      assert.strictEqual(
        summary,
        '8/24 evaluated \u00B7 4 labeled \u00B7 2 nudged \u00B7 1 closed \u00B7 1 drafted \u00B7 16 remaining'
      );
    });

    test('omits zero-count dispositions cleanly', () => {
      const state: TriageProgressState = {
        skill: 'pr-triage',
        total: 10,
        evaluated: 2,
        dispositions: { labeled: 2, nudged: 0, closed: 0, drafted: 0, approved: 0 },
        remaining: 8,
        status: 'running',
      };
      const summary = formatTriageSummary(state);
      assert.strictEqual(summary, '2/10 evaluated \u00B7 2 labeled \u00B7 8 remaining');
    });
  });

  describe('renderTriageProgressBandComponent', () => {
    const mockHelpers = {
      Box: (props: any) => ({ type: 'Box', ...props }),
      Text: (props: any) => ({ type: 'Text', ...props }),
    };

    test('returns null if helpers are missing', () => {
      const state: TriageProgressState = {
        skill: 'pr-triage',
        total: 10,
        evaluated: 2,
        dispositions: { labeled: 1, nudged: 0, closed: 0, drafted: 0, approved: 0 },
        remaining: 8,
        status: 'running',
      };
      assert.strictEqual(renderTriageProgressBandComponent(state, {} as any), null);
    });

    test('renders running band with badge and current PR details', () => {
      const state: TriageProgressState = {
        skill: 'pr-triage',
        total: 20,
        evaluated: 4,
        dispositions: { labeled: 2, nudged: 1, closed: 1, drafted: 0, approved: 0 },
        remaining: 16,
        currentPr: { number: 404, title: 'fix: edge case' },
        status: 'running',
      };
      const rendered = renderTriageProgressBandComponent(state, mockHelpers);
      assert.ok(rendered);
      assert.strictEqual(rendered.type, 'Box');
      assert.strictEqual(rendered.children[0].children[0], '[PR Triage] ');
      assert.strictEqual(rendered.children[0].color, 'cyan');
      assert.strictEqual(rendered.children[2].children[0], ' (current: #404 fix: edge case)');
    });

    test('renders completed band with checkmark when remaining is 0', () => {
      const state: TriageProgressState = {
        skill: 'pr-stale-sweep',
        total: 15,
        evaluated: 15,
        dispositions: { labeled: 5, nudged: 7, closed: 3, drafted: 0, approved: 0 },
        remaining: 0,
        status: 'completed',
      };
      const rendered = renderTriageProgressBandComponent(state, mockHelpers);
      assert.ok(rendered);
      assert.strictEqual(rendered.children[0].children[0], '[PR Stale Sweep] ');
      assert.strictEqual(rendered.children[1].color, 'green');
      assert.ok(rendered.children[1].children[0].includes('Sweep complete: 15/15 evaluated'));
    });
  });

  describe('processTriageCommand', () => {
    test('bootstraps state on gh pr list with limit flag', () => {
      const command = 'gh pr list --state open --limit 25';
      const state = processTriageCommand(command, null);
      assert.ok(state);
      assert.strictEqual(state.total, 25);
      assert.strictEqual(state.evaluated, 0);
      assert.strictEqual(state.remaining, 25);
      assert.strictEqual(state.status, 'running');
    });

    test('supports inline equals syntax for candidate limit flags', () => {
      const state1 = processTriageCommand('gh pr list --limit=35', null);
      assert.ok(state1);
      assert.strictEqual(state1.total, 35);

      const state2 = processTriageCommand('gh pr list -L=50', null);
      assert.ok(state2);
      assert.strictEqual(state2.total, 50);
    });

    test('re-anchors candidate limit when gh pr list is re-run during active sweep', () => {
      const initial: TriageProgressState = {
        skill: 'pr-triage',
        total: 10,
        evaluated: 3,
        dispositions: { labeled: 2, nudged: 1, closed: 0, drafted: 0, approved: 0 },
        remaining: 7,
        processedPrs: [101, 102, 103],
        status: 'running',
      };
      const reAnchored = processTriageCommand('gh pr list --limit 20', initial);
      assert.ok(reAnchored);
      assert.strictEqual(reAnchored.total, 20);
      assert.strictEqual(reAnchored.remaining, 17);
    });

    test('preserves monotonic evaluated progress even if processedPrs was omitted', () => {
      const initial: TriageProgressState = {
        skill: 'pr-triage',
        total: 10,
        evaluated: 5,
        dispositions: { labeled: 5, nudged: 0, closed: 0, drafted: 0, approved: 0 },
        remaining: 5,
        processedPrs: [],
        status: 'running',
      };
      const updated = processTriageCommand('gh pr close 999', initial);
      assert.ok(updated);
      assert.strictEqual(updated.evaluated, 6);
      assert.strictEqual(updated.remaining, 4);
    });

    test('updates currentPr on gh pr view command', () => {
      const initial: TriageProgressState = {
        skill: 'pr-triage',
        total: 5,
        evaluated: 1,
        dispositions: { labeled: 1, nudged: 0, closed: 0, drafted: 0, approved: 0 },
        remaining: 4,
        processedPrs: [100],
        status: 'running',
      };
      const updated = processTriageCommand('gh pr view 777 --json title', initial);
      assert.ok(updated);
      assert.strictEqual(updated.currentPr?.number, 777);
    });

    test('increments labeled disposition and evaluates PR once', () => {
      const initial: TriageProgressState = {
        skill: 'pr-triage',
        total: 5,
        evaluated: 1,
        dispositions: { labeled: 1, nudged: 0, closed: 0, drafted: 0, approved: 0 },
        remaining: 4,
        processedPrs: [100],
        status: 'running',
      };
      const updated = processTriageCommand('gh pr edit 777 --add-label "area:core"', initial);
      assert.ok(updated);
      assert.strictEqual(updated.dispositions.labeled, 2);
      assert.strictEqual(updated.evaluated, 2);
      assert.strictEqual(updated.remaining, 3);
      assert.ok(updated.processedPrs?.includes(777));
    });

    test('deduplicates multiple actions on the same PR without double-incrementing evaluated', () => {
      const initial: TriageProgressState = {
        skill: 'pr-triage',
        total: 5,
        evaluated: 2,
        dispositions: { labeled: 1, nudged: 1, closed: 0, drafted: 0, approved: 0 },
        remaining: 3,
        processedPrs: [100, 777],
        status: 'running',
      };
      // Second operation on already processed PR #777
      const updated = processTriageCommand('gh pr comment --body "Please rebase" 777', initial);
      assert.ok(updated);
      assert.strictEqual(updated.dispositions.nudged, 2);
      assert.strictEqual(updated.evaluated, 2); // Unchanged!
      assert.strictEqual(updated.remaining, 3); // Unchanged!
    });

    test('completes sweep when all distinct PRs are evaluated', () => {
      const initial: TriageProgressState = {
        skill: 'pr-triage',
        total: 2,
        evaluated: 1,
        dispositions: { labeled: 1, nudged: 0, closed: 0, drafted: 0, approved: 0 },
        remaining: 1,
        processedPrs: [100],
        status: 'running',
      };
      const updated = processTriageCommand('gh pr close -c "stale" 101', initial);
      assert.ok(updated);
      assert.strictEqual(updated.dispositions.closed, 1);
      assert.strictEqual(updated.evaluated, 2);
      assert.strictEqual(updated.remaining, 0);
      assert.strictEqual(updated.status, 'completed');
    });
  });

  describe('isConfinedProgressPath', () => {
    test('accepts valid filename residing strictly within workspace cwd', () => {
      assert.strictEqual(
        isConfinedProgressPath('/workspace/repo/.magpie-pr-triage-session123.json', '/workspace/repo'),
        true
      );
    });

    test('rejects sibling directory prefix collision (/workspace/repo-other)', () => {
      assert.strictEqual(
        isConfinedProgressPath('/workspace/repo-other/.magpie-pr-triage-test.json', '/workspace/repo'),
        false
      );
    });

    test('rejects path traversal attempts with ..', () => {
      assert.strictEqual(
        isConfinedProgressPath('/workspace/repo/../../etc/.magpie-pr-triage-test.json', '/workspace/repo'),
        false
      );
    });

    test('fails closed when cwd is null or missing', () => {
      assert.strictEqual(isConfinedProgressPath('/workspace/repo/.magpie-pr-triage-test.json', null), false);
      assert.strictEqual(isConfinedProgressPath('/workspace/repo/.magpie-pr-triage-test.json', undefined), false);
      assert.strictEqual(isConfinedProgressPath('/workspace/repo/.magpie-pr-triage-test.json', ''), false);
    });
  });

  describe('handleRenderAbovePrompt', () => {
    test('passes through to next when triage state is null', async () => {
      const test$ = createMockEngine();

      let nextCalled = false;
      await handleRenderAbovePrompt(test$, { component: 'AbovePrompt' }, () => {
        nextCalled = true;
      });
      assert.strictEqual(nextCalled, true);
    });

    test('renders Box purely without mutating state or triggering invalidations', async () => {
      const test$ = createMockEngine();
      const initial: TriageProgressState = {
        skill: 'pr-triage',
        total: 5,
        evaluated: 5,
        dispositions: { labeled: 3, nudged: 1, closed: 1, drafted: 0, approved: 0 },
        remaining: 0,
        status: 'completed',
      };
      await setTriageProgressState(test$, initial);

      let nextCalled = false;
      const rendered = await handleRenderAbovePrompt(test$, { component: 'AbovePrompt' }, () => {
        nextCalled = true;
      });

      assert.ok(rendered);
      assert.strictEqual(rendered.type, 'Box');
      assert.strictEqual(nextCalled, false); // Consumed by Box render

      // Verify state was NOT mutated during rendering
      const stateAfter = await getTriageProgressState(test$);
      assert.ok(stateAfter);
      assert.strictEqual(stateAfter.status, 'completed');
    });
  });

  describe('handleBashToolCall integration', () => {
    test('updates triage progress state on gh pr commands', async () => {
      const test$ = createMockEngine();
      await setTriageProgressState(test$, {
        skill: 'pr-triage',
        total: 10,
        evaluated: 0,
        dispositions: { labeled: 0, nudged: 0, closed: 0, drafted: 0, approved: 0 },
        remaining: 10,
        processedPrs: [],
        status: 'running',
      });

      let nextCalled = false;
      await handleBashToolCall(test$, { command: 'gh pr view 42' }, () => {
        nextCalled = true;
      });

      assert.strictEqual(nextCalled, true);
      const state = await getTriageProgressState(test$);
      assert.strictEqual(state?.currentPr?.number, 42);
    });

    test('clears completed triage state when an unrelated command executes', async () => {
      const test$ = createMockEngine();
      await setTriageProgressState(test$, {
        skill: 'pr-triage',
        total: 5,
        evaluated: 5,
        dispositions: { labeled: 3, nudged: 1, closed: 1, drafted: 0, approved: 0 },
        remaining: 0,
        status: 'completed',
      });

      let nextCalled = false;
      await handleBashToolCall(test$, { command: 'git commit -m "docs: finish"' }, () => {
        nextCalled = true;
      });

      assert.strictEqual(nextCalled, true);
      const state = await getTriageProgressState(test$);
      assert.strictEqual(state, null);
    });

    test('clears completed triage state and immediately bootstraps new sweep on gh pr list', async () => {
      const test$ = createMockEngine();
      await setTriageProgressState(test$, {
        skill: 'pr-triage',
        total: 5,
        evaluated: 5,
        dispositions: { labeled: 3, nudged: 1, closed: 1, drafted: 0, approved: 0 },
        remaining: 0,
        status: 'completed',
      });

      let nextCalled = false;
      await handleBashToolCall(test$, { command: 'gh pr list --limit 15' }, () => {
        nextCalled = true;
      });

      assert.strictEqual(nextCalled, true);
      const state = await getTriageProgressState(test$);
      assert.ok(state);
      assert.strictEqual(state.status, 'running');
      assert.strictEqual(state.total, 15);
      assert.strictEqual(state.evaluated, 0);
      assert.strictEqual(state.remaining, 15);
    });
  });
});
