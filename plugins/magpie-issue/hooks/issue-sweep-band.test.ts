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
import type { IssueSweepProgressState } from './types.js';
import {
  computeRemainingCount,
  extractIssueNumberFromCommand,
  formatIssueSweepSummary,
  isConfinedProgressPath,
  parseIssueProgressPayload,
  processIssueCommand,
  renderIssueSweepProgressBandComponent,
  sanitizeIssueTitle,
} from './issue-sweep-band.js';
import {
  getIssueSweepProgressState,
  handleBashToolCall,
  handleRenderAbovePrompt,
  setIssueSweepProgressState,
} from './duplicate-picker.js';

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

describe('issue-sweep-band mod', () => {
  describe('ambient type assignability', () => {
    test('IssueSweepProgressState satisfies PluginState ambient schema', () => {
      const state: IssueSweepProgressState = {
        skill: 'issue-triage',
        total: 10,
        evaluated: 3,
        dispositions: { labeled: 2, nudged: 1, closed: 0, duplicate: 0, other: 0 },
        remaining: 7,
        currentIssue: { number: 101, title: 'Memory leak on worker stop' },
        processedIssues: [101, 102, 103],
        status: 'running',
        updatedAt: '2026-11-24T12:00:00Z',
        renderCount: 0,
      };
      assert(state.total === 10);
      assert.strictEqual(state.dispositions.labeled, 2);
    });
  });

  describe('sanitizeIssueTitle', () => {
    test('strips ANSI CSI and OSC sequences', () => {
      const untrusted = '\x1b[31;1mMalicious\x1b[0m \x1b]0;Title\x07Issue';
      assert.strictEqual(sanitizeIssueTitle(untrusted), 'Malicious Issue');
    });

    test('strips Unicode bidirectional overrides and format controls', () => {
      const untrusted = 'Safe\u202E\u2066reversed\u2069\u200Etitle\u200Bzero';
      assert.strictEqual(sanitizeIssueTitle(untrusted), 'Safereversedtitlezero');
    });

    test('strips C0 and C1 control characters and line separators', () => {
      const untrusted = 'Line1\r\nLine2\x00\x1f\x7f';
      assert.strictEqual(sanitizeIssueTitle(untrusted), 'Line1Line2');
    });

    test('strips markdown delimiters and HTML tags', () => {
      const untrusted = '`Code` <script>alert(1)</script> "quoted"';
      assert.strictEqual(sanitizeIssueTitle(untrusted), 'Code scriptalert(1)/script quoted');
    });

    test('truncates at maxLen boundary', () => {
      const longTitle = 'A'.repeat(60);
      assert.strictEqual(sanitizeIssueTitle(longTitle, 40), 'A'.repeat(40));
    });

    test('returns empty string on non-string input', () => {
      assert.strictEqual(sanitizeIssueTitle(null), '');
      assert.strictEqual(sanitizeIssueTitle(undefined), '');
      assert.strictEqual(sanitizeIssueTitle(12345), '');
    });
  });

  describe('computeRemainingCount', () => {
    test('computes positive remaining count', () => {
      assert.strictEqual(computeRemainingCount(20, 5), 15);
    });

    test('clamps at 0 on over-evaluation', () => {
      assert.strictEqual(computeRemainingCount(10, 15), 0);
    });

    test('handles non-finite or negative total', () => {
      assert.strictEqual(computeRemainingCount(-5, 2), 0);
      assert.strictEqual(computeRemainingCount(NaN, 2), 0);
    });

    test('handles negative or invalid evaluated count', () => {
      assert.strictEqual(computeRemainingCount(10, -3), 10);
      assert.strictEqual(computeRemainingCount(10, NaN), 10);
    });
  });

  describe('extractIssueNumberFromCommand', () => {
    test('extracts unquoted issue number', () => {
      assert.strictEqual(extractIssueNumberFromCommand('gh issue view 123'), 123);
    });

    test('extracts #-prefixed issue number', () => {
      assert.strictEqual(extractIssueNumberFromCommand('gh issue view #456'), 456);
    });

    test('extracts quoted issue number', () => {
      assert.strictEqual(extractIssueNumberFromCommand('gh issue view "789"'), 789);
      assert.strictEqual(extractIssueNumberFromCommand("gh issue view '#101'"), 101);
    });

    test('handles options before positional number', () => {
      assert.strictEqual(
        extractIssueNumberFromCommand('gh issue view --repo apache/magpie 123'),
        123
      );
      assert.strictEqual(
        extractIssueNumberFromCommand('gh issue close -r apache/magpie --reason "not planned" 456'),
        456
      );
    });

    test('handles options after positional number', () => {
      assert.strictEqual(
        extractIssueNumberFromCommand('gh issue view 123 -R apache/magpie'),
        123
      );
    });

    test('ignores issue numbers inside flag arguments like --body or --comment', () => {
      assert.strictEqual(
        extractIssueNumberFromCommand('gh issue comment 123 --body "duplicate of #999"'),
        123
      );
      assert.strictEqual(
        extractIssueNumberFromCommand('gh issue edit 456 --add-label "bug #12"'),
        456
      );
    });

    test('extracts issue number from GitHub URL', () => {
      assert.strictEqual(
        extractIssueNumberFromCommand('gh issue view https://github.com/apache/magpie/issues/987'),
        987
      );
    });

    test('returns null for non-issue or malformed commands', () => {
      assert.strictEqual(extractIssueNumberFromCommand('gh pr view 123'), null);
      assert.strictEqual(extractIssueNumberFromCommand('git status'), null);
      assert.strictEqual(extractIssueNumberFromCommand(''), null);
      assert.strictEqual(extractIssueNumberFromCommand('gh issue list'), null);
    });
  });

  describe('parseIssueProgressPayload', () => {
    test('parses valid payload object', () => {
      const raw = {
        skill: 'issue-stale-sweep',
        total: 50,
        evaluated: 10,
        dispositions: { labeled: 5, nudged: 3, closed: 2, duplicate: 0, other: 0 },
        currentIssue: { number: 101, title: 'Bug in parser' },
        processedIssues: [101, 102],
        status: 'running',
      };
      const res = parseIssueProgressPayload(raw);
      assert(res.state !== null);
      assert.strictEqual(res.state.skill, 'issue-stale-sweep');
      assert.strictEqual(res.state.total, 50);
      assert.strictEqual(res.state.evaluated, 10);
      assert.strictEqual(res.state.remaining, 40);
      assert.strictEqual(res.state.dispositions.labeled, 5);
      assert.strictEqual(res.state.dispositions.nudged, 3);
      assert.strictEqual(res.state.dispositions.closed, 2);
      assert.strictEqual(res.state.currentIssue?.number, 101);
      assert.strictEqual(res.state.currentIssue?.title, 'Bug in parser');
      assert.strictEqual(res.state.processedIssues.length, 2);
    });

    test('parses valid JSON string', () => {
      const json = JSON.stringify({
        skill: 'issue-triage',
        total: 10,
        evaluated: 10,
      });
      const res = parseIssueProgressPayload(json);
      assert(res.state !== null);
      assert.strictEqual(res.state.status, 'completed');
      assert.strictEqual(res.state.remaining, 0);
    });

    test('returns error on empty or malformed payload', () => {
      assert.strictEqual(parseIssueProgressPayload(null).state, null);
      assert.strictEqual(parseIssueProgressPayload('{bad json').state, null);
      assert.strictEqual(parseIssueProgressPayload(123).state, null);
    });

    test('bounds processedIssues to 1000 items', () => {
      const hugeList = Array.from({ length: 1500 }, (_, i) => i + 1);
      const res = parseIssueProgressPayload({ total: 2000, evaluated: 1500, processedIssues: hugeList });
      assert(res.state !== null);
      assert.strictEqual(res.state.processedIssues.length, 1000);
    });
  });

  describe('formatIssueSweepSummary', () => {
    test('formats full disposition breakdown', () => {
      const state: IssueSweepProgressState = {
        skill: 'issue-triage',
        total: 25,
        evaluated: 10,
        dispositions: { labeled: 4, nudged: 3, closed: 2, duplicate: 1, other: 0 },
        remaining: 15,
        currentIssue: null,
        processedIssues: [],
        status: 'running',
        updatedAt: '2026-11-24T12:00:00Z',
        renderCount: 0,
      };
      const text = formatIssueSweepSummary(state);
      assert.strictEqual(
        text,
        '10/25 evaluated \u00B7 4 labeled \u00B7 3 nudged \u00B7 2 closed \u00B7 1 duplicate \u00B7 15 remaining'
      );
    });

    test('omits zero-count dispositions cleanly', () => {
      const state: IssueSweepProgressState = {
        skill: 'issue-stale-sweep',
        total: 10,
        evaluated: 2,
        dispositions: { labeled: 0, nudged: 2, closed: 0, duplicate: 0, other: 0 },
        remaining: 8,
        currentIssue: null,
        processedIssues: [],
        status: 'running',
        updatedAt: '2026-11-24T12:00:00Z',
        renderCount: 0,
      };
      const text = formatIssueSweepSummary(state);
      assert.strictEqual(text, '2/10 evaluated \u00B7 2 nudged \u00B7 8 remaining');
    });
  });

  describe('renderIssueSweepProgressBandComponent', () => {
    const mockHelpers = {
      Box: (props: any) => ({ type: 'Box', ...props }),
      Text: (props: any) => ({ type: 'Text', ...props }),
    };

    test('returns null if helpers missing', () => {
      const state: IssueSweepProgressState = {
        skill: 'issue-triage',
        total: 10,
        evaluated: 0,
        dispositions: { labeled: 0, nudged: 0, closed: 0, duplicate: 0, other: 0 },
        remaining: 10,
        currentIssue: null,
        processedIssues: [],
        status: 'running',
        updatedAt: '',
        renderCount: 0,
      };
      assert.strictEqual(renderIssueSweepProgressBandComponent(state, {} as any), null);
    });

    test('renders running state with cyan tag and current issue suffix', () => {
      const state: IssueSweepProgressState = {
        skill: 'issue-triage',
        total: 20,
        evaluated: 5,
        dispositions: { labeled: 3, nudged: 2, closed: 0, duplicate: 0, other: 0 },
        remaining: 15,
        currentIssue: { number: 42, title: 'Flaky test' },
        processedIssues: [42],
        status: 'running',
        updatedAt: '',
        renderCount: 0,
      };
      const rendered = renderIssueSweepProgressBandComponent(state, mockHelpers);
      assert(rendered !== null);
      assert.strictEqual(rendered.type, 'Box');
      assert.strictEqual(rendered.children[0].children[0], '[Issue Triage] ');
      assert.strictEqual(rendered.children[0].color, 'cyan');
      assert(rendered.children[1].children[0].includes('5/20 evaluated'));
      assert(rendered.children[2].children[0].includes('(current: #42 Flaky test)'));
      assert.strictEqual(rendered.children[2].dim, true);
    });

    test('renders completed state with green checkmark', () => {
      const state: IssueSweepProgressState = {
        skill: 'issue-stale-sweep',
        total: 15,
        evaluated: 15,
        dispositions: { labeled: 0, nudged: 10, closed: 5, duplicate: 0, other: 0 },
        remaining: 0,
        currentIssue: null,
        processedIssues: [],
        status: 'completed',
        updatedAt: '',
        renderCount: 0,
      };
      const rendered = renderIssueSweepProgressBandComponent(state, mockHelpers);
      assert(rendered !== null);
      assert.strictEqual(rendered.children[0].children[0], '[Issue Stale Sweep] ');
      assert(rendered.children[1].children[0].includes('\u2713 Sweep complete: 15/15 evaluated'));
      assert.strictEqual(rendered.children[1].color, 'green');
    });
  });

  describe('processIssueCommand', () => {
    test('initializes state on gh issue list with limit', () => {
      const state1 = processIssueCommand('gh issue list --limit=35', null);
      assert(state1 !== undefined && state1 !== null);
      assert.strictEqual(state1.total, 35);
      assert.strictEqual(state1.remaining, 35);
      assert.strictEqual(state1.skill, 'issue-triage');

      const state2 = processIssueCommand('gh issue list -L 50', null);
      assert(state2 !== undefined && state2 !== null);
      assert.strictEqual(state2.total, 50);
    });

    test('initializes stale-sweep on issue-stale-sweep invocation', () => {
      const state = processIssueCommand('issue-stale-sweep', null);
      assert(state !== undefined && state !== null);
      assert.strictEqual(state.skill, 'issue-stale-sweep');
      assert.strictEqual(state.total, 10);
    });

    test('re-anchors limit on subsequent gh issue list', () => {
      const initial: IssueSweepProgressState = {
        skill: 'issue-triage',
        total: 10,
        evaluated: 3,
        dispositions: { labeled: 3, nudged: 0, closed: 0, duplicate: 0, other: 0 },
        remaining: 7,
        currentIssue: null,
        processedIssues: [1, 2, 3],
        status: 'running',
        updatedAt: '',
        renderCount: 0,
      };
      const reAnchored = processIssueCommand('gh issue list --limit 20', initial);
      assert(reAnchored !== undefined && reAnchored !== null);
      assert.strictEqual(reAnchored.total, 20);
      assert.strictEqual(reAnchored.remaining, 17);
    });

    test('updates currentIssue focus on gh issue view', () => {
      const initial: IssueSweepProgressState = {
        skill: 'issue-triage',
        total: 10,
        evaluated: 0,
        dispositions: { labeled: 0, nudged: 0, closed: 0, duplicate: 0, other: 0 },
        remaining: 10,
        currentIssue: null,
        processedIssues: [],
        status: 'running',
        updatedAt: '',
        renderCount: 0,
      };
      const updated = processIssueCommand('gh issue view 777 --json title', initial);
      assert(updated !== undefined && updated !== null);
      assert.strictEqual(updated.currentIssue?.number, 777);
    });

    test('increments labeled disposition and evaluates issue', () => {
      const initial: IssueSweepProgressState = {
        skill: 'issue-triage',
        total: 10,
        evaluated: 0,
        dispositions: { labeled: 0, nudged: 0, closed: 0, duplicate: 0, other: 0 },
        remaining: 10,
        currentIssue: null,
        processedIssues: [],
        status: 'running',
        updatedAt: '',
        renderCount: 0,
      };
      const updated = processIssueCommand('gh issue edit 777 --add-label "area:core"', initial);
      assert(updated !== undefined && updated !== null);
      assert.strictEqual(updated.dispositions.labeled, 1);
      assert.strictEqual(updated.evaluated, 1);
      assert.strictEqual(updated.remaining, 9);
      assert(updated.processedIssues.includes(777));
    });

    test('increments nudged disposition and evaluates issue on comment', () => {
      const initial: IssueSweepProgressState = {
        skill: 'issue-stale-sweep',
        total: 5,
        evaluated: 0,
        dispositions: { labeled: 0, nudged: 0, closed: 0, duplicate: 0, other: 0 },
        remaining: 5,
        currentIssue: null,
        processedIssues: [],
        status: 'running',
        updatedAt: '',
        renderCount: 0,
      };
      const updated = processIssueCommand('gh issue comment --body "Please rebase" 777', initial);
      assert(updated !== undefined && updated !== null);
      assert.strictEqual(updated.dispositions.nudged, 1);
      assert.strictEqual(updated.evaluated, 1);
      assert.strictEqual(updated.remaining, 4);
    });

    test('increments closed disposition and completes sweep on last issue', () => {
      const initial: IssueSweepProgressState = {
        skill: 'issue-stale-sweep',
        total: 1,
        evaluated: 0,
        dispositions: { labeled: 0, nudged: 0, closed: 0, duplicate: 0, other: 0 },
        remaining: 1,
        currentIssue: null,
        processedIssues: [],
        status: 'running',
        updatedAt: '',
        renderCount: 0,
      };
      const updated = processIssueCommand('gh issue close -c "stale" 101', initial);
      assert(updated !== undefined && updated !== null);
      assert.strictEqual(updated.dispositions.closed, 1);
      assert.strictEqual(updated.evaluated, 1);
      assert.strictEqual(updated.remaining, 0);
      assert.strictEqual(updated.status, 'completed');
    });

    test('deduplicates actions on the same issue ID', () => {
      const initial: IssueSweepProgressState = {
        skill: 'issue-triage',
        total: 10,
        evaluated: 1,
        dispositions: { labeled: 1, nudged: 0, closed: 0, duplicate: 0, other: 0 },
        remaining: 9,
        currentIssue: null,
        processedIssues: [777],
        status: 'running',
        updatedAt: '',
        renderCount: 0,
      };
      // User comments on issue 777 after already labeling it
      const updated = processIssueCommand('gh issue comment 777 -b "thanks"', initial);
      assert(updated !== undefined && updated !== null);
      // Nudged disposition count increments
      assert.strictEqual(updated.dispositions.nudged, 1);
      // But evaluated remains 1 (not double counted)
      assert.strictEqual(updated.evaluated, 1);
      assert.strictEqual(updated.remaining, 9);
      assert.strictEqual(updated.processedIssues.length, 1);
    });
  });

  describe('isConfinedProgressPath', () => {
    test('accepts valid path under cwd', () => {
      assert(isConfinedProgressPath('/workspace/repo/.magpie-issue-sweep-abc123.json', '/workspace/repo'));
    });

    test('rejects path traversal', () => {
      assert(!isConfinedProgressPath('/workspace/repo/../etc/passwd', '/workspace/repo'));
      assert(!isConfinedProgressPath('/workspace/repo/..\\.magpie-issue-sweep-x.json', '/workspace/repo'));
    });

    test('rejects non-matching filename pattern', () => {
      assert(!isConfinedProgressPath('/workspace/repo/foo.json', '/workspace/repo'));
      assert(!isConfinedProgressPath('/workspace/repo/.magpie-issue-sweep-abc.txt', '/workspace/repo'));
    });

    test('fails closed when cwd is missing or empty', () => {
      assert(!isConfinedProgressPath('/workspace/repo/.magpie-issue-sweep-abc.json', null));
      assert(!isConfinedProgressPath('/workspace/repo/.magpie-issue-sweep-abc.json', ''));
    });
  });

  describe('hook lifecycle and auto-dismissal integration', () => {
    test('handleBashToolCall updates atom state on CLI issue commands', async () => {
      const engine = createMockEngine();
      await handleBashToolCall(engine, { command: 'gh issue list --limit 20' }, () => {});
      const state1 = await getIssueSweepProgressState(engine);
      assert(state1 !== null);
      assert.strictEqual(state1.total, 20);

      await handleBashToolCall(engine, { command: 'gh issue edit 42 --add-label bug' }, () => {});
      const state2 = await getIssueSweepProgressState(engine);
      assert(state2 !== null);
      assert.strictEqual(state2.dispositions.labeled, 1);
      assert.strictEqual(state2.evaluated, 1);
    });

    test('handleRenderAbovePrompt renders band and auto-dismisses after completion', async () => {
      const engine = createMockEngine();
      const completedState: IssueSweepProgressState = {
        skill: 'issue-triage',
        total: 1,
        evaluated: 1,
        dispositions: { labeled: 1, nudged: 0, closed: 0, duplicate: 0, other: 0 },
        remaining: 0,
        currentIssue: null,
        processedIssues: [1],
        status: 'completed',
        updatedAt: '',
        renderCount: 0,
      };
      await setIssueSweepProgressState(engine, completedState);

      // First render: renders completion checkmark and increments renderCount to 1
      const res1 = await handleRenderAbovePrompt(engine, { component: 'AbovePrompt' }, () => {});
      assert(res1 !== null);
      assert.strictEqual(res1.type, 'Box');

      const stateAfterFirstRender = await getIssueSweepProgressState(engine);
      assert(stateAfterFirstRender !== null);
      assert.strictEqual(stateAfterFirstRender.renderCount, 1);

      // Second render: auto-dismisses (resets state to null)
      let nextCalled = false;
      await handleRenderAbovePrompt(engine, { component: 'AbovePrompt' }, () => {
        nextCalled = true;
      });
      assert(nextCalled);
      const stateAfterSecondRender = await getIssueSweepProgressState(engine);
      assert.strictEqual(stateAfterSecondRender, null);
    });
  });
});
