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

import { atom, read, update } from 'claude-code';

export const driftNotice = atom(
  { plugin: 'magpie-setup', key: 'driftNotice' },
  null as string | null
);

/**
 * Parses a simple subset of YAML used for apache-magpie.lock files.
 */
function parseYamlLike(content: string): Record<string, any> {
  const result: Record<string, any> = {};
  const lines = content.split('\n');

  let inList = false;
  let currentListKey = '';

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) {
      continue;
    }

    if (line.startsWith('- ')) {
      if (inList && currentListKey) {
        result[currentListKey].push(line.substring(2).trim());
      }
      continue;
    }

    const colonIndex = line.indexOf(':');
    if (colonIndex > 0) {
      const key = line.substring(0, colonIndex).trim();
      const value = line.substring(colonIndex + 1).trim();

      if (!value) {
        inList = true;
        currentListKey = key;
        result[key] = [];
      } else {
        inList = false;
        result[key] = value;
      }
    }
  }

  return result;
}

export interface LockfileData {
  method: string;
  url?: string;
  min_version?: string;
  ref?: string;
  commit?: string;
  plugins?: string[];
}

export function parseLockfile(content: string): LockfileData {
  const parsed = parseYamlLike(content);
  return {
    method: parsed.method,
    url: parsed.url,
    min_version: parsed.min_version,
    ref: parsed.ref,
    commit: parsed.commit,
    plugins: parsed.plugins,
  };
}

export interface LocalLockfileData {
  method: string;
  url?: string;
  source_ref?: string;
  fetched_commit?: string;
}

export function parseLocalLockfile(content: string): LocalLockfileData {
  const parsed = parseYamlLike(content);
  return {
    method: parsed.method,
    url: parsed.url,
    source_ref: parsed.source_ref,
    fetched_commit: parsed.fetched_commit,
  };
}

export interface DriftCheckResult {
  isAdopted: boolean;
  hasDrift: boolean;
  lockVersion?: string;
  currentVersion?: string;
  message?: string;
}

/**
 * Joins path segments normalizing slashes.
 */
export function joinPath(...segments: string[]): string {
  if (segments.length === 0) return '.';
  const parts: string[] = [];
  for (const seg of segments) {
    if (!seg) continue;
    const split = seg.split(/[/\\]+/);
    for (const p of split) {
      if (p === '..') {
        if (parts.length > 0 && parts[parts.length - 1] !== '..') {
          parts.pop();
        } else {
          parts.push('..');
        }
      } else if (p !== '.' && p !== '') {
        parts.push(p);
      } else if (p === '' && parts.length === 0) {
        parts.push(''); // leading slash
      }
    }
  }
  const result = parts.join('/');
  if (result === '') return '/';
  if (segments[0].startsWith('/') && !result.startsWith('/')) {
    return '/' + result;
  }
  return result || '.';
}

export interface Pep440Version {
  epoch: number;
  release: number[];
  pre?: { type: string; num: number };
  post?: number;
  dev?: number;
}

export function parsePep440(v: string): Pep440Version | null {
  let s = v.trim().replace(/^v/i, '');
  if (!s) return null;

  let epoch = 0;
  const epochMatch = s.match(/^(\d+)!/);
  if (epochMatch) {
    epoch = parseInt(epochMatch[1], 10);
    s = s.slice(epochMatch[0].length);
  }

  // Look for .devN
  let dev: number | undefined = undefined;
  const devMatch = s.match(/[.-]?dev(\d+)?$/i);
  if (devMatch) {
    dev = devMatch[1] !== undefined ? parseInt(devMatch[1], 10) : 0;
    s = s.slice(0, devMatch.index);
  }

  // Look for .postN
  let post: number | undefined = undefined;
  const postMatch = s.match(/[.-]?(post|r|rev)(\d+)?$/i);
  if (postMatch) {
    post = postMatch[2] !== undefined ? parseInt(postMatch[2], 10) : 0;
    s = s.slice(0, postMatch.index);
  }

  // Look for pre-release (a|b|rc|alpha|beta|preview|c)
  let pre: { type: string; num: number } | undefined = undefined;
  const preMatch = s.match(/[.-]?(a|alpha|b|beta|rc|c|preview)(\d+)?$/i);
  if (preMatch) {
    let type = preMatch[1].toLowerCase();
    if (type === 'alpha') type = 'a';
    if (type === 'beta') type = 'b';
    if (type === 'c' || type === 'preview') type = 'rc';
    const num = preMatch[2] !== undefined ? parseInt(preMatch[2], 10) : 0;
    pre = { type, num };
    s = s.slice(0, preMatch.index);
  }

  const parts = s.split('.');
  const release: number[] = [];
  for (const part of parts) {
    if (!part || !/^\d+$/.test(part)) return null;
    release.push(parseInt(part, 10));
  }
  if (release.length === 0) return null;

  return { epoch, release, pre, post, dev };
}

