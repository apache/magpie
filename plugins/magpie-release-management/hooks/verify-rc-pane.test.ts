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
  OverallVerifyStatus,
  StepStatus,
  VerifyRcState,
  VerifyRcStep,
  VerifyStepId,
} from './types.ts';

import {
  applyJvmSkipRules,
  calculateOverallStatus,
  calculateProgressSummary,
  deriveVersionFromRcTag,
  extractDetailFromPayload,
  extractJsonFromOutput,
  extractRcTag,
  formatStepStatusBadge,
  getVerifyRcState,
  handleBashToolCall,
  mapCliSubcommandToStepId,
  normalizeStepStatus,
  register,
  renderVerifyRcPane,
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
    test('register attaches session.start, ui.render (Pane), and tool.call (Bash)', async () => {
      const registrations: any[] = [];
      const on = (...args: any[]) => {
        registrations.push(args);
      };

      register(on);
      assertStrictEqual(registrations.length, 3);
      assertStrictEqual(registrations[0][0], 'session.start');
      assertStrictEqual(registrations[1][0], 'ui.render');
      assertStrictEqual(registrations[2][0], 'tool.call');
      assertDeepStrictEqual(registrations[2][1], { tool: 'Bash' });
      assertStrictEqual(registrations[2][2], handleBashToolCall);

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
      const sessionHandler = registrations[0][1];
      const sessionResult = await sessionHandler($, { type: 'start' }, next);
      assertStrictEqual(nextCalled, true);
      assertStrictEqual(sessionResult, 'next-result');
      const stateAfterStart = await getVerifyRcState($);
      assertStrictEqual(stateAfterStart, null);

      // ui.render passes through when component is not Pane
      nextCalled = false;
      const uiHandler = registrations[1][1];
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

  describe('tool-call feed and verification middleware (PR-2)', () => {
    describe('helper functions', () => {
      test('extractRcTag parses various release candidate command patterns', () => {
        assertStrictEqual(
          extractRcTag('uv run release-config preflight --rc-tag 2.11.0-rc1'),
          '2.11.0-rc1'
        );
        assertStrictEqual(
          extractRcTag('uv run --project tools/release-management verify-rc 3.0.0-rc2 --post-to https://github.com/org/repo/issues/1'),
          '3.0.0-rc2'
        );
        assertStrictEqual(
          extractRcTag('release-verify all --tag=1.2.3-rc4'),
          '1.2.3-rc4'
        );
        assertStrictEqual(
          extractRcTag('uv run release-verify apache-beam-2.60.0-rc1'),
          'apache-beam-2.60.0-rc1'
        );
        assertStrictEqual(extractRcTag('git status'), null);
        assertStrictEqual(extractRcTag(''), null);
        assertStrictEqual(extractRcTag(null as any), null);
      });

      test('deriveVersionFromRcTag extracts release version by stripping rc suffix', () => {
        assertStrictEqual(deriveVersionFromRcTag('2.11.0-rc1'), '2.11.0');
        assertStrictEqual(deriveVersionFromRcTag('3.0.0-rc99'), '3.0.0');
        assertStrictEqual(deriveVersionFromRcTag('apache-beam-2.60.0-rc1'), 'apache-beam-2.60.0');
        assertStrictEqual(deriveVersionFromRcTag(''), '');
        assertStrictEqual(deriveVersionFromRcTag(null as any), '');
      });

      test('mapCliSubcommandToStepId maps CLI invocations to canonical step IDs', () => {
        // Preflight
        assertStrictEqual(
          mapCliSubcommandToStepId('uv run release-config preflight --skill verify-rc 2.11.0-rc1'),
          'preflight'
        );
        assertStrictEqual(
          mapCliSubcommandToStepId('uv run release-config load --skill verify-rc 2.11.0-rc1'),
          null // decoupled: load does not map to a verification step and never resets preflight
        );

        // Individual steps
        assertStrictEqual(mapCliSubcommandToStepId('release-verify inventory'), 'inventory');
        assertStrictEqual(mapCliSubcommandToStepId('release-verify signatures'), 'signatures');
        assertStrictEqual(mapCliSubcommandToStepId('release-verify checksums'), 'checksums');
        assertStrictEqual(mapCliSubcommandToStepId('release-verify rat'), null);
        assertStrictEqual(mapCliSubcommandToStepId('verify-rc rat'), 'rat-license-headers');
        assertStrictEqual(mapCliSubcommandToStepId('release-verify notice-license'), 'notice-license');
        assertStrictEqual(mapCliSubcommandToStepId('release-verify binaries'), 'binary-exclusion');
        assertStrictEqual(mapCliSubcommandToStepId('verify-rc jvm'), 'jvm-artefacts');
        assertStrictEqual(mapCliSubcommandToStepId('maven-artifact-verify'), 'jvm-artefacts');
        assertStrictEqual(mapCliSubcommandToStepId('verify-rc nexus'), 'nexus-staging');
        assertStrictEqual(mapCliSubcommandToStepId('release-verify symlinks'), 'source-tree-integrity');
        assertStrictEqual(mapCliSubcommandToStepId('verify-rc source-tree'), 'source-tree-integrity');
        assertStrictEqual(mapCliSubcommandToStepId('release-verify version'), 'version-consistency');
        assertStrictEqual(mapCliSubcommandToStepId('verify-rc repro'), 'reproducibility');
        assertStrictEqual(mapCliSubcommandToStepId('repro-archive compare'), 'reproducibility');
        assertStrictEqual(mapCliSubcommandToStepId('release-verify verdict'), 'verdict');
        assertStrictEqual(mapCliSubcommandToStepId('verify-rc report'), 'verdict');

        // Batch runner
        assertStrictEqual(mapCliSubcommandToStepId('release-verify all'), 'all');

        // Unrelated commands
        assertStrictEqual(mapCliSubcommandToStepId('git status'), null);
        assertStrictEqual(mapCliSubcommandToStepId('ls -la'), null);
        assertStrictEqual(mapCliSubcommandToStepId(''), null);
      });

      test('extractJsonFromOutput extracts parsed object from direct or mixed stdout', () => {
        // Direct JSON
        assertDeepStrictEqual(extractJsonFromOutput('{"status": "PASS", "ok": true}'), {
          status: 'PASS',
          ok: true,
        });

        // JSON inside logging output
        const mixed =
          '[INFO] Initializing verification\n{"step": "signatures", "status": "PASS"}\n[INFO] Done in 100ms';
        assertDeepStrictEqual(extractJsonFromOutput(mixed), {
          step: 'signatures',
          status: 'PASS',
        });

        // Object passed directly
        assertDeepStrictEqual(extractJsonFromOutput({ direct: 1 }), { direct: 1 });

        // Non-JSON string
        assertStrictEqual(extractJsonFromOutput('no json here'), null);
        assertStrictEqual(extractJsonFromOutput('{invalid json'), null);
        assertStrictEqual(extractJsonFromOutput(null), null);
      });

      test('normalizeStepStatus normalizes status tokens to StepStatus', () => {
        assertStrictEqual(normalizeStepStatus('PASS'), 'passed');
        assertStrictEqual(normalizeStepStatus('passed'), 'passed');
        assertStrictEqual(normalizeStepStatus('OK'), 'passed');
        assertStrictEqual(normalizeStepStatus('SUCCESS'), 'passed');
        assertStrictEqual(normalizeStepStatus('PROCEED'), 'passed');

        assertStrictEqual(normalizeStepStatus('FAIL'), 'failed');
        assertStrictEqual(normalizeStepStatus('FAILED'), 'failed');
        assertStrictEqual(normalizeStepStatus('ERROR'), 'failed');
        assertStrictEqual(normalizeStepStatus('BLOCKED'), 'failed');

        assertStrictEqual(normalizeStepStatus('WARN'), 'warning');
        assertStrictEqual(normalizeStepStatus('WARNING'), 'warning');
        assertStrictEqual(normalizeStepStatus('REVIEW'), 'running');

        assertStrictEqual(normalizeStepStatus('SKIP'), 'skipped');
        assertStrictEqual(normalizeStepStatus('SKIPPED'), 'skipped');

        assertStrictEqual(normalizeStepStatus('RUNNING'), 'running');

        assertStrictEqual(normalizeStepStatus('unknown'), 'running');
        assertStrictEqual(normalizeStepStatus(null), 'pending');
      });

      test('calculateOverallStatus computes rollup verdict accurately', () => {
        const steps = createDefaultVerifySteps();

        // Initially running (all pending)
        assertStrictEqual(calculateOverallStatus(steps), 'running');

        // If one failed, overall is failed immediately
        steps[2].status = 'failed';
        assertStrictEqual(calculateOverallStatus(steps), 'failed');

        // Reset all to passed or skipped
        for (const s of steps) {
          s.status = 'passed';
        }
        steps[7].status = 'skipped';
        steps[8].status = 'skipped';
        assertStrictEqual(calculateOverallStatus(steps), 'passed');

        // If one has a warning and all else passed/skipped, passed-with-warnings
        steps[3].status = 'warning';
        assertStrictEqual(calculateOverallStatus(steps), 'passed-with-warnings');

        // If one step is still pending, status is running (unless another is failed)
        steps[12].status = 'pending';
        assertStrictEqual(calculateOverallStatus(steps), 'running');
      });

      test('extractDetailFromPayload extracts human-readable findings', () => {
        assertStrictEqual(
          extractDetailFromPayload({ detail: 'Verified 5 signatures successfully' }),
          'Verified 5 signatures successfully'
        );
        assertStrictEqual(
          extractDetailFromPayload({ diff_summary: 'NOTICE and LICENSE identical' }),
          'NOTICE and LICENSE identical'
        );
        assertStrictEqual(
          extractDetailFromPayload({ unapproved_files: ['file1.c', 'file2.h'] }),
          'Unapproved headers: 2 file(s)'
        );
        assertStrictEqual(
          extractDetailFromPayload({ missing: ['apache-foo-1.0.tar.gz.sha512'] }),
          'Missing: apache-foo-1.0.tar.gz.sha512'
        );
        assertStrictEqual(
          extractDetailFromPayload({ prohibited_found: ['nested/build.class'] }),
          'Prohibited: nested/build.class'
        );
        assertStrictEqual(
          extractDetailFromPayload({ deprecated_md5_present: true }),
          'Deprecated md5 digest staged'
        );
        assertStrictEqual(
          extractDetailFromPayload({ dangling_symlinks: ['broken-link'] }),
          'Dangling symlink: broken-link'
        );
        assertStrictEqual(
          extractDetailFromPayload({
            validator_failures: [{ validator: 'check-symlinks', detail: 'symlink target missing' }],
          }),
          'symlink target missing'
        );
        assertStrictEqual(
          extractDetailFromPayload({ blockers: ['Keyserver unreachable'] }),
          'Keyserver unreachable'
        );
        assertStrictEqual(extractDetailFromPayload({}), null);
        assertStrictEqual(extractDetailFromPayload(null), null);
      });

      test('applyJvmSkipRules applies skip heuristics', () => {
        const steps = createDefaultVerifySteps();

        // Inventory without JVM files skips Steps 6b and 6c
        applyJvmSkipRules(steps, {
          found: ['release-3.0.0.tar.gz', 'release-3.0.0.tar.gz.asc', 'release-3.0.0.tar.gz.sha512'],
        });
        const jvmStep = steps.find((s) => s.id === 'jvm-artefacts')!;
        const nexusStep = steps.find((s) => s.id === 'nexus-staging')!;
        assertStrictEqual(jvmStep.status, 'skipped');
        assertStrictEqual(jvmStep.detail, 'No JVM artefacts staged');
        assertStrictEqual(nexusStep.status, 'skipped');
        assertStrictEqual(nexusStep.detail, 'No JVM artefacts staged');

        // Reset steps and test with JVM files staged
        const stepsWithJvm = createDefaultVerifySteps();
        applyJvmSkipRules(stepsWithJvm, {
          found: ['release-3.0.0.jar', 'release-3.0.0.pom'],
        });
        assertStrictEqual(stepsWithJvm.find((s) => s.id === 'jvm-artefacts')!.status, 'pending');
        assertStrictEqual(stepsWithJvm.find((s) => s.id === 'nexus-staging')!.status, 'pending');

      });
    });

    describe('handleBashToolCall middleware', () => {
      test('bypasses non-verification bash commands without mutating state', async () => {
        const $ = createMockEngine();
        let nextCalled = false;
        const next = async (e: any) => {
          nextCalled = true;
          return { stdout: 'branch main' };
        };

        const result = await handleBashToolCall($, { command: 'git status' }, next);
        assertStrictEqual(nextCalled, true);
        assertDeepStrictEqual(result, { stdout: 'branch main' });
        const state = await getVerifyRcState($);
        assertStrictEqual(state, null);
      });

      test('initializes VerifyRcState on release-config preflight command', async () => {
        const $ = createMockEngine();
        const next = async (e: any) => ({
          stdout: JSON.stringify({
            ok: true,
            skill: 'verify-rc',
            blockers: [],
            warnings: [],
            values: {
              rc_tag: '3.0.0-rc1',
              staging_url: 'https://dist.apache.org/repos/dist/dev/foo/3.0.0-rc1',
            },
          }),
        });

        await handleBashToolCall(
          $,
          { command: 'uv run release-config preflight --skill verify-rc 3.0.0-rc1' },
          next
        );

        const state = await getVerifyRcState($);
        assert(state !== null);
        assertStrictEqual(state.rcTag, '3.0.0-rc1');
        assertStrictEqual(state.version, '3.0.0');
        assertStrictEqual(state.overallStatus, 'running');
        assertStrictEqual(state.steps.length, 13);
        assertStrictEqual(state.steps[0].id, 'preflight');
        assertStrictEqual(state.steps[0].status, 'passed');
      });

      test('initializes VerifyRcState on standalone release-verify inventory command if unpopulated', async () => {
        const $ = createMockEngine();
        const next = async (e: any) => ({
          stdout: JSON.stringify({
            step: 'inventory',
            status: 'PASS',
            found: ['foo-3.0.0.tar.gz'],
          }),
        });

        await handleBashToolCall(
          $,
          { command: 'uv run release-verify inventory 3.0.0-rc1' },
          next
        );

        const state = await getVerifyRcState($);
        assert(state !== null);
        assertStrictEqual(state.rcTag, '3.0.0-rc1');
        assertStrictEqual(state.steps.find((s: any) => s.id === 'inventory').status, 'passed');
      });

      test('transitions step to running and then to passed upon successful tool output', async () => {
        const $ = createMockEngine();
        // Initialize state
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        let wasRunningDuringNext = false;
        const next = async (e: any) => {
          const intermediateState = await getVerifyRcState($);
          const sigStep = intermediateState.steps.find((s: any) => s.id === 'signatures');
          wasRunningDuringNext = sigStep.status === 'running';
          return {
            stdout: JSON.stringify({
              step: 'signatures',
              status: 'PASS',
              detail: 'All 3 signatures valid against KEYS',
            }),
          };
        };

        await handleBashToolCall($, { command: 'uv run release-verify signatures' }, next);

        assertStrictEqual(wasRunningDuringNext, true);
        const state = await getVerifyRcState($);
        const finalSigStep = state.steps.find((s: any) => s.id === 'signatures');
        assertStrictEqual(finalSigStep.status, 'passed');
        assertStrictEqual(finalSigStep.detail, 'All 3 signatures valid against KEYS');
        assert(typeof finalSigStep.durationMs === 'number');
      });

      test('transitions step to failed and recalculates overallStatus when tool throws', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        const next = async (e: any) => {
          throw new Error('Key 0xABCD1234 not in KEYS file');
        };

        let threw = false;
        try {
          await handleBashToolCall($, { command: 'uv run release-verify signatures' }, next);
        } catch (err: any) {
          threw = true;
          assert(err.message.includes('Key 0xABCD1234'));
        }

        assertStrictEqual(threw, true);
        const state = await getVerifyRcState($);
        const sigStep = state.steps.find((s: any) => s.id === 'signatures');
        assertStrictEqual(sigStep.status, 'failed');
        assert(sigStep.detail.includes('Key 0xABCD1234 not in KEYS file'));
        assertStrictEqual(state.overallStatus, 'failed');
      });

      test('processes batch release-verify all output updating multiple steps simultaneously', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        const batchOutput = {
          tool: 'release-verify',
          steps: [
            {
              step: 'inventory',
              status: 'PASS',
              found: ['foo-3.0.0.tar.gz', 'foo-3.0.0.tar.gz.asc', 'foo-3.0.0.tar.gz.sha512'],
            },
            { step: 'signatures', status: 'PASS' },
            { step: 'checksums', status: 'PASS' },
            { step: 'notice-license', status: 'PASS' },
            { step: 'binary-exclusion', status: 'PASS' },
            { step: 'source-tree-integrity', status: 'PASS' },
            { step: 'version-consistency', status: 'PASS' },
          ],
          verdict: {
            step: 'verdict',
            overall: 'PASS',
            step_summary: [],
          },
        };

        const next = async (e: any) => ({
          stdout: JSON.stringify(batchOutput),
        });

        await handleBashToolCall($, { command: 'uv run release-verify all' }, next);

        const state = await getVerifyRcState($);
        assertStrictEqual(state.steps.find((s: any) => s.id === 'inventory').status, 'passed');
        assertStrictEqual(state.steps.find((s: any) => s.id === 'signatures').status, 'passed');
        assertStrictEqual(state.steps.find((s: any) => s.id === 'checksums').status, 'passed');
        assertStrictEqual(state.steps.find((s: any) => s.id === 'notice-license').status, 'passed');
        assertStrictEqual(state.steps.find((s: any) => s.id === 'binary-exclusion').status, 'passed');
        assertStrictEqual(state.steps.find((s: any) => s.id === 'source-tree-integrity').status, 'passed');
        assertStrictEqual(state.steps.find((s: any) => s.id === 'version-consistency').status, 'passed');

        // Non-JVM inventory should have caused jvm-artefacts and nexus-staging to be skipped
        assertStrictEqual(state.steps.find((s: any) => s.id === 'jvm-artefacts').status, 'skipped');
        assertStrictEqual(state.steps.find((s: any) => s.id === 'nexus-staging').status, 'skipped');
      });

      test('records completedAt timestamp upon verdict step completion', async () => {
        const $ = createMockEngine();
        const steps = createDefaultVerifySteps();
        for (const s of steps) {
          s.status = 'passed';
        }
        steps[12].status = 'pending'; // verdict step

        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps,
          startedAt: Date.now() - 10000,
        });

        const next = async (e: any) => ({
          stdout: JSON.stringify({
            step: 'verdict',
            overall: 'PASS',
            step_summary: [],
          }),
        });

        await handleBashToolCall($, { command: 'uv run release-verify verdict' }, next);

        const state = await getVerifyRcState($);
        assertStrictEqual(state.steps[12].status, 'passed');
        assertStrictEqual(state.overallStatus, 'passed');
        assert(typeof state.completedAt === 'number');
      });

      test('fails open and proceeds with next() if state atom operations throw', async () => {
        const broken$ = {
          state: {
            get: () => {
              throw new Error('Database locked');
            },
            set: () => {
              throw new Error('Database locked');
            },
          },
          ui: { invalidate: () => {} },
        };

        let nextCalled = false;
        const next = async (e: any) => {
          nextCalled = true;
          return { stdout: 'success' };
        };

        const result = await handleBashToolCall(
          broken$,
          { command: 'release-config preflight 3.0.0-rc1' },
          next
        );
        assertStrictEqual(nextCalled, true);
        assertDeepStrictEqual(result, { stdout: 'success' });
      });

      test('handles blocked preflight by setting status to failed with blocker detail', async () => {
        const $ = createMockEngine();
        const next = async (e: any) => ({
          stdout: JSON.stringify({
            ok: false,
            skill: 'verify-rc',
            blockers: ['required key release_manager is missing from release-management-config.md'],
            warnings: [],
            values: {},
          }),
        });

        await handleBashToolCall(
          $,
          { command: 'uv run release-config preflight --skill verify-rc 3.0.0-rc1' },
          next
        );

        const state = await getVerifyRcState($);
        assert(state !== null);
        assertStrictEqual(state.steps[0].status, 'failed');
        assert(state.steps[0].detail!.includes('required key release_manager is missing'));
        assertStrictEqual(state.overallStatus, 'failed');
      });

      test('handles preflight with warnings by setting status to warning', async () => {
        const $ = createMockEngine();
        const next = async (e: any) => ({
          stdout: JSON.stringify({
            ok: true,
            skill: 'verify-rc',
            blockers: [],
            warnings: ['KEYS URL uses http instead of https'],
            values: { rc_tag: '3.0.0-rc1' },
          }),
        });

        await handleBashToolCall(
          $,
          { command: 'uv run release-config preflight --skill verify-rc 3.0.0-rc1' },
          next
        );

        const state = await getVerifyRcState($);
        assert(state !== null);
        assertStrictEqual(state.steps[0].status, 'warning');
        assertStrictEqual(state.steps[0].detail, 'KEYS URL uses http instead of https');
      });

      test('handles verdict FAIL by setting status to failed and overall to failed', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        const next = async (e: any) => ({
          stdout: JSON.stringify({
            step: 'verdict',
            overall: 'FAIL',
            fail_steps: ['signatures', 'checksums'],
            step_summary: [],
          }),
        });

        await handleBashToolCall($, { command: 'uv run release-verify verdict' }, next);

        const state = await getVerifyRcState($);
        assertStrictEqual(state.steps[12].status, 'failed');
        assertStrictEqual(state.steps[12].detail, 'Failed: signatures, checksums');
        assertStrictEqual(state.overallStatus, 'failed');
        assert(typeof state.completedAt === 'number');
      });

      test('handles unresolved verdict (overall: null) by keeping status running', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        const next = async (e: any) => ({
          stdout: JSON.stringify({
            step: 'verdict',
            overall: null,
            unresolved: ['notice-license', 'source-tree-integrity'],
            step_summary: [],
          }),
        });

        await handleBashToolCall($, { command: 'uv run release-verify verdict' }, next);

        const state = await getVerifyRcState($);
        assertStrictEqual(state.steps[12].status, 'running');
        assertStrictEqual(state.steps[12].detail, 'Unresolved: notice-license, source-tree-integrity');
        assertStrictEqual(state.overallStatus, 'running');
        assertStrictEqual(state.completedAt, null);
      });

      test('handles tool output with status: null by leaving step running', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        const next = async (e: any) => ({
          stdout: JSON.stringify({
            step: 'reproducibility',
            status: null,
            pending: ['--compare: what repro-archive compare printed'],
          }),
        });

        await handleBashToolCall($, { command: 'uv run verify-rc repro 3.0.0-rc1' }, next);

        const state = await getVerifyRcState($);
        assertStrictEqual(state.steps[11].status, 'running');
        assertStrictEqual(state.steps[11].detail, 'Pending: --compare: what repro-archive compare printed');
      });

      test('fails the reproducibility row on a verify-rc repro error payload', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        await handleBashToolCall($, { command: 'uv run verify-rc repro 3.0.0-rc1' }, async () => ({
          stdout: JSON.stringify({ ok: false, error: 'no such directory: dist' }),
          exitCode: 2,
        }));

        const state = await getVerifyRcState($);
        assertStrictEqual(state.steps[11].status, 'failed');
        assertStrictEqual(state.steps[11].detail, 'no such directory: dist');
      });

      test('keeps the verdict row running when verify-rc report refuses an unresolved verdict', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        await handleBashToolCall($, { command: 'uv run release-management verify-rc report' }, async () => ({
          stdout: JSON.stringify({
            ok: false,
            error: "the verdict is unresolved (steps still REVIEW: ['notice-license']); resolve them first",
          }),
          exitCode: 2,
        }));

        const state = await getVerifyRcState($);
        const verdict = state.steps.find((s: any) => s.id === 'verdict');
        assertStrictEqual(verdict.status, 'running');
        assert(state.overallStatus !== 'failed');
      });

      test('marks the batch rows running while a fresh release-verify all runs', async () => {
        const $ = createMockEngine();
        let duringRun: any = null;

        await handleBashToolCall($, { command: 'uv run release-verify all --rc-tag 3.0.0-rc1' }, async () => {
          duringRun = await getVerifyRcState($);
          return { stdout: JSON.stringify({ tool: 'release-verify', steps: [], verdict: null }) };
        });

        for (const id of ['inventory', 'signatures', 'checksums', 'notice-license']) {
          assertStrictEqual(duringRun.steps.find((s: any) => s.id === id).status, 'running');
        }
      });

      test('resets state for new RC tag in the same session', async () => {
        const $ = createMockEngine();

        // 1. Run for rc1
        await handleBashToolCall(
          $,
          { command: 'uv run release-config preflight 3.0.0-rc1' },
          async () => ({
            stdout: JSON.stringify({
              ok: true,
              skill: 'verify-rc',
              blockers: [],
              warnings: [],
              values: { rc_tag: '3.0.0-rc1' },
            }),
          })
        );
        let state = await getVerifyRcState($);
        assertStrictEqual(state.rcTag, '3.0.0-rc1');
        assertStrictEqual(state.steps[0].status, 'passed');

        // 2. Now run for rc2
        await handleBashToolCall(
          $,
          { command: 'uv run release-config preflight 3.0.0-rc2' },
          async () => ({
            stdout: JSON.stringify({
              ok: true,
              skill: 'verify-rc',
              blockers: [],
              warnings: [],
              values: { rc_tag: '3.0.0-rc2' },
            }),
          })
        );
        state = await getVerifyRcState($);
        assertStrictEqual(state.rcTag, '3.0.0-rc2');
        assertStrictEqual(state.version, '3.0.0');
        assertStrictEqual(state.steps[0].status, 'passed');
        // All subsequent steps should be reset to pending
        assertStrictEqual(state.steps[1].status, 'pending');
        assertStrictEqual(state.steps[2].status, 'pending');
      });

      test('re-running a previously passed step sets target to running in-flight', async () => {
        const $ = createMockEngine();
        const steps = createDefaultVerifySteps();
        steps[1].status = 'passed'; // inventory previously passed

        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps,
          startedAt: Date.now(),
        });

        let capturedStatusDuringExecution: string | null = null;
        const next = async () => {
          const intermediateState = await getVerifyRcState($);
          capturedStatusDuringExecution = intermediateState.steps[1].status;
          return {
            stdout: JSON.stringify({
              step: 'inventory',
              status: 'PASS',
              found: ['foo.tar.gz'],
            }),
          };
        };

        await handleBashToolCall($, { command: 'uv run release-verify inventory' }, next);
        assertStrictEqual(capturedStatusDuringExecution, 'running');
      });

      test('respects mandatory reproducibility when skip_repro_ignored is returned', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        // Tool output indicates automated signing made repro mandatory, ignoring --skip-repro
        const next = async () => ({
          stdout: JSON.stringify({
            step: 'reproducibility',
            mandatory: true,
            skipped: false,
            skip_repro_ignored: true,
            status: 'PASS',
            detail: 'Reproducibility passed (mandatory under automated signing)',
          }),
        });

        await handleBashToolCall($, { command: 'uv run verify-rc repro 3.0.0-rc1 --skip-repro' }, next);

        const state = await getVerifyRcState($);
        assertStrictEqual(state.steps[11].status, 'passed');
        assert(state.steps[11].detail!.includes('Reproducibility passed'));
      });

      test('anchored invocation ignores grep or git commit commands referencing tools', async () => {
        const $ = createMockEngine();
        let nextCalled = false;
        const next = async () => {
          nextCalled = true;
          return { stdout: 'matches found' };
        };

        // grep merely mentions tool name
        await handleBashToolCall($, { command: 'grep -n maven-artifact-verify README.md' }, next);
        assertStrictEqual(nextCalled, true);
        let state = await getVerifyRcState($);
        assertStrictEqual(state, null);

        // git commit message merely mentions release-verify
        await handleBashToolCall($, { command: 'git commit -m "chore: release-verify version fix"' }, next);
        state = await getVerifyRcState($);
        assertStrictEqual(state, null);
      });

      test('handles error-only JSON on bad input by setting status to failed', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        const next = async () => ({
          exitCode: 2,
          isError: true,
          stdout: JSON.stringify({
            error: 'unrecognized arguments: --bad-flag',
          }),
        });

        await handleBashToolCall($, { command: 'uv run release-verify binaries --bad-flag' }, next);

        const state = await getVerifyRcState($);
        const step = state.steps.find((s: any) => s.id === 'binary-exclusion');
        assertStrictEqual(step.status, 'failed');
        assert(step.detail.includes('unrecognized arguments: --bad-flag'));
        assertStrictEqual(state.overallStatus, 'failed');
      });

      test('release-config load is decoupled: does not reset preflight status or wipe state', async () => {
        const $ = createMockEngine();

        // 1. Preflight runs and passes
        await handleBashToolCall(
          $,
          { command: 'uv run release-config preflight --skill verify-rc 2.11.0-rc1' },
          async () => ({
            stdout: JSON.stringify({
              ok: true,
              skill: 'verify-rc',
              blockers: [],
              warnings: [],
              values: { rc_tag: '2.11.0-rc1' },
            }),
          })
        );
        let state = await getVerifyRcState($);
        assertStrictEqual(state.steps[0].status, 'passed');
        assertStrictEqual(state.rcTag, '2.11.0-rc1');

        // 2. Redirected load runs with empty stdout
        await handleBashToolCall(
          $,
          { command: 'uv run release-config load 2.11.0-rc1 > /tmp/load.json' },
          async () => ({ stdout: '' })
        );

        state = await getVerifyRcState($);
        assertStrictEqual(state.steps[0].status, 'passed');
        assertStrictEqual(state.rcTag, '2.11.0-rc1');
      });

      test('anchored tag extraction ignores non-step commands and --dir paths', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        // Arbitrary non-step command with -rc2
        await handleBashToolCall($, { command: 'git show 3.0.0-rc2' }, async () => ({ stdout: 'commit...' }));
        let state = await getVerifyRcState($);
        assertStrictEqual(state.rcTag, '3.0.0-rc1');

        // Step command with --dir containing another rc string
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify inventory --dir /tmp/other-1.0.0-rc9' },
          async () => ({
            stdout: JSON.stringify({ step: 'inventory', status: 'PASS', found: ['a.tar.gz'] }),
          })
        );
        state = await getVerifyRcState($);
        assertStrictEqual(state.rcTag, '3.0.0-rc1'); // Did not reset to 1.0.0-rc9
        assertStrictEqual(state.steps.find((s: any) => s.id === 'inventory').status, 'passed');
      });

      test('processes batch release-verify all failure by marking all batch steps failed', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        // Simulate release-verify all exit 2 with error JSON
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify all' },
          async () => ({
            exitCode: 2,
            isError: true,
            stdout: JSON.stringify({ error: 'Missing required flag: --keys' }),
          })
        );

        const state = await getVerifyRcState($);
        const batchIds = [
          'inventory',
          'signatures',
          'checksums',
          'notice-license',
          'binary-exclusion',
          'source-tree-integrity',
          'version-consistency',
        ];
        for (const id of batchIds) {
          const s = state.steps.find((step: any) => step.id === id);
          assertStrictEqual(s.status, 'failed');
          assert(s.detail.includes('Missing required flag: --keys'));
        }
        assertStrictEqual(state.overallStatus, 'failed');
      });

      test('processes batch release-verify all failure when next() throws exception', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        try {
          await handleBashToolCall($, { command: 'uv run release-verify all' }, async () => {
            throw new Error('Command timed out after 120s');
          });
        } catch (err: any) {
          assert(err.message.includes('Command timed out'));
        }

        const state = await getVerifyRcState($);
        const batchIds = [
          'inventory',
          'signatures',
          'checksums',
          'notice-license',
          'binary-exclusion',
          'source-tree-integrity',
          'version-consistency',
        ];
        for (const id of batchIds) {
          const s = state.steps.find((step: any) => step.id === id);
          assertStrictEqual(s.status, 'failed');
          assert(s.detail.includes('Command timed out after 120s'));
        }
        assertStrictEqual(state.overallStatus, 'failed');
      });

      test('extracts wrapped tool.call response shape { result: { stdout, exitCode } }', async () => {
        const $ = createMockEngine();
        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps: createDefaultVerifySteps(),
          startedAt: Date.now(),
        });

        // Wrapped response format
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify inventory' },
          async () => ({
            result: {
              stdout: JSON.stringify({
                step: 'inventory',
                status: 'PASS',
                found: ['pkg-3.0.0.tar.gz'],
              }),
              exitCode: 0,
            },
          })
        );

        const state = await getVerifyRcState($);
        const invStep = state.steps.find((s: any) => s.id === 'inventory');
        assertStrictEqual(invStep.status, 'passed');
      });

      test('authoritative verdict reconciles REVIEW rows and sets overall status', async () => {
        const $ = createMockEngine();
        const steps = createDefaultVerifySteps();
        // notice-license in review
        const nl = steps.find((s) => s.id === 'notice-license');
        if (nl) nl.status = 'running';

        await setVerifyRcState($, {
          rcTag: '3.0.0-rc1',
          version: '3.0.0',
          overallStatus: 'running',
          steps,
          startedAt: Date.now(),
        });

        // Verdict output resolves notice-license via step_summary
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify verdict --status notice-license=PASS' },
          async () => ({
            stdout: JSON.stringify({
              step: 'verdict',
              overall: 'PASS',
              step_summary: [
                { step: 'inventory', status: 'PASS' },
                { step: 'notice-license', status: 'PASS' },
              ],
            }),
          })
        );

        const state = await getVerifyRcState($);
        const resolvedNl = state.steps.find((s: any) => s.id === 'notice-license');
        assertStrictEqual(resolvedNl.status, 'passed');
        assertStrictEqual(state.steps.find((s: any) => s.id === 'verdict').status, 'passed');
        assertStrictEqual(state.overallStatus, 'passed');
        assert(typeof state.completedAt === 'number');
      });
    });

    describe('end-to-end verification lifecycle simulation', () => {
      test('simulates complete 13-step verification run to PASS', async () => {
        const $ = createMockEngine();

        // 1. Step 0: Pre-flight check
        await handleBashToolCall(
          $,
          { command: 'uv run release-config preflight --skill verify-rc 2.11.0-rc1' },
          async () => ({
            stdout: JSON.stringify({
              ok: true,
              skill: 'verify-rc',
              blockers: [],
              warnings: [],
              values: { rc_tag: '2.11.0-rc1' },
            }),
          })
        );
        let state = await getVerifyRcState($);
        assertStrictEqual(state.steps[0].status, 'passed');
        assertStrictEqual(state.overallStatus, 'running');

        // 2. Step 1: Inventory (no JVM files)
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify inventory' },
          async () => ({
            stdout: JSON.stringify({
              step: 'inventory',
              status: 'PASS',
              found: ['foo-2.11.0.tar.gz', 'foo-2.11.0.tar.gz.asc', 'foo-2.11.0.tar.gz.sha512'],
            }),
          })
        );
        state = await getVerifyRcState($);
        assertStrictEqual(state.steps[1].status, 'passed');
        assertStrictEqual(state.steps[7].status, 'skipped'); // jvm-artefacts
        assertStrictEqual(state.steps[8].status, 'skipped'); // nexus-staging
        assertStrictEqual(state.steps[11].status, 'pending'); // reproducibility pending until verify-rc repro

        // 3. Step 2: Signatures
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify signatures' },
          async () => ({
            stdout: JSON.stringify({ step: 'signatures', status: 'PASS', detail: 'Good signature' }),
          })
        );

        // 4. Step 3: Checksums
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify checksums' },
          async () => ({
            stdout: JSON.stringify({ step: 'checksums', status: 'PASS' }),
          })
        );

        // 5. Step 4: RAT license headers
        await handleBashToolCall(
          $,
          { command: 'uv run release-management verify-rc rat' },
          async () => ({
            stdout: JSON.stringify({ step: 'rat-license-headers', status: 'PASS' }),
          })
        );

        // 6. Step 5: NOTICE and LICENSE
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify notice-license' },
          async () => ({
            stdout: JSON.stringify({ step: 'notice-license', status: 'PASS' }),
          })
        );

        // 7. Step 6: Binary exclusion
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify binaries' },
          async () => ({
            stdout: JSON.stringify({ step: 'binary-exclusion', status: 'PASS' }),
          })
        );

        // 8. Step 7: Source integrity
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify symlinks' },
          async () => ({
            stdout: JSON.stringify({ step: 'source-tree-integrity', status: 'PASS' }),
          })
        );

        // 9. Step 8: Version consistency
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify version' },
          async () => ({
            stdout: JSON.stringify({ step: 'version-consistency', status: 'PASS' }),
          })
        );

        // 10. Step 9: Reproducibility
        await handleBashToolCall(
          $,
          { command: 'uv run verify-rc repro 2.11.0-rc1 --skip-repro' },
          async () => ({
            stdout: JSON.stringify({
              mandatory: false,
              skipped: true,
              skip_reason: '--skip-repro was passed',
              status: 'SKIP',
            }),
          })
        );
        state = await getVerifyRcState($);
        assertStrictEqual(state.steps[11].status, 'skipped');

        // 11. Step 10: Final verdict
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify verdict' },
          async () => ({
            stdout: JSON.stringify({ step: 'verdict', overall: 'PASS', step_summary: [] }),
          })
        );

        const finalState = await getVerifyRcState($);
        assertStrictEqual(finalState.overallStatus, 'passed');
        assert(typeof finalState.completedAt === 'number');

        const summary = calculateProgressSummary(finalState.steps);
        assertStrictEqual(summary.passed, 10);
        assertStrictEqual(summary.skipped, 3);
        assertStrictEqual(summary.failed, 0);
        assertStrictEqual(summary.completed, 13);
        assertStrictEqual(summary.total, 13);
      });

      test('simulates failure lifecycle with hard blocker at signatures step', async () => {
        const $ = createMockEngine();

        // Step 0: Preflight PASS
        await handleBashToolCall(
          $,
          { command: 'uv run release-config preflight 3.0.0-rc1' },
          async () => ({
            stdout: JSON.stringify({
              ok: true,
              skill: 'verify-rc',
              blockers: [],
              warnings: [],
              values: { rc_tag: '3.0.0-rc1' },
            }),
          })
        );

        // Step 1: Inventory PASS
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify inventory' },
          async () => ({
            stdout: JSON.stringify({ step: 'inventory', status: 'PASS', found: ['a.tar.gz', 'a.tar.gz.asc'] }),
          })
        );

        // Step 2: Signatures FAIL
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify signatures' },
          async () => ({
            stdout: JSON.stringify({
              step: 'signatures',
              status: 'FAIL',
              detail: 'Key 0xABCD1234 not found in staged KEYS file from dist.apache.org',
            }),
          })
        );

        const failedState = await getVerifyRcState($);
        assertStrictEqual(failedState.overallStatus, 'failed');
        const sigStep = failedState.steps.find((s: any) => s.id === 'signatures')!;
        assertStrictEqual(sigStep.status, 'failed');
        assert(sigStep.detail!.includes('Key 0xABCD1234 not found'));

        // Verify pane reflects hard blocker
        const pane = renderVerifyRcPane($, {}, failedState);
        assert(pane !== null);
        const headerText = pane.children[0].children[1].children[0];
        assert(headerText.includes('Status: FAILED'));
        const footerText = pane.children[2].children[0].children[0];
        assert(footerText.includes('Verdict: FAIL (Hard blocker encountered; do not release candidate)'));
      });

      test('simulates real skill command order (preflight -> redirected load -> steps -> verdict)', async () => {
        const $ = createMockEngine();

        // 1. Step 0: Pre-flight check
        await handleBashToolCall(
          $,
          { command: 'uv run release-config preflight --skill verify-rc 2.11.0-rc1' },
          async () => ({
            stdout: JSON.stringify({
              ok: true,
              skill: 'verify-rc',
              blockers: [],
              warnings: [],
              values: { rc_tag: '2.11.0-rc1' },
            }),
          })
        );
        let state = await getVerifyRcState($);
        assertStrictEqual(state.steps[0].status, 'passed');
        assertStrictEqual(state.rcTag, '2.11.0-rc1');

        // 2. Redirected load command (output saved to scratch, stdout empty)
        await handleBashToolCall(
          $,
          { command: 'uv run release-config load 2.11.0-rc1 > /scratch/verify-rc-load.json' },
          async () => ({ stdout: '' })
        );
        state = await getVerifyRcState($);
        // Pre-flight must NOT be wiped or reset to running
        assertStrictEqual(state.steps[0].status, 'passed');
        assertStrictEqual(state.rcTag, '2.11.0-rc1');

        // 3. Verification steps run
        // Inventory
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify inventory' },
          async () => ({
            stdout: JSON.stringify({
              step: 'inventory',
              status: 'PASS',
              found: ['foo-2.11.0.tar.gz', 'foo-2.11.0.tar.gz.asc', 'foo-2.11.0.tar.gz.sha512'],
            }),
          })
        );

        // Signatures, Checksums, RAT
        await handleBashToolCall($, { command: 'uv run release-verify signatures' }, async () => ({
          stdout: JSON.stringify({ step: 'signatures', status: 'PASS' }),
        }));
        await handleBashToolCall($, { command: 'uv run release-verify checksums' }, async () => ({
          stdout: JSON.stringify({ step: 'checksums', status: 'PASS' }),
        }));
        await handleBashToolCall($, { command: 'uv run release-management verify-rc rat' }, async () => ({
          stdout: JSON.stringify({ step: 'rat-license-headers', status: 'PASS' }),
        }));

        // Notice & license returns REVIEW -> normalized to running
        await handleBashToolCall($, { command: 'uv run release-verify notice-license' }, async () => ({
          stdout: JSON.stringify({ step: 'notice-license', status: 'REVIEW', detail: 'Manual review required' }),
        }));
        state = await getVerifyRcState($);
        assertStrictEqual(state.steps.find((s: any) => s.id === 'notice-license').status, 'running');
        assertStrictEqual(state.overallStatus, 'running');

        // Binaries, Symlinks, Version
        await handleBashToolCall($, { command: 'uv run release-verify binaries' }, async () => ({
          stdout: JSON.stringify({ step: 'binary-exclusion', status: 'PASS' }),
        }));
        await handleBashToolCall($, { command: 'uv run release-verify symlinks' }, async () => ({
          stdout: JSON.stringify({ step: 'source-tree-integrity', status: 'PASS' }),
        }));
        await handleBashToolCall($, { command: 'uv run release-verify version' }, async () => ({
          stdout: JSON.stringify({ step: 'version-consistency', status: 'PASS' }),
        }));

        // Reproducibility skipped
        await handleBashToolCall(
          $,
          { command: 'uv run verify-rc repro 2.11.0-rc1 --skip-repro' },
          async () => ({
            stdout: JSON.stringify({ mandatory: false, skipped: true, status: 'SKIP' }),
          })
        );

        // 4. Final verdict with manual override: notice-license=PASS
        await handleBashToolCall(
          $,
          { command: 'uv run release-verify verdict --status notice-license=PASS' },
          async () => ({
            stdout: JSON.stringify({
              step: 'verdict',
              overall: 'PASS',
              step_summary: [
                { step: 'inventory', status: 'PASS' },
                { step: 'signatures', status: 'PASS' },
                { step: 'checksums', status: 'PASS' },
                { step: 'rat-license-headers', status: 'PASS' },
                { step: 'notice-license', status: 'PASS' },
                { step: 'binary-exclusion', status: 'PASS' },
                { step: 'jvm-artefacts', status: 'SKIP' },
                { step: 'nexus-staging', status: 'SKIP' },
                { step: 'source-tree-integrity', status: 'PASS' },
                { step: 'version-consistency', status: 'PASS' },
                { step: 'reproducibility', status: 'SKIP' },
              ],
            }),
          })
        );

        const finalState = await getVerifyRcState($);
        assertStrictEqual(finalState.overallStatus, 'passed');
        assert(typeof finalState.completedAt === 'number');

        // Notice-license reconciled to passed from step_summary
        const nlStep = finalState.steps.find((s: any) => s.id === 'notice-license');
        assertStrictEqual(nlStep.status, 'passed');

        // Pre-flight still passed
        assertStrictEqual(finalState.steps[0].status, 'passed');

        // Verdict step itself passed
        assertStrictEqual(finalState.steps[12].status, 'passed');

        // Render check
        const pane = renderVerifyRcPane($, {}, finalState);
        assert(pane !== null);
        const headerText = pane.children[0].children[1].children[0];
        assert(headerText.includes('Progress: 13/13 completed · Status: PASSED'));
        const footerText = pane.children[2].children[0].children[0];
        assert(footerText.includes('Verdict: PASS (All mechanical checks passed; voter obligation remains)'));
      });
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
