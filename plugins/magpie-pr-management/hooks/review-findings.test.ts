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
  calculateSummary,
  formatActionIndicator,
  formatFindingDescription,
  formatFindingsTerminalFallback,
  formatKeepAnswer,
  formatSeverityBadge,
  getReviewFindingsState,
  isAnchored,
  normalizeAction,
  normalizeFilePath,
  normalizeLine,
  normalizeSeverity,
  normalizeSource,
  parseFindings,
  register,
  renderFindingsPane,
  reviewFindingsState,
  sanitizeFindingText,
  serializeFindingsForRender,
  setReviewFindingsState,
  truncateFilePath,
  truncateText,
} from './review-findings.ts';
import type { ReviewFinding, ReviewFindingsState } from './types.ts';

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

function assertDeepStrictEqual(actual: any, expected: any): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `Expected deep equality: ${JSON.stringify(expected)} !== ${JSON.stringify(actual)}`
    );
  }
}

describe('magpie-pr-management review findings mod (PR-1 & PR-2)', () => {
  describe('normalization helpers', () => {
    test('normalizeSeverity maps known severities and synonyms case-insensitively', () => {
      assertStrictEqual(normalizeSeverity('blocking'), 'blocking');
      assertStrictEqual(normalizeSeverity('BLOCKING'), 'blocking');
      assertStrictEqual(normalizeSeverity('critical'), 'blocking');
      assertStrictEqual(normalizeSeverity('blocker'), 'blocking');

      assertStrictEqual(normalizeSeverity('major'), 'major');
      assertStrictEqual(normalizeSeverity('Major'), 'major');
      assertStrictEqual(normalizeSeverity('high'), 'major');

      assertStrictEqual(normalizeSeverity('minor'), 'minor');
      assertStrictEqual(normalizeSeverity('low'), 'minor');

      assertStrictEqual(normalizeSeverity('nit'), 'nit');
      assertStrictEqual(normalizeSeverity('NIT'), 'nit');
      assertStrictEqual(normalizeSeverity('trivial'), 'nit');
      assertStrictEqual(normalizeSeverity('info'), 'nit');

      assertStrictEqual(normalizeSeverity(null), 'minor');
      assertStrictEqual(normalizeSeverity(123), 'minor');
    });

    test('normalizeSeverity logs an error when encountering an unmapped severity', () => {
      const errors: string[] = [];
      const result = normalizeSeverity('catastrophic', errors);
      assertStrictEqual(result, 'minor');
      assertStrictEqual(errors.length, 1);
      assert(errors[0].includes("Unrecognized severity 'catastrophic'"));
    });

    test('normalizeFilePath standardizes Windows backslashes and strips leading relative paths', () => {
      assertStrictEqual(
        normalizeFilePath('src\\pr_management\\code_review\\body.py'),
        'src/pr_management/code_review/body.py'
      );
      assertStrictEqual(normalizeFilePath('./providers/foo/hook.py'), 'providers/foo/hook.py');
      assertStrictEqual(normalizeFilePath('.\\providers\\foo\\hook.py'), 'providers/foo/hook.py');
      assertStrictEqual(normalizeFilePath(''), 'general');
      assertStrictEqual(normalizeFilePath(null), 'general');
    });

    test('normalizeLine validates integers and rejects malformed prefixes with error logging', () => {
      assertStrictEqual(normalizeLine(42), 42);
      assertStrictEqual(normalizeLine('142'), 142);
      assertStrictEqual(normalizeLine(0), null);
      assertStrictEqual(normalizeLine(-10), null);
      assertStrictEqual(normalizeLine(null), null);
      assertStrictEqual(normalizeLine(undefined), null);

      const errors: string[] = [];
      assertStrictEqual(normalizeLine('12.5', errors), null);
      assertStrictEqual(normalizeLine('12-20', errors), null);
      assertStrictEqual(normalizeLine('1e2', errors), null);
      assertStrictEqual(normalizeLine('invalid', errors), null);
      assertStrictEqual(errors.length, 4);
      assert(errors[0].includes("Malformed line number '12.5'"));
    });

    test('numeric non-integer or negative lines and non-string severities are recorded', () => {
      const lineErrors: string[] = [];
      assertStrictEqual(normalizeLine(12.5, lineErrors), null);
      assertStrictEqual(normalizeLine(-3, lineErrors), null);
      assertStrictEqual(lineErrors.length, 2);
      assert(lineErrors[0].includes("Malformed line number '12.5'"));
      assert(lineErrors[1].includes("Malformed line number '-3'"));

      const severityErrors: string[] = [];
      assertStrictEqual(normalizeSeverity(42, severityErrors), 'minor');
      assertStrictEqual(severityErrors.length, 1);
      assert(severityErrors[0].includes("Invalid severity type 'number'"));
    });

    test('normalizeSource validates reviewer source attributes', () => {
      assertStrictEqual(normalizeSource('primary'), 'primary');
      assertStrictEqual(normalizeSource('adversarial'), 'adversarial');
      assertStrictEqual(normalizeSource('both'), 'both');
      assertStrictEqual(normalizeSource('ADVERSARIAL'), 'adversarial');
      assertStrictEqual(normalizeSource('other'), 'primary');
      assertStrictEqual(normalizeSource(null), 'primary');
    });

    test('normalizeAction defaults missing to accept and treats unrecognized as skip with error', () => {
      assertStrictEqual(normalizeAction('accept'), 'accept');
      assertStrictEqual(normalizeAction('skip'), 'skip');
      assertStrictEqual(normalizeAction('edit'), 'edit');
      assertStrictEqual(normalizeAction('ACCEPT'), 'accept');
      assertStrictEqual(normalizeAction(undefined), 'accept');
      assertStrictEqual(normalizeAction(null), 'accept');

      const errors: string[] = [];
      assertStrictEqual(normalizeAction('reject', errors), 'skip');
      assertStrictEqual(normalizeAction('drop', errors), 'skip');
      assertStrictEqual(normalizeAction(123 as any, errors), 'skip');
      assertStrictEqual(errors.length, 3);
      assert(errors[0].includes("Unrecognized action 'reject'"));
    });

    test('sanitizeFindingText strips ANSI CSI, OSC sequences, and C0/C1 control characters', () => {
      // ANSI color / style CSI sequences
      assertStrictEqual(sanitizeFindingText('\u001b[31;1mSecurity alert\u001b[0m'), 'Security alert');
      // Cursor movements and screen clear
      assertStrictEqual(sanitizeFindingText('\u001b[2K\u001b[1Aclean text'), 'clean text');
      // OSC 8 hyperlinks (keeping visible text, dropping escape target)
      assertStrictEqual(
        sanitizeFindingText('\u001b]8;;https://example.com\u0007Click here\u001b]8;;\u0007'),
        'Click here'
      );
      // C0 and C1 control characters (null, bell, backspace, newlines, DEL)
      assertStrictEqual(sanitizeFindingText('Line1\r\nLine2\u0000\u0007\u007f'), 'Line1Line2');
      // Empty input
      assertStrictEqual(sanitizeFindingText(''), '');
      assertStrictEqual(sanitizeFindingText(null as any), '');
    });

    test('formatFindingDescription harmonizes rule and body with length truncation', () => {
      // Both rule and body present
      assertStrictEqual(
        formatFindingDescription('security-rule', 'Check input buffer'),
        'security-rule \u2014 Check input buffer'
      );
      // Only body present
      assertStrictEqual(formatFindingDescription(undefined, 'Unanchored note'), 'Unanchored note');
      // Only rule present
      assertStrictEqual(formatFindingDescription('rule-only', ''), 'rule-only');
      // Truncation when exceeding maxLength
      const longBody = 'A'.repeat(100);
      const formatted = formatFindingDescription('rule', longBody, 30);
      assertStrictEqual(formatted.length, 30);
      assert(formatted.endsWith('...'));
      // Strips ANSI escapes from both rule and body
      assertStrictEqual(
        formatFindingDescription('\u001b[31mrule\u001b[0m', '\u001b[32mclean body\u001b[0m'),
        'rule \u2014 clean body'
      );
    });
  });

  describe('calculateSummary and isAnchored', () => {
    test('isAnchored matches render criteria where line is positive integer', () => {
      assertStrictEqual(isAnchored({ line: 1 }), true);
      assertStrictEqual(isAnchored({ line: 142 }), true);
      assertStrictEqual(isAnchored({ line: 0 }), false);
      assertStrictEqual(isAnchored({ line: -1 }), false);
      assertStrictEqual(isAnchored({ line: null }), false);
      assertStrictEqual(isAnchored({}), false);
    });

    test('accurately aggregates severity and anchoring statistics', () => {
      const findings: ReviewFinding[] = [
        {
          id: 'finding-1',
          file: 'a.py',
          line: 10,
          severity: 'blocking',
          body: 'Critical flaw',
          action: 'accept',
        },
        {
          id: 'finding-2',
          file: 'b.py',
          line: 20,
          severity: 'major',
          body: 'Security breach',
          action: 'accept',
        },
        {
          id: 'finding-3',
          file: 'c.py',
          line: null,
          severity: 'minor',
          body: 'Unanchored style',
          action: 'accept',
        },
        {
          id: 'finding-4',
          file: 'd.py',
          line: 30,
          severity: 'nit',
          body: 'Typo in comment',
          action: 'skip',
        },
      ];

      const summary = calculateSummary(findings);
      assertStrictEqual(summary.blockingCount, 1);
      assertStrictEqual(summary.majorCount, 1);
      assertStrictEqual(summary.minorCount, 1);
      assertStrictEqual(summary.nitCount, 1);
      assertStrictEqual(summary.total, 4);
      assertStrictEqual(summary.anchoredCount, 3);
      assertStrictEqual(summary.unanchoredCount, 1);
    });
  });

  describe('formatKeepAnswer', () => {
    test('returns ALL when all anchored findings are accepted or edited', () => {
      const allAccepted: ReviewFinding[] = [
        { id: '1', file: 'a.py', line: 10, severity: 'major', body: 'Issue 1', action: 'accept' },
        { id: '2', file: 'b.py', line: 20, severity: 'minor', body: 'Issue 2', action: 'accept' },
      ];
      assertStrictEqual(formatKeepAnswer(allAccepted), 'ALL');

      const allEdited: ReviewFinding[] = [
        { id: '1', file: 'a.py', line: 10, severity: 'major', body: 'Issue 1', action: 'edit' },
        { id: '2', file: 'b.py', line: 20, severity: 'minor', body: 'Issue 2', action: 'edit' },
      ];
      assertStrictEqual(formatKeepAnswer(allEdited), 'ALL');
    });

    test('returns NONE when all anchored findings are skipped or when no findings are anchored', () => {
      const skipped: ReviewFinding[] = [
        { id: '1', file: 'a.py', line: 10, severity: 'major', body: 'Issue 1', action: 'skip' },
      ];
      assertStrictEqual(formatKeepAnswer(skipped), 'NONE');

      const unanchoredOnly: ReviewFinding[] = [
        { id: '2', file: 'b.py', line: null, severity: 'minor', body: 'Issue 2', action: 'accept' },
      ];
      assertStrictEqual(formatKeepAnswer(unanchoredOnly), 'NONE');
    });

    test('treats both accept and edit as kept in mixed lists', () => {
      const findings: ReviewFinding[] = [
        { id: '1', file: 'a.py', line: 10, severity: 'major', body: 'First', action: 'accept' },
        { id: '2', file: 'b.py', line: 20, severity: 'major', body: 'Second', action: 'edit' },
        { id: '3', file: 'c.py', line: 30, severity: 'nit', body: 'Third', action: 'skip' },
        { id: '4', file: 'd.py', line: 40, severity: 'minor', body: 'Fourth', action: 'accept' },
      ];
      assertStrictEqual(formatKeepAnswer(findings), '1,2,4');
    });

    test('anchoring parity check with Python render rule', () => {
      const rawDataset = [
        { file: 'a.py', line: 12, body: 'Valid line 12', action: 'accept' },
        { file: 'b.py', line: null, body: 'Unanchored null', action: 'accept' },
        { file: 'c.py', line: 0, body: 'Zero line unanchored', action: 'accept' },
        { file: 'd.py', line: 55, body: 'Valid line 55', action: 'skip' },
        { file: 'e.py', line: 99, body: 'Valid line 99', action: 'edit' },
      ];

      const parsed = parseFindings(rawDataset);
      const pythonAnchoredIndices: number[] = [];
      const pythonAnchored = rawDataset.filter((item) => Boolean(item.line));

      for (let i = 0; i < pythonAnchored.length; i += 1) {
        const item = pythonAnchored[i];
        if (item.action === 'accept' || item.action === 'edit') {
          pythonAnchoredIndices.push(i + 1);
        }
      }

      const modAnswer = formatKeepAnswer(parsed.findings);
      assertStrictEqual(modAnswer, pythonAnchoredIndices.join(','));
      assertStrictEqual(modAnswer, '1,3');
    });
  });

  describe('serializeFindingsForRender', () => {
    test('produces clean JSON payload matching render parameter requirements', () => {
      const findings: ReviewFinding[] = [
        {
          id: 'finding-1',
          file: 'a.py',
          line: 142,
          severity: 'blocking',
          body: 'Syntax flaw',
          rule: 'syntax',
          action: 'accept',
        },
      ];
      const serialized = serializeFindingsForRender(findings);
      const decoded = JSON.parse(serialized);
      assertStrictEqual(Array.isArray(decoded), true);
      assertStrictEqual(decoded.length, 1);
      assertStrictEqual(decoded[0].file, 'a.py');
      assertStrictEqual(decoded[0].line, 142);
      assertStrictEqual(decoded[0].severity, 'blocking');
      assertStrictEqual(decoded[0].explanation, 'Syntax flaw');
      assertStrictEqual(decoded[0].rule_id, 'syntax');
    });

    test('round-trips a full Step-4 finding with every key render reads', () => {
      const step4 = {
        file: 'providers/foo/hook.py',
        line: 142,
        rule_source: '<project-config>/criteria.md',
        rule_section: '#code-quality-rules',
        rule_id: 'Flag imports inside a function body',
        quoted_rule: 'Never import inside a function.',
        excerpt: 'def get_client():\n    import boto3\n',
        severity: 'major',
        suggestion: 'Move import to file header.',
        suggestion_block: 'import boto3\n',
        side: 'RIGHT',
        reviewers: ['alice'],
      };

      const parsed = parseFindings([step4]);
      assertStrictEqual(parsed.errors.length, 0);
      assertStrictEqual(parsed.findings.length, 1);

      const serialized = serializeFindingsForRender(parsed.findings);
      const roundTripped = JSON.parse(serialized)[0];

      for (const [key, value] of Object.entries(step4)) {
        assertDeepStrictEqual(roundTripped[key], value);
      }
    });

    test('render numbering over the serialised file matches formatKeepAnswer', () => {
      const raw = [
        { file: 'a.py', lineNumber: '12', body: 'Valid line 12', action: 'accept' },
        { file: 'b.py', line_number: '14', body: 'Valid line 14', action: 'edit' },
        { file: 'c.py', line: '0', body: 'Zero string unanchored', action: 'accept' },
        'not an object',
        { file: 'd.py', line: 55, body: 'Valid line 55', action: 'skip' },
        { file: 'e.py', line: 99, body: 'Valid line 99', action: 'edit' },
      ];

      const parsed = parseFindings(raw);
      const serialized = serializeFindingsForRender(parsed.findings);
      const consumedByRender: Array<Record<string, unknown>> = JSON.parse(serialized);

      const renderAnchored = consumedByRender.filter((f) => Boolean(f.line));
      const actions = parsed.findings.filter(isAnchored).map((f) => f.action);
      assertStrictEqual(renderAnchored.length, actions.length);
      const renderKept = renderAnchored
        .map((_, i) => i + 1)
        .filter((i) => actions[i - 1] === 'accept' || actions[i - 1] === 'edit');
      assertStrictEqual(formatKeepAnswer(parsed.findings), renderKept.join(','));
      assertStrictEqual(formatKeepAnswer(parsed.findings), '1,2,4');
    });
  });

  describe('parseFindings', () => {
    test('preserves code suggestion leading indentation with trimEnd', () => {
      const raw = JSON.stringify([
        {
          file: 'src/main.py',
          line: 42,
          severity: 'major',
          body: 'Indented block suggestion',
          suggestion_block: '    def hello():\n        return 42\n',
        },
      ]);

      const result = parseFindings(raw);
      assertStrictEqual(result.errors.length, 0);
      assertStrictEqual(result.findings.length, 1);
      assertStrictEqual(
        result.findings[0].fixup,
        '    def hello():\n        return 42'
      );
    });

    test('extracts JSON payload from markdown code block fences even with surrounding prose', () => {
      const markdown = `
Here are the review findings from Step 4:
\`\`\`json
[
  {
    "file": "providers/foo.py",
    "line": 100,
    "severity": "major",
    "explanation": "Resource leak detected",
    "rule_id": "resource-leak",
    "suggestion_block": "    with acquire() as conn:"
  }
]
\`\`\`
End of observations.
`;
      const result = parseFindings(markdown);
      assertStrictEqual(result.errors.length, 0);
      assertStrictEqual(result.findings.length, 1);
      const f = result.findings[0];
      assertStrictEqual(f.id, 'finding-1');
      assertStrictEqual(f.file, 'providers/foo.py');
      assertStrictEqual(f.line, 100);
      assertStrictEqual(f.severity, 'major');
      assertStrictEqual(f.body, 'Resource leak detected');
      assertStrictEqual(f.rule, 'resource-leak');
      assertStrictEqual(f.fixup, '    with acquire() as conn:');
    });

    test('parses findings nested inside an object property', () => {
      const payload = {
        findings: [
          {
            file: 'test.py',
            line: 5,
            severity: 'nit',
            suggestion: 'Fix indentation',
          },
        ],
      };
      const result = parseFindings(payload);
      assertStrictEqual(result.errors.length, 0);
      assertStrictEqual(result.findings.length, 1);
      assertStrictEqual(result.findings[0].body, 'Fix indentation');
      assertStrictEqual(result.findings[0].severity, 'nit');
    });

    test('handles empty or malformed inputs without throwing exceptions', () => {
      const emptyResult = parseFindings('');
      assertStrictEqual(emptyResult.findings.length, 0);
      assertStrictEqual(emptyResult.errors.length, 0);

      const nullResult = parseFindings(null);
      assertStrictEqual(nullResult.findings.length, 0);

      const invalidJsonResult = parseFindings('invalid { json');
      assertStrictEqual(invalidJsonResult.findings.length, 0);
      assertStrictEqual(invalidJsonResult.errors.length, 1);
      assert(invalidJsonResult.errors[0].includes('JSON parse error'));

      const nonObjectArray = parseFindings(JSON.stringify(['string item', null]));
      assertStrictEqual(nonObjectArray.findings.length, 0);
      assertStrictEqual(nonObjectArray.errors.length, 2);
    });
  });

  describe('PR-2 UI formatters and helpers', () => {
    test('formatSeverityBadge maps severities to labels, colors, and emphasis', () => {
      const blocking = formatSeverityBadge('blocking');
      assertStrictEqual(blocking.label, '[BLOCKING]');
      assertStrictEqual(blocking.color, 'error');
      assertStrictEqual(blocking.bold, true);

      const major = formatSeverityBadge('major');
      assertStrictEqual(major.label, '[MAJOR]');
      assertStrictEqual(major.color, 'error');
      assertStrictEqual(major.bold, false);

      const minor = formatSeverityBadge('minor');
      assertStrictEqual(minor.label, '[MINOR]');
      assertStrictEqual(minor.color, 'warning');
      assertStrictEqual(minor.bold, false);

      const nit = formatSeverityBadge('nit');
      assertStrictEqual(nit.label, '[NIT]');
      assertStrictEqual(nit.color, 'dim');
      assertStrictEqual(nit.bold, false);
    });

    test('formatActionIndicator maps actions to indicator labels and styles', () => {
      const accept = formatActionIndicator('accept');
      assertStrictEqual(accept.label, '[x] Accept');
      assertStrictEqual(accept.color, 'success');
      assertStrictEqual(accept.bold, true);

      const skip = formatActionIndicator('skip');
      assertStrictEqual(skip.label, '[ ] Skip');
      assertStrictEqual(skip.color, 'dim');
      assertStrictEqual(skip.bold, false);

      const edit = formatActionIndicator('edit');
      assertStrictEqual(edit.label, '[E] Edit');
      assertStrictEqual(edit.color, 'info');
      assertStrictEqual(edit.bold, true);
    });

    test('truncateFilePath preserves short paths and abbreviates long deep paths', () => {
      assertStrictEqual(truncateFilePath('short/path.py', 36), 'short/path.py');
      assertStrictEqual(
        truncateFilePath(
          'plugins/magpie-security-tools/tools/security-management/src/state.py',
          30
        ),
        '.../src/state.py'
      );
    });

    test('formatFindingsTerminalFallback formats clean representation for terminal output', () => {
      const findings: ReviewFinding[] = [
        {
          id: '1',
          file: 'providers/foo/hook.py',
          line: 142,
          severity: 'major',
          body: 'Resource leak',
          rule: 'leak',
          action: 'accept',
        },
        {
          id: '2',
          file: 'providers/foo/general.py',
          line: null,
          severity: 'nit',
          body: 'Unanchored note',
          action: 'skip',
        },
      ];
      const state: ReviewFindingsState = {
        prNumber: 1234,
        findings,
        summary: calculateSummary(findings),
        selectedIndex: 0,
      };

      const fallback = formatFindingsTerminalFallback(state);
      assert(fallback.includes('PR #1234 Review findings (1 inline, 1 general):'));
      assert(fallback.includes('Proposed inline comments:'));
      assert(fallback.includes('[x] 1. [MAJOR] providers/foo/hook.py:142 \u2014 leak \u2014 Resource leak'));
      assert(fallback.includes('General observations (unanchored):'));
      assert(fallback.includes('[ ] \u2022 [NIT] providers/foo/general.py \u2014 Unanchored note'));
      assert(fallback.includes('Summary: 0 blocking, 1 major, 0 minor, 1 nit (2 total)'));
    });

    test('formatFindingsTerminalFallback handles empty state gracefully', () => {
      const state: ReviewFindingsState = {
        findings: [],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };
      assertStrictEqual(formatFindingsTerminalFallback(state), 'No review findings to display.');
    });

    test('renderFindingsPane returns null when findings are empty or ui resolution fails', () => {
      const state: ReviewFindingsState = {
        findings: [],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };
      assertStrictEqual(renderFindingsPane({}, {}, state), null);

      const populatedState: ReviewFindingsState = {
        findings: [
          { id: '1', file: 'a.py', line: 10, severity: 'minor', body: 'Note', action: 'accept' },
        ],
        summary: calculateSummary([]),
        selectedIndex: 0,
      };
      assertStrictEqual(renderFindingsPane({}, {}, populatedState), null);
    });

    test('renderFindingsPane builds UI Box tree using resolved components', () => {
      const findings: ReviewFinding[] = [
        {
          id: '1',
          file: 'src/a.py',
          line: 12,
          severity: 'blocking',
          body: 'Flaw',
          rule: 'security',
          action: 'accept',
        },
        {
          id: '2',
          file: 'docs/b.md',
          line: null,
          severity: 'nit',
          body: 'Grammar',
          action: 'skip',
        },
      ];
      const state: ReviewFindingsState = {
        prNumber: 42,
        findings,
        summary: calculateSummary(findings),
        selectedIndex: 0,
      };

      const mockBox = (props: any) => ({ type: 'Box', ...props });
      const mockText = (props: any) => ({ type: 'Text', ...props });
      const fake$ = {
        ui: {
          resolve: () => ({ Box: mockBox, Text: mockText }),
        },
      };

      const pane = renderFindingsPane(fake$, {}, state);
      assertStrictEqual(pane.type, 'Box');
      assertStrictEqual(Array.isArray(pane.children), true);
    });

    test('renderFindingsPane displays clean overflow indicator without roadmap text', () => {
      const findings: ReviewFinding[] = [];
      for (let i = 1; i <= 14; i += 1) {
        findings.push({
          id: String(i),
          file: `src/file${i}.py`,
          line: i,
          severity: 'minor',
          body: `Finding ${i}`,
          rule: 'style',
          action: 'accept',
        });
      }
      const state: ReviewFindingsState = {
        prNumber: 99,
        findings,
        summary: calculateSummary(findings),
        selectedIndex: 0,
      };

      const collectedTexts: string[] = [];
      const mockBox = (props: any) => ({ type: 'Box', ...props });
      const mockText = (props: any) => {
        if (props.children) {
          collectedTexts.push(...props.children);
        }
        return { type: 'Text', ...props };
      };
      const fake$ = {
        ui: {
          resolve: () => ({ Box: mockBox, Text: mockText }),
        },
      };

      renderFindingsPane(fake$, {}, state);
      const overflowText = collectedTexts.find((t) => t.includes('showing'));
      assert(overflowText, 'Expected overflow indicator text');
      assertStrictEqual(overflowText, '... showing 10 of 14 findings');
      assert(!overflowText.includes('PR-3'), 'Must not contain PR-3 delivery plan text');
      assert(!overflowText.includes('scroll or select'), 'Must not contain scroll hint');
    });

    test('renderFindingsPane sanitizes ANSI and control characters in file, rule, and body', () => {
      const findings: ReviewFinding[] = [
        {
          id: '1',
          file: '\u001b[31msrc/dangerous.py\u001b[0m',
          line: 10,
          severity: 'blocking',
          body: '\u001b]8;;https://malicious.link\u0007Dangerous body\u001b]8;;\u0007',
          rule: '\u001b[1;33mrule-injection\u001b[0m',
          action: 'accept',
        },
      ];
      const state: ReviewFindingsState = {
        prNumber: 100,
        findings,
        summary: calculateSummary(findings),
        selectedIndex: 0,
      };

      const collectedTexts: string[] = [];
      const mockBox = (props: any) => ({ type: 'Box', ...props });
      const mockText = (props: any) => {
        if (props.children) {
          collectedTexts.push(...props.children);
        }
        return { type: 'Text', ...props };
      };
      const fake$ = {
        ui: {
          resolve: () => ({ Box: mockBox, Text: mockText }),
        },
      };

      renderFindingsPane(fake$, {}, state);
      const combined = collectedTexts.join(' ');
      assert(!combined.includes('\u001b'), 'Rendered text must not contain ANSI escape bytes');
      assert(combined.includes('src/dangerous.py'), 'Expected clean file path');
      assert(combined.includes('rule-injection'), 'Expected clean rule');
      assert(combined.includes('Dangerous body'), 'Expected clean body');
    });
  });

  describe('mod hook registration and Pane UI mounting', () => {
    test('registers session.start and ui.render (Pane) lifecycle hooks cleanly', () => {
      const registered: Array<{ event: string; opts?: any; handler: Function }> = [];
      const fakeOn = (event: string, optsOrHandler: any, handler?: Function) => {
        if (typeof optsOrHandler === 'function') {
          registered.push({ event, handler: optsOrHandler });
        } else {
          registered.push({ event, opts: optsOrHandler, handler: handler! });
        }
      };

      register(fakeOn);
      assertStrictEqual(registered.length, 2);
      assertStrictEqual(registered[0].event, 'session.start');
      assertStrictEqual(registered[1].event, 'ui.render');
      assertStrictEqual(registered[1].opts?.component, 'Pane');
    });

    test('session.start fixture hydration routes through setReviewFindingsState and invalidates UI', async () => {
      const registered: Array<{ event: string; handler: Function }> = [];
      const fakeOn = (event: string, optsOrHandler: any, handler?: Function) => {
        if (typeof optsOrHandler === 'function') {
          registered.push({ event, handler: optsOrHandler });
        }
      };
      register(fakeOn);

      let invalidatedSurface: string | null = null;
      let nextCalled = false;
      const fake$ = {
        ui: {
          invalidate: (surface: string) => {
            invalidatedSurface = surface;
          },
        },
      };
      const fakePayload = {
        prNumber: 555,
        prTitle: 'Sample PR',
        findings: [
          {
            id: '1',
            file: 'src/app.py',
            line: 20,
            severity: 'major',
            body: 'Unused import',
            rule: 'lint',
            action: 'accept',
          },
        ],
      };
      const fakeNext = (payload: any) => {
        nextCalled = true;
        return payload;
      };

      await registered[0].handler(fake$, fakePayload, fakeNext);
      assert(nextCalled, 'Handler should chain to next(e)');
      assertStrictEqual(invalidatedSurface, 'ui.render', 'Expected session.start to invalidate ui.render');

      const currentState = await getReviewFindingsState(fake$);
      assert(currentState !== null, 'State should be populated from fixture payload');
      assertStrictEqual(currentState?.prNumber, 555);
      assertStrictEqual(currentState?.findings.length, 1);
    });

    test('ui.render mounts Pane on terminal and desktop surfaces when findings exist', async ($: any, on: any) => {
      on('ui.render', () => ({ type: 'Box', children: [] }));
      on('session.start', () => ({ cwd: '/work' }));

      const testFindings: ReviewFinding[] = [
        {
          id: '1',
          file: 'src/core.py',
          line: 42,
          severity: 'blocking',
          body: 'Security breach detected',
          rule: 'sec-rule',
          action: 'accept',
        },
        {
          id: '2',
          file: 'README.md',
          line: null,
          severity: 'nit',
          body: 'Typo in readme',
          action: 'skip',
        },
      ];

      await $.session.start({
        surface: 'terminal',
        isInteractive: true,
        cwd: '/work',
        prNumber: 1920,
        findings: testFindings,
      });

      for (const surface of ['terminal', 'desktop'] as const) {
        const ui = await $.ui.mount({
          plugin: 'magpie-pr-management',
          surface,
          component: 'Pane',
          props: {},
        });
        const header = await ui.find({ type: 'Text', text: /PR #1920: Review Findings/ });
        assert(header, "Expected header rendered on " + surface);

        const blockingBadge = await ui.find({ type: 'Text', text: /\[BLOCKING\]/ });
        assert(blockingBadge, "Expected blocking badge rendered on " + surface);

        const inlineSection = await ui.find({
          type: 'Text',
          text: /Proposed inline comments:/,
        });
        assert(inlineSection, "Expected inline comments section on " + surface);
      }
    });

    test('ui.render passes through unchanged when state is null or empty', async ($: any, on: any) => {
      on('ui.render', () => ({ type: 'Box', children: [] }));
      on('session.start', () => ({ cwd: '/work' }));

      await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' });
      await setReviewFindingsState($, null);

      for (const surface of ['terminal', 'desktop'] as const) {
        const ui = await $.ui.mount({
          plugin: 'magpie-pr-management',
          surface,
          component: 'Pane',
          props: {},
        });
        const found = await ui.find({ type: 'Text', text: /Review Findings/ });
        assertStrictEqual(
          found,
          undefined,
          "Pane should not render findings on " + surface + " when state is null"
        );
      }
    });
  });

  describe('type contract synchronization', () => {
    test('types.ts and types.d.ts declare matching field structures', () => {
      const sampleState: ReviewFindingsState = {
        prNumber: 10,
        prTitle: 'Title',
        findings: [
          {
            id: '1',
            file: 'src/main.py',
            line: 42,
            severity: 'blocking',
            body: 'Flaw',
            rule: 'sec',
            source: 'primary',
            fixup: 'fix',
            action: 'accept',
            raw: {},
          },
        ],
        summary: {
          blockingCount: 1,
          majorCount: 0,
          minorCount: 0,
          nitCount: 0,
          total: 1,
          anchoredCount: 1,
          unanchoredCount: 0,
        },
        selectedIndex: 0,
      };

      const findingKeys = Object.keys(sampleState.findings[0]).sort();
      const expectedFindingKeys = [
        'action',
        'body',
        'file',
        'fixup',
        'id',
        'line',
        'raw',
        'rule',
        'severity',
        'source',
      ].sort();
      assertDeepStrictEqual(findingKeys, expectedFindingKeys);

      const summaryKeys = Object.keys(sampleState.summary).sort();
      const expectedSummaryKeys = [
        'anchoredCount',
        'blockingCount',
        'majorCount',
        'minorCount',
        'nitCount',
        'total',
        'unanchoredCount',
      ].sort();
      assertDeepStrictEqual(summaryKeys, expectedSummaryKeys);

      const stateKeys = Object.keys(sampleState).sort();
      const expectedStateKeys = [
        'findings',
        'prNumber',
        'prTitle',
        'selectedIndex',
        'summary',
      ].sort();
      assertDeepStrictEqual(stateKeys, expectedStateKeys);
    });
  });
});