export function comparePep440(aStr: string, bStr: string): number {
  const a = parsePep440(aStr);
  const b = parsePep440(bStr);

  if (!a || !b) {
    return aStr.localeCompare(bStr);
  }

  if (a.epoch !== b.epoch) {
    return a.epoch - b.epoch;
  }

  const maxLen = Math.max(a.release.length, b.release.length);
  for (let i = 0; i < maxLen; i++) {
    const aVal = a.release[i] ?? 0;
    const bVal = b.release[i] ?? 0;
    if (aVal !== bVal) {
      return aVal - bVal;
    }
  }

  const getPhaseRank = (v: Pep440Version) => {
    if (v.dev !== undefined && !v.pre && !v.post) return -1; // e.g. 1.0.dev1
    if (v.pre) {
      if (v.pre.type === 'a') return 0;
      if (v.pre.type === 'b') return 1;
      if (v.pre.type === 'rc') return 2;
    }
    if (v.post !== undefined) return 4; // e.g. 1.0.post1
    return 3; // final release: 1.0
  };

  const aPhase = getPhaseRank(a);
  const bPhase = getPhaseRank(b);

  if (aPhase !== bPhase) {
    return aPhase - bPhase;
  }

  // Same phase comparisons:
  if (aPhase === -1) {
    return (a.dev ?? 0) - (b.dev ?? 0);
  }

  if (a.pre && b.pre) {
    if (a.pre.num !== b.pre.num) {
      return a.pre.num - b.pre.num;
    }
    const aDev = a.dev !== undefined ? a.dev : Infinity;
    const bDev = b.dev !== undefined ? b.dev : Infinity;
    if (aDev !== bDev) {
      return aDev - bDev;
    }
  }

  if (a.post !== undefined && b.post !== undefined) {
    if (a.post !== b.post) {
      return a.post - b.post;
    }
    const aDev = a.dev !== undefined ? a.dev : Infinity;
    const bDev = b.dev !== undefined ? b.dev : Infinity;
    if (aDev !== bDev) {
      return aDev - bDev;
    }
  }

  return 0;
}

/**
 * Resolves the currently executing plugin's version using provided fs adapters.
 */
export async function resolvePluginVersion(
  exists: (p: string) => Promise<boolean>,
  read: (p: string) => Promise<string>,
  pluginDir?: string
): Promise<string | undefined> {
  if (!pluginDir) return undefined;

  const candidatePaths = [
    joinPath(pluginDir, '.claude-plugin', 'plugin.json'),
    joinPath(pluginDir, 'package.json'),
    joinPath(pluginDir, '..', 'package.json'),
    joinPath(pluginDir, '..', '..', 'package.json')
  ];

  for (const p of candidatePaths) {
    try {
      if (await exists(p)) {
        const content = await read(p);
        const parsed = JSON.parse(content);
        if (parsed && typeof parsed.version === 'string' && parsed.version.trim()) {
          return parsed.version.trim();
        }
      }
    } catch {
      // Continue searching next candidate
    }
  }

  return undefined;
}

/**
 * Core deterministic drift check between workspace lockfile and installed plugin/snapshot.
 */
