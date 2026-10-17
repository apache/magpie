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

/**
 * Single forbidden-term regexes for public surfaces, aligned with
 * plugins/magpie-security/skills/issue-fix/implementation-plan.md:31-43.
 *
 * Public surface commit messages, PR descriptions, and PR comments must not
 * contain any of: CVE references, vulnerability, security fix/patch/advisory,
 * security@, or specific vulnerability class names.
 */
export const FORBIDDEN_TERM_RULES: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  { name: 'CVE reference', pattern: /\bCVE(?:-\d{4}-\d+)?\b/i },
  { name: 'vulnerability', pattern: /\bvulnerabilit(?:y|ies)\b/i },
  { name: 'security fix', pattern: /\bsecurity[\s-]+(?:fix|patch|advisory)\b/i },
  { name: 'security mailing list', pattern: /\bsecurity@/i },
  { name: 'SSRF', pattern: /\bSSRF\b/i },
  { name: 'XSS', pattern: /\bXSS\b/i },
  { name: 'CSRF', pattern: /\bCSRF\b/i },
  { name: 'SQL injection', pattern: /\bSQL[\s-]+injection\b/i },
  { name: 'path traversal', pattern: /\bpath[\s-]+traversal\b/i },
  { name: 'remote code execution', pattern: /\b(?:remote[\s-]+code[\s-]+execution|RCE)\b/i },
  { name: 'privilege escalation', pattern: /\bprivilege[\s-]+escalation\b/i },
  { name: 'auth bypass', pattern: /\bauth(?:orization|entication)?[\s-]+bypass\b/i },
];

/**
 * Finds all unique forbidden embargo terms that appear in the candidate text.
 */
export function findForbiddenTerms(text: string): string[] {
  if (!text || typeof text !== 'string') {
    return [];
  }

  const matched: string[] = [];
  for (const rule of FORBIDDEN_TERM_RULES) {
    if (rule.pattern.test(text)) {
      matched.push(rule.name);
    }
  }

  return matched;
}

export type FileReader = (filePath: string) => Promise<string | null | undefined>;

export interface ProjectRepos {
  trackerRepo?: string;
  upstreamRepo?: string;
  isTrackerCheckout?: boolean;
}

/**
 * Cleans and validates a repository slug (owner/repo).
 * Filters out placeholders, TODOs, comments, and non-slug text like "not used".
 */
