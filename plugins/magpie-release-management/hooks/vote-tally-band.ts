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

import type { VoteStatus, VoteTallyState } from './types.js';

/**
 * Sanitizes voter handles, RC tags, and identities by:
 * 1. Stripping ANSI OSC sequences (\x1b\] ... (\x07|\x1b\\))
 * 2. Stripping ANSI CSI sequences (\x1b\[ ... [@-~])
 * 3. Stripping other ANSI escape codes (\x1b[@-Z\\-_])
 * 4. Stripping Unicode bidirectional overrides (\u202A-\u202E, \u2066-\u2069, \u200E, \u200F)
 * 5. Stripping zero-width, invisible, variation selectors, and format control characters (\u200B-\u200D, \uFEFF, \u2060, \u00AD, \uFE00-\uFE0F)
 * 6. Stripping C0 and C1 control characters (\x00-\x1f, \x7f-\x9f)
 * 7. Stripping markdown / HTML delimiters (` < > " ')
 * 8. Stripping leading @ symbols and extraneous whitespace
 * 9. Bounding string length to maxLen (default 40 characters)
 */
export function sanitizeVoter(text: string, maxLen: number = 40): string {
  if (typeof text !== 'string') return '';
  return text
    .replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, '')
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, '')
    .replace(/\x1b[@-Z\\-_]/g, '')
    .replace(/[\u202A-\u202E\u2066-\u2069\u200E\u200F]/g, '')
    .replace(/[\u200B-\u200D\uFEFF\u2060\u00AD\uFE00-\uFE0F]/g, '')
    .replace(/[\x00-\x1f\x7f-\x9f]/g, '')
    .replace(/[`<>"']/g, '')
    .replace(/^@+/, '')
    .trim()
    .slice(0, maxLen);
}

/**
 * Derives the base release version from an RC tag (e.g. "3.0.0-rc1" -> "3.0.0").
 */
export function deriveVersionFromRcTag(rcTag: string): string {
  if (typeof rcTag !== 'string') return '';
  const match = rcTag.match(/^v?([0-9]+(?:\.[0-9]+)+(?:-[a-zA-Z0-9]+)?)(?:-rc[0-9]+|\.rc[0-9]+)$/i);
  return match && match[1] ? match[1] : rcTag.replace(/-rc[0-9]+$/i, '');
}

/**
 * Computes remaining hours in the voting window (clamped at 0).
 */
export function computeRemainingHours(
  openedAt: string,
  windowHours: number = 72,
  nowMs: number = Date.now()
): number {
  try {
    const openedMs = Date.parse(openedAt);
    if (isNaN(openedMs)) return 0;
    const deadlineMs = openedMs + windowHours * 3600 * 1000;
    const diffHours = (deadlineMs - nowMs) / (3600 * 1000);
    return Math.max(0, Math.ceil(diffHours));
  } catch {
    return 0;
  }
}

/**
 * Evaluates the ASF vote status according to PMC bylaws:
 * - Package releases require majority approval with at least 3 positive binding votes:
 *   bindingPlus >= 3 and bindingPlus > bindingMinus.
 * - Negative binding votes are dissenting votes in the majority calculation, not fatal vetoes.
 * - If tally script reported a canonical verdict ('PASSED' / 'FAILED') or halted on ambiguous votes,
 *   that authoritative outcome is respected.
 * - If remainingHours > 0 and criteria met: 'passed' (voting open, criteria satisfied)
 * - If remainingHours > 0 and criteria not yet met: 'voting'
 * - If remainingHours <= 0 and criteria met: 'closed' (ready for [RESULT])
 * - If remainingHours <= 0 and criteria not met: 'failed'
 */
export function evaluateVoteStatus(
  binding: { plus: number; minus: number },
  remainingHours: number,
  tallyResult?: 'PASSED' | 'FAILED' | null,
  haltedOnAmbiguous: boolean = false
): VoteStatus {
  if (haltedOnAmbiguous) {
    return remainingHours <= 0 ? 'failed' : 'voting';
  }

  if (tallyResult === 'FAILED') {
    return 'failed';
  }

  const criteriaMet =
    tallyResult === 'PASSED' || (binding.plus >= 3 && binding.plus > binding.minus);

  if (remainingHours > 0) {
    return criteriaMet ? 'passed' : 'voting';
  } else {
    return criteriaMet ? 'closed' : 'failed';
  }
}

/**
 * Formats the badge text and color for the AbovePrompt banner.
 */
export function formatBandMessage(
  state: VoteTallyState,
  remainingHours: number
): { text: string; color: 'success' | 'warning' | 'error' | 'info' } {
  const rc = sanitizeVoter(state.rcTag || 'RC');
  const bp = state.binding?.plus ?? 0;
  const bm = state.binding?.minus ?? 0;
  const nbp = state.nonBinding?.plus ?? 0;
  const nbm = state.nonBinding?.minus ?? 0;
  const windowHours = state.windowHours || 72;
  const dissentPart = bm > 0 ? ` \u00B7 -${bm} binding` : '';
  const nonBindingDissent = nbm > 0 ? ` / -${nbm}` : '';

  // 1. Authoritative failed state (tallyResult === 'FAILED' or window expired without criteria met)
  if (state.status === 'failed') {
    const reason = bp < 3 ? `Quorum not met (+${bp} binding)` : `Not approved (+${bp} / -${bm} binding)`;
    if (remainingHours <= 0) {
      return {
        text: `\uD83D\uDDF3\uFE0F [VOTE: ${rc}] ${windowHours}h window closed \u2022 ${reason} \u2022 Vote failed`,
        color: 'error',
      };
    }
    return {
      text: `\uD83D\uDDF3\uFE0F [VOTE: ${rc}] +${bp}${dissentPart} binding (PMC) \u00B7 +${nbp}${nonBindingDissent} non-binding \u2022 ${remainingHours}h remaining (Vote failed / blocked)`,
      color: 'error',
    };
  }

  // 2. Authoritative closed state or elapsed voting window (<= 0h remaining)
  if (state.status === 'closed' || remainingHours <= 0) {
    if (state.status === 'closed' || (bp >= 3 && bp > bm)) {
      const dissentMsg = bm > 0 ? ` (${bm} dissenting)` : '';
      return {
        text: `\uD83D\uDDF3\uFE0F [VOTE: ${rc}] ${windowHours}h window closed \u2022 Criteria met (+${bp} binding${dissentMsg}) \u2022 Ready for [RESULT]`,
        color: 'info',
      };
    } else {
      const reason = bp < 3 ? `Quorum not met (+${bp} binding)` : `Not approved (+${bp} / -${bm} binding)`;
      return {
        text: `\uD83D\uDDF3\uFE0F [VOTE: ${rc}] ${windowHours}h window closed \u2022 ${reason} \u2022 Vote failed`,
        color: 'error',
      };
    }
  }

  // 3. Active voting window (> 0h remaining)
  if (bp >= 3 && bp > bm) {
    const warningNote = bm > 0 ? ` (DISSENT: -${bm})` : '';
    return {
      text: `\uD83D\uDDF3\uFE0F [VOTE: ${rc}] +${bp}${dissentPart} binding (PMC) \u00B7 +${nbp}${nonBindingDissent} non-binding \u2022 ${remainingHours}h remaining (CRITERIA MET${warningNote})`,
      color: bm > 0 ? 'warning' : 'success',
    };
  } else {
    const needed = Math.max(1, 3 - bp, bm - bp + 1);
    return {
      text: `\uD83D\uDDF3\uFE0F [VOTE: ${rc}] +${bp}${dissentPart} binding (PMC) \u00B7 +${nbp}${nonBindingDissent} non-binding \u2022 ${remainingHours}h remaining (Needs ${needed} more binding +1)`,
      color: bm > 0 ? 'error' : 'warning',
    };
  }
}

/**
 * Pure component renderer: renders the AbovePrompt band using resolved Box and Text components.
 */
export function renderVoteTallyBandComponent(Box: any, Text: any, state: VoteTallyState | null): any {
  if (!state || !Box || !Text) return null;
  const remainingHours = computeRemainingHours(state.openedAt, state.windowHours);
  const { text, color } = formatBandMessage(state, remainingHours);

  return Box({
    padding: 0,
    children: [
      Text({
        children: [text],
        color: color,
        bold: true,
      }),
    ],
  });
}

/**
 * Extracts and parses JSON from command execution output.
 */
export function extractJsonFromOutput(output: string): any {
  if (typeof output !== 'string') return null;
  const trimmed = output.trim();
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
    try {
      return JSON.parse(trimmed);
    } catch {
      // Continue to search for embedded json
    }
  }
  const firstBrace = output.indexOf('{');
  const lastBrace = output.lastIndexOf('}');
  if (firstBrace !== -1 && lastBrace > firstBrace) {
    try {
      return JSON.parse(output.substring(firstBrace, lastBrace + 1));
    } catch {
      return null;
    }
  }
  return null;
}

/**
 * Robustly extracts command output text from arbitrary engine tool execution result envelopes.
 */
export function extractRawOutput(res: any): string {
  if (typeof res === 'string') return res;
  if (!res || typeof res !== 'object') return '';
  const inner = res.result && typeof res.result === 'object' ? res.result : res;
  return (
    (typeof inner.output === 'string' ? inner.output : null) ??
    (typeof inner.stdout === 'string' ? inner.stdout : null) ??
    (typeof inner.content === 'string' ? inner.content : null) ??
    (typeof inner.text === 'string' ? inner.text : null) ??
    (typeof res.output === 'string' ? res.output : null) ??
    (typeof res.stdout === 'string' ? res.stdout : null) ??
    (typeof res.content === 'string' ? res.content : null) ??
    (typeof res.text === 'string' ? res.text : null) ??
    ''
  );
}

/**
 * Pure state processing function for vote-tally commands.
 * Returns the updated VoteTallyState if the command modified vote state, or undefined if no-op.
 */
export function processVoteCommand(
  command: string,
  rawOutput: string,
  current: VoteTallyState | null
): VoteTallyState | null | undefined {
  if (!command || typeof command !== 'string' || !command.includes('vote-tally')) {
    return undefined;
  }

  // 1. Intercept preflight: captures rcTag and openedAt
  if (command.includes('release-config preflight') && command.includes('vote-tally')) {
    const flagMatch = command.match(/(?:--rc-tag|--tag)[=\s]+([0-9A-Za-z_.\-]+-rc\d+)/i);
    const skillMatch = command.match(/(?:--skill[=\s]+vote-tally)\s+([0-9A-Za-z_.\-]+-rc\d+)/i);
    let rcTag: string | null = flagMatch?.[1] || skillMatch?.[1] || null;
    if (!rcTag) {
      const tokens = command.split(/\s+/);
      for (let i = 0; i < tokens.length; i++) {
        const token = tokens[i];
        if (!token) continue;
        const prev = tokens[i - 1] ?? '';
        if (/^--(?:project|dir|path|workdir)\b/i.test(prev)) continue;
        if (/^[0-9A-Za-z_.\-]+-rc\d+$/i.test(token)) {
          rcTag = token;
          break;
        }
      }
    }
    const openedMatch = command.match(/--vote-opened[=\s]+(?:'([^']+)'|"([^"]+)"|([^\s]+))/i);

    if (rcTag) {
      const parsedOpened = openedMatch ? (openedMatch[1] || openedMatch[2] || openedMatch[3] || '') : '';
      const openedAt: string = parsedOpened || current?.openedAt || new Date().toISOString();
      const nextState: VoteTallyState = current
        ? { ...current }
        : {
            rcTag,
            version: deriveVersionFromRcTag(rcTag),
            openedAt,
            windowHours: 72,
            binding: { plus: 0, minus: 0, zero: 0 },
            nonBinding: { plus: 0, minus: 0, zero: 0 },
            vetoes: [],
            status: 'voting' as VoteStatus,
            updatedAt: Date.now(),
          };
      nextState.rcTag = rcTag;
      nextState.version = deriveVersionFromRcTag(rcTag);
      if (parsedOpened) nextState.openedAt = parsedOpened;
      nextState.updatedAt = Date.now();
      return nextState;
    }
  }

  // 2. Intercept tally: captures binding/non-binding counts, dissenting votes, and verdict
  if (command.includes('release-management vote-tally tally')) {
    const json = extractJsonFromOutput(rawOutput);
    if (json && !json.error && (typeof json.binding_plus1 !== 'undefined' || Array.isArray(json.voters))) {
      const bindingPlus = Number(json.binding_plus1 ?? 0);
      const bindingMinus = Number(json.binding_minus1 ?? 0);
      const bindingZero = Number(json.binding_zero ?? 0);
      const nonBindingPlus = Number(json.nonbinding_plus1 ?? 0);
      const nonBindingMinus = Number(json.nonbinding_minus1 ?? 0);
      const nonBindingZero = Number(json.nonbinding_zero ?? 0);

      const dissentingVoters: string[] = [];
      if (Array.isArray(json.voters)) {
        for (const voter of json.voters) {
          if (voter && voter.binding === true && voter.value === '-1') {
            const id = voter.from || voter.login || '';
            if (id) dissentingVoters.push(sanitizeVoter(id));
          }
        }
      }

      const rcTag = current?.rcTag || 'RC';
      const openedAt = current?.openedAt || (json.opened_at || json.started_at || new Date().toISOString());
      const windowHours = current?.windowHours ?? 72;
      const remainingHours = computeRemainingHours(openedAt, windowHours);

      const tallyResult =
        json.result === 'PASSED' || json.result === 'FAILED' ? json.result : null;
      const halted = Boolean(json.halted_on_ambiguous);

      const status = evaluateVoteStatus(
        { plus: bindingPlus, minus: bindingMinus },
        remainingHours,
        tallyResult,
        halted
      );

      const newState: VoteTallyState = {
        rcTag,
        version: deriveVersionFromRcTag(rcTag),
        openedAt,
        windowHours,
        binding: { plus: bindingPlus, minus: bindingMinus, zero: bindingZero },
        nonBinding: { plus: nonBindingPlus, minus: nonBindingMinus, zero: nonBindingZero },
        vetoes: dissentingVoters,
        status,
        updatedAt: Date.now(),
      };
      return newState;
    }
  }

  return undefined;
}