export async function checkSetupDrift(
  exists: (p: string) => Promise<boolean>,
  read: (p: string) => Promise<string>,
  workspaceDir: string,
  pluginDir?: string
): Promise<DriftCheckResult> {
  try {
    if (typeof exists !== 'function' || typeof read !== 'function') {
      return {
        isAdopted: false,
        hasDrift: false,
      };
    }

    const lockPath = joinPath(workspaceDir, '.apache-magpie.lock');

    if (!(await exists(lockPath))) {
      return {
        isAdopted: false,
        hasDrift: false,
      };
    }

    const rawContent = await read(lockPath);
    const content = rawContent.trim();
    if (!content) {
      return {
        isAdopted: true,
        hasDrift: true,
        message:
          'Apache Magpie: Empty `.apache-magpie.lock` detected. Run `/magpie-setup upgrade` to populate.',
      };
    }

    let lockData: LockfileData;
    try {
      lockData = parseLockfile(content);
    } catch {
      return {
        isAdopted: true,
        hasDrift: true,
        message:
          'Apache Magpie: Malformed `.apache-magpie.lock` detected. Run `/magpie-setup upgrade` to repair.',
      };
    }

    const method = lockData.method;

    // 1. Method: marketplace (Adoption Floor semantics)
    if (method === 'marketplace') {
      const minVersion = lockData.min_version;
      if (!minVersion) {
        return {
          isAdopted: true,
          hasDrift: true,
          message:
            'Apache Magpie: Malformed `.apache-magpie.lock` (missing min_version). Run `/magpie-setup upgrade` to repair.',
        };
      }

      const currentVersion = await resolvePluginVersion(exists, read, pluginDir);
      if (currentVersion) {
        // Floor semantics: drift only occurs when installed < min_version
        if (comparePep440(currentVersion, minVersion) < 0) {
          return {
            isAdopted: true,
            hasDrift: true,
            lockVersion: minVersion,
            currentVersion,
            message: `Apache Magpie: Installed plugin version (${currentVersion}) is below adoption floor (${minVersion}). Run \`/magpie-setup upgrade\` to reconcile.`,
          };
        }

        return {
          isAdopted: true,
          hasDrift: false,
          lockVersion: minVersion,
          currentVersion,
        };
      }

      return {
        isAdopted: true,
        hasDrift: false,
        lockVersion: minVersion,
      };
    }

    // 2. Snapshot methods (git-tag, git-branch, svn-zip)
    if (method === 'git-tag' || method === 'git-branch' || method === 'svn-zip') {
      const localLockPath = joinPath(workspaceDir, '.apache-magpie.local.lock');
      const committedPin = lockData.ref || lockData.commit;

      if (!(await exists(localLockPath))) {
        return {
          isAdopted: true,
          hasDrift: true,
          lockVersion: committedPin,
          message:
            'Apache Magpie: Local snapshot lockfile missing (`.apache-magpie.local.lock`). Run `/magpie-setup upgrade` to fetch snapshot.',
        };
      }

      const rawLocalContent = await read(localLockPath);
      const localContent = rawLocalContent.trim();
      if (!localContent) {
        return {
          isAdopted: true,
          hasDrift: true,
          lockVersion: committedPin,
          message:
            'Apache Magpie: Empty `.apache-magpie.local.lock` detected. Run `/magpie-setup upgrade` to refresh.',
        };
      }

      let localData: LocalLockfileData;
      try {
        localData = parseLocalLockfile(localContent);
      } catch {
        return {
          isAdopted: true,
          hasDrift: true,
          lockVersion: committedPin,
          message:
            'Apache Magpie: Malformed `.apache-magpie.local.lock` detected. Run `/magpie-setup upgrade` to repair.',
        };
      }

      if (method === 'git-tag' || method === 'git-branch') {
        const refMismatch = Boolean(lockData.ref && localData.source_ref && lockData.ref !== localData.source_ref);
        const commitMismatch = Boolean(
          lockData.commit && localData.fetched_commit && lockData.commit !== localData.fetched_commit
        );

        if (refMismatch || commitMismatch) {
          const localPin = localData.source_ref || localData.fetched_commit;
          return {
            isAdopted: true,
            hasDrift: true,
            lockVersion: committedPin,
            message: `Apache Magpie: Snapshot drift detected (${localPin} -> ${committedPin}). Run \`/magpie-setup upgrade\` to reconcile snapshot and overrides.`,
          };
        }

        return {
          isAdopted: true,
          hasDrift: false,
          lockVersion: committedPin,
        };
      }

      if (method === 'svn-zip') {
        if (lockData.ref && localData.source_ref && lockData.ref !== localData.source_ref) {
          return {
            isAdopted: true,
            hasDrift: true,
            lockVersion: lockData.ref,
            message: `Apache Magpie: Snapshot drift detected (${localData.source_ref} -> ${lockData.ref}). Run \`/magpie-setup upgrade\` to reconcile snapshot and overrides.`,
          };
        }

        return {
          isAdopted: true,
          hasDrift: false,
          lockVersion: lockData.ref,
        };
      }
    }

    return {
      isAdopted: true,
      hasDrift: true,
      message:
        'Apache Magpie: Malformed `.apache-magpie.lock` (unknown or missing method). Run `/magpie-setup upgrade` to repair.',
    };
  } catch {
    return {
      isAdopted: false,
      hasDrift: false,
    };
  }
}

/**
 * Event hook registration entry point for Claude Code.
 */
export function register(on: any): void {
  // 1. Hook session.start to check for lockfile drift
  on('session.start', async ($: any, e: any, next: any) => {
    try {
      const workspaceDir = await $.session.root();
      const pluginDir = $.plugin.root;

      const result = await checkSetupDrift(
        async (p) => await $.fs.exists(p),
        async (p) => await $.fs.read(p),
        workspaceDir,
        pluginDir
      );

      if (result.hasDrift && result.message) {
        await update($, driftNotice, () => result.message);
        try {
          $.ui.invalidate('ui.render');
        } catch {
          // fallback
        }
      } else {
        await update($, driftNotice, () => null);
      }
    } catch {
      // Safe no-op on exception
    }
    if (typeof next === 'function') {
      return next(e);
    }
  });

  // 2. Hook ui.render to display AbovePrompt drift banner if detected
  on('ui.render', { component: 'AbovePrompt' }, async ($: any, e: any, next: any) => {
    const notice = await read($, driftNotice);
    if (!notice) {
      if (typeof next === 'function') return next(e);
      return;
    }

    try {
      const { Box, Text } = $.ui.resolve(e);
      if (Box && Text) {
        return Box({
          padding: 0,
          children: [
            Text({
              children: [`\u26A0 ${notice}`],
              color: 'warning',
              bold: true,
            }),
          ],
        });
      }
    } catch {
      // Fallback cleanly
    }

    if (typeof next === 'function') {
      return next(e);
    }
  });
}

export default register;