function cleanRepoSlug(raw: string | undefined): string | undefined {
  if (!raw || typeof raw !== 'string') {
    return undefined;
  }
  const trimmed = raw.trim().replace(/^[`'"]+|[`'"]+$/g, '').trim().toLowerCase();
  if (
    trimmed.startsWith('todo') ||
    trimmed.startsWith('<') ||
    trimmed.startsWith('not used') ||
    trimmed.startsWith('not_used') ||
    trimmed === 'none' ||
    trimmed === 'n/a' ||
    trimmed === '-' ||
    !trimmed.includes('/')
  ) {
    return undefined;
  }
  const match = trimmed.match(/^([a-z0-9_.-]+\/[a-z0-9_.-]+)/);
  return match ? match[1] : undefined;
}

/**
 * Parses project manifest content (Markdown table or YAML syntax) to extract
 * tracker_repo and upstream_repo slugs without assuming naming conventions.
 */
export function parseProjectManifest(content: string): ProjectRepos {
  const result: ProjectRepos = {};
  if (!content || typeof content !== 'string') {
    return result;
  }

  // Markdown table row: | `?tracker_repo`? | `?<slug>`? |
  const trackerMatch =
    content.match(/\|\s*`?tracker_repo`?\s*\|\s*`?([^`|\r\n]+)`?/i) ??
    content.match(/^\s*tracker_repo:\s*`?([^`\r\n#]+)`?/im);
  const trackerSlug = cleanRepoSlug(trackerMatch?.[1]);
  if (trackerSlug) {
    result.trackerRepo = trackerSlug;
  }

  // Markdown table row: | `?upstream_repo`? | `?<slug>`? |
  const upstreamMatch =
    content.match(/\|\s*`?upstream_repo`?\s*\|\s*`?([^`|\r\n]+)`?/i) ??
    content.match(/^\s*upstream_repo:\s*`?([^`\r\n#]+)`?/im);
  const upstreamSlug = cleanRepoSlug(upstreamMatch?.[1]);
  if (upstreamSlug) {
    result.upstreamRepo = upstreamSlug;
  }

  return result;
}

/**
 * Resolves repository identity from <project-config>/project.md in precedence order:
 * 1. .apache-magpie-local/project.md
 * 2. .git/apache-magpie/project.md
 * 3. .apache-magpie-overrides/project.md
 */
export async function resolveProjectConfig(readFile?: FileReader): Promise<ProjectRepos> {
  if (!readFile) {
    return {};
  }

  const candidatePaths = [
    '.apache-magpie-local/project.md',
    '.git/apache-magpie/project.md',
    '.apache-magpie-overrides/project.md',
  ];

  for (const path of candidatePaths) {
    try {
      const content = await readFile(path);
      if (content && typeof content === 'string') {
        const repos = parseProjectManifest(content);
        if (repos.trackerRepo || repos.upstreamRepo) {
          repos.isTrackerCheckout = true;
          return repos;
        }
      }
    } catch {
      // Continue to next candidate
    }
  }

  return {};
}

/**
 * Splits a composite shell command line into individual subcommands on
 * separators (;, &&, ||, |, \n, \r), respecting single and double quotes.
 */
export function splitShellCommands(commandLine: string): string[] {
  const commands: string[] = [];
  if (!commandLine || typeof commandLine !== 'string') {
    return commands;
  }

  let current = '';
  let inSingle = false;
  let inDouble = false;
  let isEscaped = false;

  for (let i = 0; i < commandLine.length; i++) {
    const char = commandLine[i];
    const next = commandLine[i + 1];

    if (isEscaped) {
      current += char;
      isEscaped = false;
      continue;
    }

    if (char === '\\' && !inSingle) {
      isEscaped = true;
      current += char;
      continue;
    }

    if (char === "'" && !inDouble) {
      inSingle = !inSingle;
      current += char;
      continue;
    }

    if (char === '"' && !inSingle) {
      inDouble = !inDouble;
      current += char;
      continue;
    }

    if (!inSingle && !inDouble) {
      if (char === '\n' || char === '\r' || char === ';') {
        if (current.trim()) {
          commands.push(current.trim());
        }
        current = '';
        continue;
      }
      if (char === '&' && next === '&') {
        if (current.trim()) {
          commands.push(current.trim());
        }
        current = '';
        i++; // skip second &
        continue;
      }
      if (char === '|' && next === '|') {
        if (current.trim()) {
          commands.push(current.trim());
        }
        current = '';
        i++; // skip second |
        continue;
      }
      if (char === '|') {
        if (current.trim()) {
          commands.push(current.trim());
        }
        current = '';
        continue;
      }
    }

    current += char;
  }

  if (current.trim()) {
    commands.push(current.trim());
  }

  return commands;
}

/**
 * Resolves a file path relative to an optional git working directory (-C <dir>)
 * without requiring node:path.
 */
export function resolvePath(dir: string | undefined, filePath: string): string {
  if (!filePath) return '';
  const trimmed = filePath.trim().replace(/^['"]|['"]$/g, '');
  if (!dir || trimmed.startsWith('/') || trimmed.startsWith('\\') || /^[a-zA-Z]:/.test(trimmed)) {
    return trimmed;
  }
  const cleanDir = dir.trim().replace(/[\\/]+$/, '');
  const cleanPath = trimmed.replace(/^\.[\\/]+/, '').replace(/^[\\/]+/, '');
  return `${cleanDir}/${cleanPath}`;
}

export interface ParsedSubcommand {
  raw: string;
  isPublicSurfaceCommand: boolean;
  commandType: string;
  targetRepo?: string;
  gitCwd?: string;
  extractedTexts: string[];
  referencedFiles: string[];
  hasDynamicInput: boolean;
}

/**
 * Parses a single subcommand, identifying git/gh invocations and extracting
 * messages (-m, -t, -b, -f body=...), file references (-F, --body-file),
 * target repositories (-R, --repo), git working directory (-C), and attached short flags.
 */
export function parseSubcommand(subcommand: string): ParsedSubcommand {
  const result: ParsedSubcommand = {
    raw: subcommand,
    isPublicSurfaceCommand: false,
    commandType: '',
    extractedTexts: [],
    referencedFiles: [],
    hasDynamicInput: false,
  };

  const trimmed = subcommand.trim();
  if (!trimmed) {
    return result;
  }

  // Extract git working directory (-C <dir> or -C=<dir>)
  const cwdMatch = trimmed.match(/(?:^|\s)git\s+.*?-C(?:=|\s+)(?:"([^"]+)"|'([^']+)'|([^\s;&|]+))/i);
  if (cwdMatch) {
    result.gitCwd = cwdMatch[1] ?? cwdMatch[2] ?? cwdMatch[3];
  }

  // Extract explicit target repository (-R <repo> or --repo <repo> or --repo=<repo>)
  const repoMatch = trimmed.match(/(?:(?:^|\s)-(?!-)[a-zA-Z]*R|--repo)(?:=|\s+)(?:"([^"]+)"|'([^']+)'|([^\s;&|]+))/i);
  if (repoMatch) {
    result.targetRepo = (repoMatch[1] ?? repoMatch[2] ?? repoMatch[3] ?? '').toLowerCase();
  }

  // Detect dynamic inputs: heredocs (<<), process substitution (<()), command substitution ($() or ``), variables ($VAR)
  if (/<<|`|\$\(|\$[a-zA-Z_]/.test(trimmed)) {
    result.hasDynamicInput = true;
  }

  // 1. git commit (including git commit --amend, -m, -am, -sm, -sam, -F)
  if (/(?:^|\s)git\s+(?:-[^\s]+(?:\s+[^\s]+)?\s+)*commit(?:\s|$)/i.test(trimmed)) {
    result.isPublicSurfaceCommand = true;
    result.commandType = 'git commit';

    // Flag git commit --amend without explicit new message as indeterminate reuse
    if (/(?:^|\s)--amend(?:\s|$)/i.test(trimmed) && !/(?:(?:^|\s)-(?!-)[a-zA-Z]*[mF]|--message|--file)/.test(trimmed)) {
      result.hasDynamicInput = true;
    }

    // Extract -m, -am, -sm, -sam, or --message="..." (attached or separated)
    const mMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*m|--message)(?:=|\s*|)(?:\$?"([^"]*)"|\$?'([^']*)'|([^\s;&|]+))/g);
    for (const m of mMatches) {
      const text = m[1] ?? m[2] ?? m[3];
      if (text) {
        result.extractedTexts.push(text);
      }
    }

    // Extract -F or --file="..." (attached or separated)
    const fMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*F|--file)(?:=|\s*|)(?:"([^"]+)"|'([^']+)'|([^\s;&|]+))/g);
    for (const f of fMatches) {
      const file = f[1] ?? f[2] ?? f[3];
      if (file) {
        if (file === '-') {
          result.hasDynamicInput = true;
        } else {
          result.referencedFiles.push(file);
        }
      }
    }

    return result;
  }

  // 2. git tag (including git tag -a ... -m "...", git tag -m "...")
  if (/(?:^|\s)git\s+(?:-[^\s]+(?:\s+[^\s]+)?\s+)*tag(?:\s|$)/i.test(trimmed)) {
    // Only tag commands that attach an annotated message (-m or -F) are public-surface publishing commands
    const hasMsgFlag = /(?:(?:^|\s)-(?!-)[a-zA-Z]*m|--message|(?:^|\s)-(?!-)[a-zA-Z]*F|--file)/.test(trimmed);
    if (hasMsgFlag) {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'git tag';

      const mMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*m|--message)(?:=|\s*|)(?:\$?"([^"]*)"|\$?'([^']*)'|([^\s;&|]+))/g);
      for (const m of mMatches) {
        const text = m[1] ?? m[2] ?? m[3];
        if (text) {
          result.extractedTexts.push(text);
        }
      }

      const fMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*F|--file)(?:=|\s*|)(?:"([^"]+)"|'([^']+)'|([^\s;&|]+))/g);
      for (const f of fMatches) {
        const file = f[1] ?? f[2] ?? f[3];
        if (file) {
          if (file === '-') {
            result.hasDynamicInput = true;
          } else {
            result.referencedFiles.push(file);
          }
        }
      }

      return result;
    }
  }

  // 3. gh pr create
  if (/(?:^|\s)gh\s+pr\s+create(?:\s|$)/i.test(trimmed)) {
    result.isPublicSurfaceCommand = true;
    result.commandType = 'gh pr create';

    // Flag --fill / --fill-first which auto-populates title and body from commits
    if (/(?:^|\s)--fill(?:-first)?(?:\s|$)/i.test(trimmed)) {
      result.hasDynamicInput = true;
    }

    const titleMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*t|--title)(?:=|\s*|)(?:"([^"]*)"|'([^']*)'|([^\s;&|]+))/g);
    for (const t of titleMatches) {
      const text = t[1] ?? t[2] ?? t[3];
      if (text) {
        result.extractedTexts.push(text);
      }
    }

    const bodyMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*b|--body)(?:=|\s*|)(?:\$?"([^"]*)"|\$?'([^']*)'|([^\s;&|]+))/g);
    for (const b of bodyMatches) {
      const text = b[1] ?? b[2] ?? b[3];
      if (text) {
        result.extractedTexts.push(text);
      }
    }

    const fileMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*F|--body-file)(?:=|\s*|)(?:"([^"]+)"|'([^']+)'|([^\s;&|]+))/g);
    for (const f of fileMatches) {
      const file = f[1] ?? f[2] ?? f[3];
      if (file) {
        if (file === '-') {
          result.hasDynamicInput = true;
        } else {
          result.referencedFiles.push(file);
        }
      }
    }

    return result;
  }

  // 4. gh pr edit
  if (/(?:^|\s)gh\s+pr\s+edit(?:\s|$)/i.test(trimmed)) {
    result.isPublicSurfaceCommand = true;
    result.commandType = 'gh pr edit';

    const titleMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*t|--title)(?:=|\s*|)(?:"([^"]*)"|'([^']*)'|([^\s;&|]+))/g);
    for (const t of titleMatches) {
      const text = t[1] ?? t[2] ?? t[3];
      if (text) {
        result.extractedTexts.push(text);
      }
    }

    const bodyMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*b|--body)(?:=|\s*|)(?:\$?"([^"]*)"|\$?'([^']*)'|([^\s;&|]+))/g);
    for (const b of bodyMatches) {
      const text = b[1] ?? b[2] ?? b[3];
      if (text) {
        result.extractedTexts.push(text);
      }
    }

    const fileMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*F|--body-file)(?:=|\s*|)(?:"([^"]+)"|'([^']+)'|([^\s;&|]+))/g);
    for (const f of fileMatches) {
      const file = f[1] ?? f[2] ?? f[3];
      if (file) {
        if (file === '-') {
          result.hasDynamicInput = true;
        } else {
          result.referencedFiles.push(file);
        }
      }
    }

    return result;
  }

  // 5. gh pr review
  if (/(?:^|\s)gh\s+pr\s+review(?:\s|$)/i.test(trimmed)) {
    result.isPublicSurfaceCommand = true;
    result.commandType = 'gh pr review';

    const bodyMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*b|--body)(?:=|\s*|)(?:\$?"([^"]*)"|\$?'([^']*)'|([^\s;&|]+))/g);
    for (const b of bodyMatches) {
      const text = b[1] ?? b[2] ?? b[3];
      if (text) {
        result.extractedTexts.push(text);
      }
    }

    const fileMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*F)(?:=|\s*|)(?:"([^"]+)"|'([^']+)'|([^\s;&|]+))/g);
    for (const f of fileMatches) {
      const file = f[1] ?? f[2] ?? f[3];
      if (file) {
        if (file === '-') {
          result.hasDynamicInput = true;
        } else {
          result.referencedFiles.push(file);
        }
      }
    }

    return result;
  }

  // 6. gh pr comment / gh issue comment
  if (/(?:^|\s)gh\s+(?:pr|issue)\s+comment(?:\s|$)/i.test(trimmed)) {
    result.isPublicSurfaceCommand = true;
    result.commandType = 'gh pr comment';

    const bodyMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*b|--body)(?:=|\s*|)(?:\$?"([^"]*)"|\$?'([^']*)'|([^\s;&|]+))/g);
    for (const b of bodyMatches) {
      const text = b[1] ?? b[2] ?? b[3];
      if (text) {
        result.extractedTexts.push(text);
      }
    }

    const fileMatches = trimmed.matchAll(/(?:(?:^|\s)-(?!-)[a-zA-Z]*F|--body-file)(?:=|\s*|)(?:"([^"]+)"|'([^']+)'|([^\s;&|]+))/g);
    for (const f of fileMatches) {
      const file = f[1] ?? f[2] ?? f[3];
      if (file) {
        if (file === '-') {
          result.hasDynamicInput = true;
        } else {
          result.referencedFiles.push(file);
        }
      }
    }

    return result;
  }

  // 7. gh api (e.g. gh api repos/<owner>/<repo>/... -f body="..." or -F body=...)
  if (/(?:^|\s)gh\s+api(?:\s|$)/i.test(trimmed)) {
    // Check if targeting a repo endpoint: repos/:owner/:repo
    const apiRepoMatch = trimmed.match(/(?:^|\s)gh\s+api\s+(?:repos\/)?([a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+)/i);
    if (apiRepoMatch && apiRepoMatch[1]) {
      result.targetRepo = apiRepoMatch[1].toLowerCase();
    }

    // Extract fields: -f body=..., -f "body=...", -F body=..., --field body=..., --raw-field body=...
    const fieldMatches = trimmed.matchAll(
      /(?:-f|-F|--field|--raw-field)(?:=|\s+)(?:"(?:body|title)=([^"]*)"|'(?:body|title)=([^']*)'|(?:body|title)=(?:"([^"]*)"|'([^']*)'|([^\s;&|]+)))/gi
    );
    for (const f of fieldMatches) {
      const val = f[1] ?? f[2] ?? f[3] ?? f[4] ?? f[5];
      if (val) {
        result.extractedTexts.push(val);
      }
    }

    if (result.extractedTexts.length > 0) {
      result.isPublicSurfaceCommand = true;
      result.commandType = 'gh api';
      return result;
    }
  }

  return result;
}

export interface EvaluationOptions {
  readFile?: FileReader;
  env?: Record<string, string | undefined>;
  projectConfig?: ProjectRepos;
}

/**
 * Generates an actionable, maintainer-aligned blocking explanation.
 * Does NOT teach the agent how to bypass; instructs asking the maintainer.
 */
function generateBlockingReason(commandType: string, terms: string[]): string {
  const termList = terms.map((t) => `\`${t}\``).join(', ');
  return [
    `⛔ Apache Magpie Security Guard: Blocked public-surface command (${commandType}).`,
    `Found forbidden security disclosure term(s): ${termList}.`,
    '',
    'Confidentiality Rule (AGENTS.md & docs/security/fixing-security-issues.md):',
    'Public commits, tags, PR descriptions, and comments on upstream repositories must describe the change in neutral functional terms without mentioning CVE IDs or vulnerability classes before the coordinated disclosure advisory has shipped.',
    'If this is legitimate post-coordinated-disclosure maintenance, consult an Apache Magpie security-team maintainer to review and set the environment bypass.',
  ].join('\n');
}

/**
 * Evaluates whether a public-surface command violates embargo terms.
 * Evaluates per subcommand, respects project.md config for tracker/upstream resolution,
 * fails closed on unreadable files, and honours only human-set environment escape hatches.
 */
export async function evaluatePublicSurfaceCommand(
  commandLine: string,
  options?: EvaluationOptions
): Promise<{ blocked: boolean; matchedTerms: string[]; reason?: string }> {
  // Deterministic escape hatch: honour ONLY environment variable set by human before session
  if (options?.env?.MAGPIE_ALLOW_EMBARGO_TERMS === '1') {
    return { blocked: false, matchedTerms: [] };
  }

  if (!commandLine || typeof commandLine !== 'string') {
    return { blocked: false, matchedTerms: [] };
  }

  // Resolve project configuration (tracker_repo, upstream_repo)
  const projectConfig = options?.projectConfig ?? (await resolveProjectConfig(options?.readFile));
  const trackerRepo = projectConfig.trackerRepo?.toLowerCase();
  const upstreamRepo = projectConfig.upstreamRepo?.toLowerCase();

  // If no upstream_repo or tracker_repo is configured, or if running in the apache/magpie framework repo,
  // this workspace is not bound to a private embargoed fix workflow. Let all pass.
  if (!upstreamRepo || !trackerRepo || trackerRepo === upstreamRepo || upstreamRepo === 'apache/magpie') {
    return { blocked: false, matchedTerms: [] };
  }

  // Split command line into individual subcommands
  const subcommands = splitShellCommands(commandLine);

  for (const rawSub of subcommands) {
    const parsed = parseSubcommand(rawSub);
    if (!parsed.isPublicSurfaceCommand) {
      continue;
    }

    // 1. Exemption: Subcommand explicitly targets the private security tracker
    if (parsed.targetRepo && trackerRepo && parsed.targetRepo === trackerRepo) {
      continue;
    }

    // 2. Repository scoping: If subcommand targets an explicit repository that is NOT upstream_repo, let it pass
    if (parsed.targetRepo && parsed.targetRepo !== upstreamRepo) {
      continue;
    }

    // 3. For git commands without explicit repo, check repository context
    if (!parsed.targetRepo) {
      const gitCwd = parsed.gitCwd?.toLowerCase();
      if (gitCwd) {
        // Exemption if inside tracker repository
        const trackerSlug = trackerRepo.split('/')[1];
        if (trackerSlug && gitCwd.includes(trackerSlug)) {
          continue;
        }
        // Check if git -C points to upstream repository
        const upstreamSlug = upstreamRepo.split('/')[1] ?? upstreamRepo;
        const isUpstream = gitCwd.includes(upstreamRepo) || gitCwd.includes(upstreamSlug) || gitCwd.includes('upstream');
        if (!isUpstream) {
          // Working in an unrelated repository (e.g. apache/magpie)
          continue;
        }
      } else if (projectConfig.isTrackerCheckout) {
        // Bare git command in the tracker repository itself without upstream context
        continue;
      } else if (options?.readFile) {
        try {
          const gitConfig = await options.readFile('.git/config');
          if (gitConfig && typeof gitConfig === 'string') {
            const gitConfigLower = gitConfig.toLowerCase();
            if (trackerRepo && gitConfigLower.includes(trackerRepo)) {
              continue;
            }
            const upstreamSlug = upstreamRepo.split('/')[1] ?? upstreamRepo;
            const isUpstream = gitConfigLower.includes(upstreamRepo) || gitConfigLower.includes(upstreamSlug);
            if (!isUpstream) {
              continue;
            }
          }
        } catch {
          // Fall through to inspection if .git/config is absent
        }
      }
    }

    // If dynamic input (stdin -, heredoc, command substitution, variable, pipe, gh pr create --fill, git commit --amend without message) is present
    if (parsed.hasDynamicInput) {
      // First check if the commandLine itself explicitly carries forbidden terms (e.g. echo "Fix CVE-..." | git commit -F -)
      const dynamicTerms = findForbiddenTerms(commandLine);
      if (dynamicTerms.length > 0) {
        const uniqueTerms = Array.from(new Set(dynamicTerms));
        return {
          blocked: true,
          matchedTerms: uniqueTerms,
          reason: generateBlockingReason(parsed.commandType, uniqueTerms),
        };
      }
      // If the published content cannot be determined statically, fail closed
      return {
        blocked: true,
        matchedTerms: ['dynamic input'],
        reason: `⛔ Apache Magpie Security Guard: Blocked public-surface command (${parsed.commandType}) with indeterminate dynamic input. Content constructed from variables ($VAR), command substitution ($(..)), stdin (-), or automated reuse (--amend/--fill) cannot be verified deterministically before publication. Provide the text explicitly or via an inspectable file.`,
      };
    }

    // Collect all text candidates for this subcommand
    const candidateTexts: string[] = [...parsed.extractedTexts];

    // Read and inspect any referenced message files (-F / --body-file)
    for (const file of parsed.referencedFiles) {
      const resolvedPath = resolvePath(parsed.gitCwd, file);
      if (!options?.readFile) {
        return {
          blocked: true,
          matchedTerms: [],
          reason: `⛔ Apache Magpie Security Guard: Blocked public-surface command (${parsed.commandType}). Referenced message file cannot be read: \`${resolvedPath}\`.`,
        };
      }

      try {
        const content = await options.readFile(resolvedPath);
        if (content === null || content === undefined || typeof content !== 'string') {
          return {
            blocked: true,
            matchedTerms: [],
            reason: `⛔ Apache Magpie Security Guard: Blocked public-surface command (${parsed.commandType}). Referenced message file could not be read: \`${resolvedPath}\`.`,
          };
        }
        candidateTexts.push(content);
      } catch {
        return {
          blocked: true,
          matchedTerms: [],
          reason: `⛔ Apache Magpie Security Guard: Blocked public-surface command (${parsed.commandType}). Referenced message file could not be read: \`${resolvedPath}\`.`,
        };
      }
    }

    // Check for forbidden terms in candidate texts
    const combinedText = candidateTexts.join('\n');
    const matched = findForbiddenTerms(combinedText);

    if (matched.length > 0) {
      const uniqueTerms = Array.from(new Set(matched));
      return {
        blocked: true,
        matchedTerms: uniqueTerms,
        reason: generateBlockingReason(parsed.commandType, uniqueTerms),
      };
    }
  }

  return { blocked: false, matchedTerms: [] };
}

/**
 * Event hook registration entry point for Claude Code.
 */
export function register(on: any): void {
  on('tool.call', async ($: any, e: any, next: any) => {
    const toolName = (e?.tool || '').toLowerCase();
    const command = e?.input?.command || e?.params?.command;

    if (toolName === 'bash' && typeof command === 'string') {
      const evaluation = await evaluatePublicSurfaceCommand(command, {
        readFile: async (filePath: string) => {
          try {
            return await $.fs.read(filePath);
          } catch {
            return null;
          }
        },
      });

      if (evaluation.blocked && evaluation.reason) {
        return {
          error: evaluation.reason,
        };
      }
    }

    if (typeof next === 'function') {
      return next(e);
    }
  });
}

export default register;
