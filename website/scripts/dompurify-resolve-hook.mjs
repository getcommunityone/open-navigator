import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { fileURLToPath } from 'node:url';

const shim = pathToFileURL(
  join(dirname(fileURLToPath(import.meta.url)), 'mermaid-dom-purify.mjs'),
).href;

export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'dompurify') {
    const parent = context.parentURL ?? '';
    if (!parent.includes('mermaid-dom-purify.mjs')) {
      return { url: shim, shortCircuit: true };
    }
  }
  return nextResolve(specifier, context);
}
