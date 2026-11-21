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
import type { VoteTallyState } from './types.js';

import {
  computeRemainingHours,
  deriveVersionFromRcTag,
  evaluateVoteStatus,
  extractJsonFromOutput,
  extractRawOutput,
  formatBandMessage,
  processVoteCommand,
  renderVoteTallyBandComponent,
  sanitizeVoter,
} from './vote-tally-band.js';

import {
  getVoteTallyState,
  handleBashToolCall,
  setVoteTallyState,
  voteTallyState,
} from './verify-rc-pane.js';

function must<T>(v: T | null | undefined, what = 'value'): T {
  if (v === null || v === undefined) throw new Error(`missing ${what}`);
  return v;
}

function createMockEngine(initialState: VoteTallyState | null = null): any {
  const store = new Map<string, any>();
  if (initialState) {
    store.set('voteTallyState', initialState);
  }

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
      invalidate: (_event: string) => {
        invalidated = true;
      },
      resolve: (e: any) => ({
        Box: (props: any) => ({ type: 'Box', props }),
        Text: (props: any) => ({ type: 'Text', props }),
      }),
      get wasInvalidated() {
        return invalidated;
      },
    },
    getState: () => (store.has('voteTallyState') ? store.get('voteTallyState') : null),
  };
}

describe('magpie-release-management vote-tally-band mod (Issue #2215)', () => {
  describe('normalization and sanitization', () => {
    test('sanitizeVoter strips ANSI escape sequences (CSI and OSC) and control characters', () => {
      const malicious = '\x1b]0;Title\x07\x1b[31;1m@alice_pmc\x1b[0m\x00\x07';
      const clean = sanitizeVoter(malicious);
      if (clean !== 'alice_pmc') {
        throw new Error(`expected alice_pmc, got ${clean}`);
      }
    });

    test('sanitizeVoter strips Unicode bidirectional overrides, zero-width, and variation selectors', () => {
      const spoofed = '\u202E@malicious\u200B_voter\u202C\uFEFF\uFE0F\u200E';
      const clean = sanitizeVoter(spoofed);
      if (clean !== 'malicious_voter') {
        throw new Error(`expected malicious_voter, got ${clean}`);
      }
    });

    test('sanitizeVoter removes backticks, html delimiters, and bounds length', () => {
      const input = '`voter<script src="evil.js">`' + 'a'.repeat(60);
      const clean = sanitizeVoter(input, 30);
      if (clean.includes('<') || clean.includes('`') || clean.includes('"')) {
        throw new Error(`unstripped delimiters in ${clean}`);
      }
      if (clean.length > 30) {
        throw new Error(`expected length <= 30, got ${clean.length}`);
      }
    });

    test('sanitizeVoter handles empty or non-string inputs safely', () => {
      if (sanitizeVoter('') !== '') throw new Error('expected empty string');
      if (sanitizeVoter(null as any) !== '') throw new Error('expected empty string on null');
    });

    test('deriveVersionFromRcTag extracts version from rc tags', () => {
      if (deriveVersionFromRcTag('3.0.0-rc1') !== '3.0.0') throw new Error('3.0.0 mismatch');
      if (deriveVersionFromRcTag('v2.10.1-rc2') !== '2.10.1') throw new Error('2.10.1 mismatch');
      if (deriveVersionFromRcTag('1.0.0.rc4') !== '1.0.0') throw new Error('1.0.0 mismatch');
      if (deriveVersionFromRcTag('custom-tag') !== 'custom-tag') throw new Error('fallback mismatch');
    });
  });

  describe('countdown and ASF vote evaluation', () => {
    test('computeRemainingHours computes remaining window accurately', () => {
      const now = Date.parse('2026-11-21T12:00:00Z');
      const opened24hAgo = new Date(now - 24 * 3600 * 1000).toISOString();
      const remaining = computeRemainingHours(opened24hAgo, 72, now);
      if (remaining !== 48) {
        throw new Error(`expected 48 hours remaining, got ${remaining}`);
      }
    });

    test('computeRemainingHours clamps expired or boundary time at 0', () => {
      const now = Date.parse('2026-11-21T12:00:00Z');
      const opened80hAgo = new Date(now - 80 * 3600 * 1000).toISOString();
      if (computeRemainingHours(opened80hAgo, 72, now) !== 0) {
        throw new Error('expected 0 hours remaining for expired vote');
      }
    });

    test('evaluateVoteStatus correctly marks status based on ASF bylaws', () => {
      // 1. Voting active, criteria met (3 positive binding, 0 negative)
      const activePassed = evaluateVoteStatus({ plus: 3, minus: 0 }, 24);
      if (activePassed !== 'passed') throw new Error(`expected passed, got ${activePassed}`);

      // 2. Voting active, criteria met with dissenting vote (4 positive binding, 1 negative) -> majority holds!
      const activeMajority = evaluateVoteStatus({ plus: 4, minus: 1 }, 24);
      if (activeMajority !== 'passed') throw new Error(`expected passed for +4/-1 majority, got ${activeMajority}`);

      // 3. Voting active, criteria not yet met (<3 binding)
      const activeVoting = evaluateVoteStatus({ plus: 2, minus: 0 }, 24);
      if (activeVoting !== 'voting') throw new Error(`expected voting, got ${activeVoting}`);

      // 4. Voting active, tie (+3/-3) -> not majority approval
      const activeTie = evaluateVoteStatus({ plus: 3, minus: 3 }, 24);
      if (activeTie !== 'voting') throw new Error(`expected voting on tie, got ${activeTie}`);

      // 5. Window closed, criteria met
      const closedPassed = evaluateVoteStatus({ plus: 4, minus: 1 }, 0);
      if (closedPassed !== 'closed') throw new Error(`expected closed, got ${closedPassed}`);

      // 6. Window closed, criteria not met
      const closedFailed = evaluateVoteStatus({ plus: 2, minus: 0 }, 0);
      if (closedFailed !== 'failed') throw new Error(`expected failed, got ${closedFailed}`);

      // 7. Authoritative tally result overrides raw evaluation
      const canonicalFailed = evaluateVoteStatus({ plus: 4, minus: 0 }, 24, 'FAILED');
      if (canonicalFailed !== 'failed') throw new Error(`expected failed on canonical tally result, got ${canonicalFailed}`);

      // 8. Halted on ambiguous votes remains in voting state when window active, but fails when window closed
      const halted = evaluateVoteStatus({ plus: 4, minus: 0 }, 24, null, true);
      if (halted !== 'voting') throw new Error(`expected voting when halted on ambiguous, got ${halted}`);

      const haltedClosed = evaluateVoteStatus({ plus: 4, minus: 0 }, 0, null, true);
      if (haltedClosed !== 'failed') throw new Error(`expected failed when halted on ambiguous after close, got ${haltedClosed}`);
    });
  });

  describe('formatBandMessage badge formatting', () => {
    const baseState: VoteTallyState = {
      rcTag: '3.0.0-rc1',
      version: '3.0.0',
      openedAt: '2026-11-20T12:00:00Z',
      windowHours: 72,
      binding: { plus: 3, minus: 0, zero: 0 },
      nonBinding: { plus: 2, minus: 0, zero: 0 },
      vetoes: [],
      status: 'passed',
      updatedAt: Date.now(),
    };

    test('formats CRITERIA MET message when active and >=3 binding votes with 0 dissent', () => {
      const msg = formatBandMessage(baseState, 48);
      if (msg.color !== 'success') throw new Error(`expected success, got ${msg.color}`);
      if (!msg.text.includes('+3 binding (PMC)')) throw new Error(`missing binding count in ${msg.text}`);
      if (!msg.text.includes('CRITERIA MET')) throw new Error(`missing CRITERIA MET in ${msg.text}`);
    });

    test('formats warning CRITERIA MET message when active and >=3 binding votes with dissenting -1', () => {
      const stateWithDissent = {
        ...baseState,
        binding: { plus: 4, minus: 1, zero: 0 },
      };
      const msg = formatBandMessage(stateWithDissent, 48);
      if (msg.color !== 'warning') throw new Error(`expected warning on dissent, got ${msg.color}`);
      if (!msg.text.includes('+4 · -1 binding')) throw new Error(`missing dissent count in ${msg.text}`);
      if (!msg.text.includes('CRITERIA MET (DISSENT: -1)')) throw new Error(`missing dissent note in ${msg.text}`);
    });

    test('formats pending binding votes message when <3 binding votes', () => {
      const state = {
        ...baseState,
        binding: { plus: 2, minus: 0, zero: 0 },
        status: 'voting' as const,
      };
      const msg = formatBandMessage(state, 48);
      if (msg.color !== 'warning') throw new Error(`expected warning, got ${msg.color}`);
      if (!msg.text.includes('Needs 1 more binding +1')) throw new Error(`missing needed count in ${msg.text}`);
    });

    test('formats window closed message when 0 hours remain and criteria met', () => {
      const msg = formatBandMessage(baseState, 0);
      if (msg.color !== 'info') throw new Error(`expected info, got ${msg.color}`);
      if (!msg.text.includes('72h window closed')) throw new Error(`missing window closed in ${msg.text}`);
      if (!msg.text.includes('Ready for [RESULT]')) throw new Error(`missing ready for result in ${msg.text}`);
    });

    test('formats window closed failure message when quorum not met', () => {
      const failedState = { ...baseState, binding: { plus: 2, minus: 0, zero: 0 } };
      const msg = formatBandMessage(failedState, 0);
      if (msg.color !== 'error') throw new Error(`expected error, got ${msg.color}`);
      if (!msg.text.includes('Quorum not met')) throw new Error(`missing quorum not met in ${msg.text}`);
    });

    test('formats error message when status is failed even during active window', () => {
      const failedState = {
        ...baseState,
        binding: { plus: 4, minus: 0, zero: 0 },
        status: 'failed' as const,
      };
      const msg = formatBandMessage(failedState, 48);
      if (msg.color !== 'error') throw new Error(`expected error on failed status, got ${msg.color}`);
      if (!msg.text.includes('Vote failed / blocked')) throw new Error(`missing failed / blocked in ${msg.text}`);
    });
  });

  describe('renderVoteTallyBandComponent UI component', () => {
    test('returns null when state is null (clean prompt guarantee)', () => {
      const res = renderVoteTallyBandComponent(
        (props: any) => ({ type: 'Box', props }),
        (props: any) => ({ type: 'Text', props }),
        null
      );
      if (res !== null) throw new Error('expected null when state is unpopulated');
    });

    test('renders Box/Text component tree when state is active', () => {
      const state: VoteTallyState = {
        rcTag: '3.0.0-rc1',
        version: '3.0.0',
        openedAt: new Date(Date.now() - 24 * 3600 * 1000).toISOString(),
        windowHours: 72,
        binding: { plus: 3, minus: 0, zero: 0 },
        nonBinding: { plus: 1, minus: 0, zero: 0 },
        vetoes: [],
        status: 'passed',
        updatedAt: Date.now(),
      };
      const res = renderVoteTallyBandComponent(
        (props: any) => ({ type: 'Box', props }),
        (props: any) => ({ type: 'Text', props }),
        state
      );
      must(res, 'rendered UI Box');
      if (res.type !== 'Box') throw new Error('expected Box container');
      if (!Array.isArray(res.props.children) || res.props.children.length === 0) {
        throw new Error('expected Text child');
      }
      const textChild = res.props.children[0];
      if (textChild.type !== 'Text') throw new Error('expected Text child');
      if (textChild.props.color !== 'success') throw new Error('expected success color');
    });
  });

  describe('tool call interception and reactive state ingestion', () => {
    test('extractJsonFromOutput parses pure or embedded json', () => {
      const pure = '{"binding_plus1": 3}';
      if (extractJsonFromOutput(pure)?.binding_plus1 !== 3) throw new Error('pure json failed');

      const embedded = 'Notice: loading\n{"binding_plus1": 4}\nDone';
      if (extractJsonFromOutput(embedded)?.binding_plus1 !== 4) throw new Error('embedded json failed');

      if (extractJsonFromOutput('not json at all') !== null) throw new Error('should return null');
    });

    test('extractRawOutput extracts text from varied result envelopes', () => {
      if (extractRawOutput('plain string') !== 'plain string') throw new Error('string extraction failed');
      if (extractRawOutput({ stdout: 'out1' }) !== 'out1') throw new Error('stdout extraction failed');
      if (extractRawOutput({ result: { output: 'out2' } }) !== 'out2') throw new Error('result.output extraction failed');
      if (extractRawOutput({ result: { text: 'out3' } }) !== 'out3') throw new Error('result.text extraction failed');
    });

    test('handleBashToolCall intercepts preflight and initializes vote state', async () => {
      const $ = createMockEngine(null);
      const e = {
        params: {
          command:
            'uv run --project tools/release-config release-config preflight --skill vote-tally 3.0.0-rc1 --vote-opened 2026-11-20T10:00:00Z',
        },
      };
      const next = async () => '{"verdict": "proceed"}';

      await handleBashToolCall($, e, next);
      const stored = await getVoteTallyState($);
      must(stored, 'stored vote state');
      if (stored?.rcTag !== '3.0.0-rc1') throw new Error(`expected 3.0.0-rc1, got ${stored?.rcTag}`);
      if (stored?.openedAt !== '2026-11-20T10:00:00Z') throw new Error('openedAt mismatch');
    });

    test('handleBashToolCall intercepts tally command and updates metrics and status', async () => {
      const existingState: VoteTallyState = {
        rcTag: '3.0.0-rc1',
        version: '3.0.0',
        openedAt: new Date(Date.now() - 10 * 3600 * 1000).toISOString(),
        windowHours: 72,
        binding: { plus: 0, minus: 0, zero: 0 },
        nonBinding: { plus: 0, minus: 0, zero: 0 },
        vetoes: [],
        status: 'voting',
        updatedAt: Date.now(),
      };
      const $ = createMockEngine(existingState);

      const tallyPayload = {
        binding_plus1: 3,
        binding_minus1: 0,
        binding_zero: 0,
        nonbinding_plus1: 2,
        nonbinding_minus1: 0,
        nonbinding_zero: 0,
        voters: [
          { login: 'pmc1', binding: true, value: '+1' },
          { login: 'pmc2', binding: true, value: '+1' },
          { login: 'pmc3', binding: true, value: '+1' },
          { login: 'comm1', binding: false, value: '+1' },
        ],
        result: 'PASSED',
      };

      const e = {
        params: {
          command: 'uv run --project tools/release-management release-management vote-tally tally --votes votes.json',
        },
      };
      const next = async () => JSON.stringify(tallyPayload);

      await handleBashToolCall($, e, next);
      const updated = await getVoteTallyState($);
      must(updated, 'updated state');
      if (updated?.binding.plus !== 3) throw new Error(`expected 3 binding, got ${updated?.binding.plus}`);
      if (updated?.nonBinding.plus !== 2) throw new Error(`expected 2 non-binding, got ${updated?.nonBinding.plus}`);
      if (updated?.status !== 'passed') throw new Error(`expected status passed, got ${updated?.status}`);
    });

    test('handleBashToolCall captures dissenting voters from voters array', async () => {
      const $ = createMockEngine({
        rcTag: '3.0.0-rc1',
        version: '3.0.0',
        openedAt: new Date(Date.now() - 10 * 3600 * 1000).toISOString(),
        windowHours: 72,
        binding: { plus: 0, minus: 0, zero: 0 },
        nonBinding: { plus: 0, minus: 0, zero: 0 },
        vetoes: [],
        status: 'voting',
        updatedAt: Date.now(),
      });

      const tallyPayload = {
        binding_plus1: 4,
        binding_minus1: 1,
        voters: [
          { login: 'pmc1', binding: true, value: '+1' },
          { login: 'pmc2', binding: true, value: '+1' },
          { login: 'pmc3', binding: true, value: '+1' },
          { login: 'pmc4', binding: true, value: '+1' },
          { login: 'pmc_dissent', binding: true, value: '-1' },
        ],
        result: 'PASSED',
      };

      const e = {
        params: {
          command: 'uv run --project tools/release-management release-management vote-tally tally',
        },
      };
      const next = async () => JSON.stringify(tallyPayload);

      await handleBashToolCall($, e, next);
      const updated = await getVoteTallyState($);
      must(updated, 'updated state');
      if (updated?.vetoes.length !== 1 || updated?.vetoes[0] !== 'pmc_dissent') {
        throw new Error(`expected pmc_dissent in vetoes, got ${JSON.stringify(updated?.vetoes)}`);
      }
      if (updated?.status !== 'passed') throw new Error(`expected status passed, got ${updated?.status}`);
    });
  });
});
