/** Node shim so mermaid's `import DOMPurify from "dompurify"` gets `.sanitize`. */
import { JSDOM } from 'jsdom';
import createDOMPurify from 'dompurify';

const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>');
const window = dom.window;
globalThis.window = window;
globalThis.document = window.document;

const purify = createDOMPurify(window);
export default purify;
export const sanitize = purify.sanitize.bind(purify);
