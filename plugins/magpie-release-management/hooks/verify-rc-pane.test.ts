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

import { createDefaultVerifySteps } from './types.ts';
import type {
  StepStatus,
  VerifyRcState,
  VerifyRcStep,
} from './types.ts';

import {
  calculateProgressSummary,
  formatStepStatusBadge,
  getVerifyRcState,
  renderVerifyRcPane,
  register,
  sanitizeText,
  setVerifyRcState,
  truncateText,
  verifyRcState,
} from './verify-rc-pane.ts';

function assert(condition: any, message?: string): void {
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

function assertDeepStrictEqual(actual: any, expected: any, message?: string): void {
  const a = JSON.stringify(actual);
  const b = JSON.stringify(expected);
  if (a !== b) {
    throw new Error(message || `Expected ${b} but got ${a}`);
  }
}

function createMockEngine(overrides: any = {}): any {
  const store = new Map<string, any>();
  let invalidated = false;
  return {
    state: {
      get: (atom: any) => {
        return { isSet: store.has(atom.key), value: store.has(atom.key) ? store.get(atom.key) : null };
      },
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
      _store: store,
    },
    ui: {
      invalidate: () => {
        invalidated = true;
      },
      resolve: () => ({
        Box: (props: any) => ({ type: 'Box', ...props }),
        Text: (props: any) => ({ type: 'Text', ...props }),
      }),
      get wasInvalidated() {
        return invalidated;
      },
    },
    ...overrides,
  };
}

describe('magpie-release-management verify-rc checklist mod (PR-1)', () => {
  describe('normalization and formatters', () => {
    test('sanitizeText strips ANSI CSI, OSC sequences, and control characters', () => {
      assertStrictEqual(sanitizeText('plain text'), 'plain text');
      assertStrictEqual(sanitizeText('\x1b[31mRed Alert\x1b[0m'), 'Red Alert');
      assertStrictEqual(sanitizeText('\x1b]0;Window Title\x07Clean Text'), 'Clean Text');
      assertStrictEqual(sanitizeText('Line 1\x00\x08Text\x1f'), 'Line 1Text');
      assertStrictEqual(sanitizeText('\x1b[?25lHidden cursor'), 'Hidden cursor');
      assertStrictEqual(sanitizeText('failure\n[PASS] another check'), 'failure [PASS] another check');
      assertStrictEqual(sanitizeText(null), '');
      assertStrictEqual(sanitizeText(undefined), '');
      assertStrictEqual(sanitizeText(12345), '');
    });

    test('truncateText handles short and long strings with ellipsis', () => {
      assertStrictEqual(truncateText('short', 10), 'short');
      assertStrictEqual(truncateText('exactlength', 11), 'exactlength');
      assertStrictEqual(truncateText('a very long text that must be truncated', 15), 'a very long te\u2026');
      assertStrictEqual(truncateText('', 10), '');
    });

    test('formatStepStatusBadge maps all 6 StepStatus values correctly', () => {
      const passed = formatStepStatusBadge('passed');
      assertStrictEqual(passed.label, 'PASS');
      assertStrictEqual(passed.color, 'success');
      assertStrictEqual(passed.symbol, '[\u2713]');
      assertStrictEqual(passed.bold, true);

      const failed = formatStepStatusBadge('failed');
      assertStrictEqual(failed.label, 'FAIL');
      assertStrictEqual(failed.color, 'error');
      assertStrictEqual(failed.symbol, '[\u2717]');
      assertStrictEqual(failed.bold, true);

      const warning = formatStepStatusBadge('warning');
      assertStrictEqual(warning.label, 'WARN');
      assertStrictEqual(warning.color, 'warning');
      assertStrictEqual(warning.symbol, '[!]');
      assertStrictEqual(warning.bold, true);

      const running = formatStepStatusBadge('running');
      assertStrictEqual(running.label, 'RUNNING');
      assertStrictEqual(running.color, 'info');
      assertStrictEqual(running.symbol, '[*]');
      assertStrictEqual(running.bold, true);

      const skipped = formatStepStatusBadge('skipped');
      assertStrictEqual(skipped.label, 'SKIP');
      assertStrictEqual(skipped.color, 'dim');
      assertStrictEqual(skipped.symbol, '[-]');
      assertStrictEqual(skipped.bold, false);

      const pending = formatStepStatusBadge('pending');
      assertStrictEqual(pending.label, 'PENDING');
      assertStrictEqual(pending.color, 'dim');
      assertStrictEqual(pending.symbol, '[ ]');
      assertStrictEqual(pending.bold, false);
    });

    test('calculateProgressSummary aggregates step metrics accurately', () => {
      const steps: VerifyRcStep[] = [
        { id: 'preflight', label: 'Preflight', status: 'passed' },
        { id: 'inventory', label: 'Inventory', status: 'passed' },
        { id: 'signatures', label: 'Signatures', status: 'failed', detail: 'Key missing' },
        { id: 'checksums', label: 'Checksums', status: 'warning', detail: 'Deprecated md5' },
        { id: 'rat-license-headers', label: 'RAT', status: 'running' },
        { id: 'notice-license', label: 'Notice', status: 'skipped' },
        { id: 'binary-exclusion', label: 'Binaries', status: 'pending' },
      ];

      const summary = calculateProgressSummary(steps);
      assertStrictEqual(summary.total, 7);
      assertStrictEqual(summary.passed, 2);
      assertStrictEqual(summary.failed, 1);
      assertStrictEqual(summary.warning, 1);
      assertStrictEqual(summary.running, 1);
      assertStrictEqual(summary.skipped, 1);
      assertStrictEqual(summary.pending, 1);
      assertStrictEqual(summary.completed, 5); // passed + failed + warning + skipped
    });
  });

  describe('createDefaultVerifySteps canonical sequence', () => {
    test('returns all 13 canonical steps matching verify-rc/SKILL.md in exact order', () => {
      const steps = createDefaultVerifySteps();
      assertStrictEqual(steps.length, 13);

      const expectedIds = [
        'preflight',
        'inventory',
        'signatures',
        'checksums',
        'rat-license-headers',
        'notice-license',
        'binary-exclusion',
        'jvm-artefacts',
        'nexus-staging',
        'source-tree-integrity',
        'version-consistency',
        'reproducibility',
        'verdict',
      ];

      for (let i = 0; i < expectedIds.length; i += 1) {
        assertStrictEqual(steps[i].id, expectedIds[i]);
        assertStrictEqual(steps[i].status, 'pending');
        assert(typeof steps[i].label === 'string' && steps[i].label.length > 0);
      }
    });
  });

  describe('state store management and accessors', () => {
    test('getVerifyRcState and setVerifyRcState round-trip successfully', async () => {
      const $ = createMockEngine();
      const initial = await getVerifyRcState($);
      assertStrictEqual(initial, null);

      const sampleState: VerifyRcState = {
        rcTag: '2.11.0-rc1',
        version: '2.11.0',
        stagingUrl: 'https://dist.apache.org/repos/dist/dev/foo/2.11.0-rc1',
        overallStatus: 'running',
        currentStepId: 'signatures',
        steps: createDefaultVerifySteps(),
        startedAt: Date.now(),
      };

      await setVerifyRcState($, sampleState);
      assertStrictEqual($.ui.wasInvalidated, true);

      const retrieved = await getVerifyRcState($);
      assertDeepStrictEqual(retrieved, sampleState);

      await setVerifyRcState($, null);
      const afterReset = await getVerifyRcState($);
      assertStrictEqual(afterReset, null);
    });

    test('getVerifyRcState fails open when store throws exception', async () => {
      const failing$ = {
        state: {
          get: () => {
            throw new Error('Database disk error');
          },
        },
      };
      const result = await getVerifyRcState(failing$);
      assertStrictEqual(result, null);
    });
  });

  describe('renderVerifyRcPane UI component', () => {
    test('returns null when state is null or steps empty', () => {
      const $ = createMockEngine();
      assertStrictEqual(renderVerifyRcPane($, { component: 'Pane' }, null), null);

      const emptyStepsState: VerifyRcState = {
        rcTag: '2.11.0-rc1',
        version: '2.11.0',
        overallStatus: 'running',
        steps: [],
        startedAt: Date.now(),
      };
      assertStrictEqual(renderVerifyRcPane($, { component: 'Pane' }, emptyStepsState), null);
    });

    test('returns null when $.ui.resolve fails or Box/Text are missing', () => {
      const broken$ = {
        ui: {
          resolve: () => {
            throw new Error('UI resolve failed');
          },
        },
      };
      const state: VerifyRcState = {
        rcTag: '2.11.0-rc1',
        version: '2.11.0',
        overallStatus: 'running',
        steps: createDefaultVerifySteps(),
        startedAt: Date.now(),
      };
      assertStrictEqual(renderVerifyRcPane(broken$, { component: 'Pane' }, state), null);
    });

    test('renders structured Box tree with header, step rows, and footer', () => {
      const $ = createMockEngine();
      const steps = createDefaultVerifySteps();
      steps[0].status = 'passed';
      steps[1].status = 'passed';
      steps[2].status = 'running';

      const state: VerifyRcState = {
        rcTag: '2.11.0-rc1',
        version: '2.11.0',
        overallStatus: 'running',
        currentStepId: 'signatures',
        steps,
        startedAt: Date.now(),
      };

      const pane = renderVerifyRcPane($, { component: 'Pane' }, state);
      assert(pane !== null);
      assertStrictEqual(pane.type, 'Box');
      assertStrictEqual(pane.flexDirection, 'column');
      assertStrictEqual(pane.children.length, 3); // Header box, Steps box, Footer box

      const headerBox = pane.children[0];
      assertStrictEqual(headerBox.type, 'Box');
      const headerTitle = headerBox.children[0];
      assert(headerTitle.children[0].includes('2.11.0-rc1'));

      const stepsBox = pane.children[1];
      assertStrictEqual(stepsBox.type, 'Box');
      assertStrictEqual(stepsBox.children.length, 13);

      // Verify row 0 (preflight) has PASS badge
      const row0 = stepsBox.children[0];
      assertStrictEqual(row0.children[0].children[0], '[\u2713] ');
      assertStrictEqual(row0.children[2].children[0], '[PASS]');

      // Verify row 2 (signatures) has RUNNING badge
      const row2 = stepsBox.children[2];
      assertStrictEqual(row2.children[0].children[0], '[*] ');
      assertStrictEqual(row2.children[2].children[0], '[RUNNING]');

      const footerBox = pane.children[2];
      assert(footerBox.children[0].children[0].includes('signatures'));
    });

    test('displays inline details for failed or warning steps while keeping passed rows single-line', () => {
      const $ = createMockEngine();
      const steps = createDefaultVerifySteps();
      steps[2].status = 'failed';
      steps[2].detail = 'Key 0x1234ABCD not found in KEYS file';
      steps[3].status = 'warning';
      steps[3].detail = 'Deprecated md5 digest file staged';
      steps[0].status = 'passed';
      steps[0].detail = 'This should not appear in row';

      const state: VerifyRcState = {
        rcTag: '2.11.0-rc1',
        version: '2.11.0',
        overallStatus: 'failed',
        steps,
        startedAt: Date.now(),
      };

      const pane = renderVerifyRcPane($, { component: 'Pane' }, state);
      const stepsBox = pane.children[1];

      // Row 0 (passed): children length is 3 (no detail)
      const passedRow = stepsBox.children[0];
      assertStrictEqual(passedRow.children.length, 3);

      // Row 2 (failed): children length is 4 (includes detail)
      const failedRow = stepsBox.children[2];
      assertStrictEqual(failedRow.children.length, 4);
      assert(failedRow.children[3].children[0].includes('0x1234ABCD'));

      // Row 3 (warning): children length is 4 (includes detail)
      const warningRow = stepsBox.children[3];
      assertStrictEqual(warningRow.children.length, 4);
      assert(warningRow.children[3].children[0].includes('Deprecated md5'));
    });

    test('renders appropriate final verdict footer text and colors', () => {
      const $ = createMockEngine();
      const steps = createDefaultVerifySteps();

      const passedState: VerifyRcState = {
        rcTag: '2.11.0-rc1',
        version: '2.11.0',
        overallStatus: 'passed',
        steps,
        startedAt: Date.now(),
      };
      const passedPane = renderVerifyRcPane($, { component: 'Pane' }, passedState);
      assert(passedPane.children[2].children[0].children[0].includes('PASS'));

      const warnState: VerifyRcState = {
        rcTag: '2.11.0-rc1',
        version: '2.11.0',
        overallStatus: 'passed-with-warnings',
        steps,
        startedAt: Date.now(),
      };
      const warnPane = renderVerifyRcPane($, { component: 'Pane' }, warnState);
      assert(warnPane.children[2].children[0].children[0].includes('PASS-WITH-WARNINGS'));

      const failedState: VerifyRcState = {
        rcTag: '2.11.0-rc1',
        version: '2.11.0',
        overallStatus: 'failed',
        steps,
        startedAt: Date.now(),
      };
      const failedPane = renderVerifyRcPane($, { component: 'Pane' }, failedState);
      assert(failedPane.children[2].children[0].children[0].includes('FAIL'));
    });

    test('renders exact visual text format matching Pane layout specification', () => {
      const $ = createMockEngine();
      const steps = createDefaultVerifySteps();
      steps[0].status = 'passed';
      steps[1].status = 'passed';
      steps[2].status = 'running';

      const state: VerifyRcState = {
        rcTag: '3.0.0-rc1',
        version: '3.0.0',
        overallStatus: 'running',
        currentStepId: 'signatures',
        steps,
        startedAt: 1700000000000,
      };

      const pane = renderVerifyRcPane($, { component: 'Pane' }, state);
      assert(pane !== null);

      // Helper to format Box/Text hierarchy for visual inspection
      const lines: string[] = [];
      lines.push('---------------- [ LIVE PANE RENDERING PREVIEW ] ----------------');
      lines.push(`${pane.children[0].children[0].children[0]}`);
      lines.push(`${pane.children[0].children[1].children[0]}`);
      lines.push('');
      for (const row of pane.children[1].children) {
        const rowText = row.children.map((c: any) => c.children[0]).join('');
        lines.push(rowText);
      }
      lines.push('');
      lines.push(`${pane.children[2].children[0].children[0]}`);
      lines.push('------------------------------------------------------------------');
      console.log('\n' + lines.join('\n'));

      // Also preview failure state
      const failSteps = createDefaultVerifySteps();
      failSteps[0].status = 'passed';
      failSteps[1].status = 'passed';
      failSteps[2].status = 'failed';
      failSteps[2].detail = 'Key 0xABCD1234 not found in staged KEYS file from dist.apache.org';
      failSteps[3].status = 'warning';
      failSteps[3].detail = 'Deprecated md5 digest file staged alongside sha512';
      const failState: VerifyRcState = {
        rcTag: '3.0.0-rc1',
        version: '3.0.0',
        overallStatus: 'failed',
        steps: failSteps,
        startedAt: 1700000000000,
        completedAt: 1700000015000,
      };
      const failPane = renderVerifyRcPane($, { component: 'Pane' }, failState);
      const failLines: string[] = [];
      failLines.push('-------------- [ HARD BLOCKER FAILURE PANE PREVIEW ] -------------');
      failLines.push(`${failPane.children[0].children[0].children[0]}`);
      failLines.push(`${failPane.children[0].children[1].children[0]}`);
      failLines.push('');
      for (const row of failPane.children[1].children) {
        const rowText = row.children.map((c: any) => c.children[0]).join('');
        failLines.push(rowText);
      }
      failLines.push('');
      failLines.push(`${failPane.children[2].children[0].children[0]}`);
      failLines.push('------------------------------------------------------------------');
      console.log('\n' + failLines.join('\n'));

      // Verify Header
      const headerBox = pane.children[0];
      assertStrictEqual(headerBox.children[0].children[0], 'RC Verification: 3.0.0-rc1');
      assertStrictEqual(headerBox.children[0].bold, true);
      assertStrictEqual(
        headerBox.children[1].children[0],
        'Progress: 2/13 completed \u00B7 Status: RUNNING'
      );
      assertStrictEqual(headerBox.children[1].color, 'info');

      // Verify Step Rows
      const stepsBox = pane.children[1];
      assertStrictEqual(stepsBox.children.length, 13);

      // Preflight (passed)
      const row0 = stepsBox.children[0];
      assertStrictEqual(row0.children[0].children[0], '[\u2713] ');
      assertStrictEqual(row0.children[0].color, 'success');
      assertStrictEqual(row0.children[1].children[0], 'Pre-flight check & config resolution ');
      assertStrictEqual(row0.children[2].children[0], '[PASS]');
      assertStrictEqual(row0.children.length, 3); // Single-line row

      // Inventory (passed)
      const row1 = stepsBox.children[1];
      assertStrictEqual(row1.children[0].children[0], '[\u2713] ');
      assertStrictEqual(row1.children[2].children[0], '[PASS]');

      // Signatures (running)
      const row2 = stepsBox.children[2];
      assertStrictEqual(row2.children[0].children[0], '[*] ');
      assertStrictEqual(row2.children[0].color, 'info');
      assertStrictEqual(row2.children[1].children[0], 'GPG signatures (KEYS verification) ');
      assertStrictEqual(row2.children[1].bold, true);
      assertStrictEqual(row2.children[2].children[0], '[RUNNING]');

      // Checksums (pending)
      const row3 = stepsBox.children[3];
      assertStrictEqual(row3.children[0].children[0], '[ ] ');
      assertStrictEqual(row3.children[0].color, 'dim');
      assertStrictEqual(row3.children[1].children[0], 'SHA512 & digest checksums ');
      assertStrictEqual(row3.children[2].children[0], '[PENDING]');

      // Verify Footer
      const footerBox = pane.children[2];
      assertStrictEqual(
        footerBox.children[0].children[0],
        'Current: GPG signatures (KEYS verification)...'
      );
      assertStrictEqual(footerBox.children[0].color, 'info');
    });

    test('strips ANSI escape sequences and truncates overflow in rendered output', () => {
      const $ = createMockEngine();
      const steps = createDefaultVerifySteps();
      steps[2].status = 'failed';
      steps[2].detail =
        '\x1b[31mKey 0xABCD1234 not found in staged KEYS file from dist.apache.org repository\x1b[0m';

      const state: VerifyRcState = {
        rcTag: '\x1b[32m2.11.0-rc1\x1b[0m',
        version: '2.11.0',
        overallStatus: 'failed',
        steps,
        startedAt: Date.now(),
      };

      const pane = renderVerifyRcPane($, { component: 'Pane' }, state);
      const headerBox = pane.children[0];
      // Title must be sanitized
      assertStrictEqual(headerBox.children[0].children[0], 'RC Verification: 2.11.0-rc1');

      // Failed row detail must be sanitized and truncated to 60 chars
      const stepsBox = pane.children[1];
      const failedRow = stepsBox.children[2];
      assertStrictEqual(failedRow.children.length, 4);
      const detailText = failedRow.children[3].children[0];
      assert(!detailText.includes('\x1b'));
      assert(detailText.endsWith('\u2026'));
      // Prefix is " \u2014 " (3 chars) + truncated text (60 chars) = 63 chars
      assertStrictEqual(detailText.length, 63);
    });
  });

  describe('hook registration', () => {
    test('register attaches session.start and ui.render (Pane)', async () => {
      const registeredHooks = new Map<string, Function>();
      const on = (event: string, handler: Function) => {
        registeredHooks.set(event, handler);
      };

      register(on);
      assertStrictEqual(registeredHooks.has('session.start'), true);
      assertStrictEqual(registeredHooks.has('ui.render'), true);

      const $ = createMockEngine();
      let nextCalled = false;
      const next = (e: any) => {
        nextCalled = true;
        return 'next-result';
      };

      // session.start resets state to null
      await setVerifyRcState($, {
        rcTag: 'old-rc',
        version: 'old',
        overallStatus: 'running',
        steps: createDefaultVerifySteps(),
        startedAt: Date.now(),
      });
      const sessionHandler = registeredHooks.get('session.start')!;
      const sessionResult = await sessionHandler($, { type: 'start' }, next);
      assertStrictEqual(nextCalled, true);
      assertStrictEqual(sessionResult, 'next-result');
      const stateAfterStart = await getVerifyRcState($);
      assertStrictEqual(stateAfterStart, null);

      // ui.render passes through when component is not Pane
      nextCalled = false;
      const uiHandler = registeredHooks.get('ui.render')!;
      const otherComponentResult = await uiHandler($, { component: 'AbovePrompt' }, next);
      assertStrictEqual(nextCalled, true);
      assertStrictEqual(otherComponentResult, 'next-result');

      // ui.render returns Pane when component is Pane and state populated
      nextCalled = false;
      const steps = createDefaultVerifySteps();
      await setVerifyRcState($, {
        rcTag: '2.11.0-rc1',
        version: '2.11.0',
        overallStatus: 'running',
        steps,
        startedAt: Date.now(),
      });
      const paneResult = await uiHandler($, { component: 'Pane' }, next);
      assertStrictEqual(nextCalled, false);
      assert(paneResult !== null && paneResult.type === 'Box');
    });
  });

  describe('ambient PluginState type conformity', () => {
    test('VerifyRcState matches ambient PluginState magpie-release-management interface shape', () => {
      const state: VerifyRcState = {
        rcTag: '2.11.0-rc1',
        version: '2.11.0',
        stagingUrl: 'https://dist.apache.org',
        postTo: 'https://github.com/apache/foo/issues/1',
        overallStatus: 'running',
        currentStepId: 'signatures',
        steps: [
          {
            id: 'signatures',
            label: 'Signatures',
            status: 'passed',
            detail: 'All keys verified',
            durationMs: 120,
          },
        ],
        startedAt: Date.now(),
        completedAt: Date.now() + 5000,
      };

      // Verify all required fields exist and match expected types
      assertStrictEqual(typeof state.rcTag, 'string');
      assertStrictEqual(typeof state.version, 'string');
      assertStrictEqual(typeof state.overallStatus, 'string');
      assertStrictEqual(typeof state.startedAt, 'number');
      assert(Array.isArray(state.steps));
      assertStrictEqual(state.steps[0].id, 'signatures');
      assertStrictEqual(state.steps[0].status, 'passed');
    });
  });
});
