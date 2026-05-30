#!/usr/bin/env node
/**
 * Validate Mermaid diagram text; print parse errors with line hints.
 *
 *   cd website && npm install
 *   npm run check-mermaid -- path/to/diagram.mmd
 *   npm run check-mermaid -- --json path/to/diagram.mmd
 */
import { readFileSync } from 'node:fs';
import mermaid from 'mermaid';

mermaid.initialize({ startOnLoad: false, securityLevel: 'loose', logLevel: 'error' });

const jsonOut = process.argv.includes('--json');
const inputs = process.argv.slice(2).filter((a) => a !== '--json');
const sources =
  inputs.length === 0
    ? [readFileSync(0, 'utf8')]
    : inputs.map((p) => readFileSync(p, 'utf8'));

let failed = 0;
for (let i = 0; i < sources.length; i++) {
  const src = sources[i].trim();
  if (!src) continue;
  const label = inputs[i] ?? '(stdin)';
  try {
    await mermaid.parse(src);
    if (jsonOut) {
      console.log(JSON.stringify({ index: i, label, ok: true }));
    } else {
      console.log(`OK  ${label}`);
    }
  } catch (e) {
    failed += 1;
    const line = e.hash?.loc?.first_line ?? null;
    const column = e.hash?.loc?.first_column ?? null;
    const row = {
      index: i,
      label,
      ok: false,
      message: e.message || String(e),
      line,
      column,
      snippet: src.split('\n').slice(0, 12).join('\n'),
    };
    if (jsonOut) {
      console.log(JSON.stringify(row));
    } else {
      const loc = line != null ? ` (line ${line})` : '';
      console.error(`FAIL${loc}  ${label}`);
      console.error(row.message);
      console.error('---');
      console.error(src.slice(0, 500));
      console.error('---');
    }
  }
}
process.exit(failed > 0 ? 1 : 0);
