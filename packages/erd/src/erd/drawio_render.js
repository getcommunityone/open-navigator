// renders each given .drawio to a .png beside it with the draw.io viewer in headless Chromium, and embeds the
// diagram xml in the png (a tEXt "mxfile" chunk, as draw.io's editable-png export does), so the png shows anywhere
// and draw.io can still open it. Ported from healthtransformationlab/health-transformation-lab-nlp
// (diagrams/_build/drawio_render.js, itself from jcbowyer/DE_Assessment).
// run: node drawio_render.js <files...>   (needs Node 20.15+ for zlib.crc32, and playwright; VIEWER overrides
// the viewer script, e.g. a local draw.io webapp: VIEWER=http://localhost:8765/js/viewer-static.min.js, see render.md)
const fs = require('fs'), path = require('path'), zlib = require('zlib');
const { chromium } = require('playwright');
const VIEWER = process.env.VIEWER || 'https://viewer.diagrams.net/js/viewer-static.min.js';

function embed(png, xml) {
  const data = Buffer.concat([Buffer.from('mxfile\0', 'latin1'), Buffer.from(encodeURIComponent(xml), 'latin1')]);
  const type = Buffer.from('tEXt', 'latin1');
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(zlib.crc32(Buffer.concat([type, data])) >>> 0);
  const iend = png.length - 12;                          // IEND is the last 12 bytes
  return Buffer.concat([png.subarray(0, iend), len, type, data, crc, png.subarray(iend)]);
}

(async () => {
  const files = process.argv.slice(2).map(f => path.resolve(f));
  if (!files.length) { console.error('usage: node drawio_render.js <file.drawio...>'); process.exit(2); }
  const browser = await chromium.launch();
  for (const file of files) {
    const xml = fs.readFileSync(file, 'utf8');
    // the viewer fits the diagram to the viewport: size it to the diagram (top-level cells) and render at 2x,
    // capped at 16000 px on the longer side, Chromium's limit for one screenshot
    const geoms = [...xml.matchAll(/<mxGeometry x="([\d.-]+)" y="([\d.-]+)" width="([\d.]+)" height="([\d.]+)" as="geometry"/g)]
      .map(m => m.slice(1).map(Number)).filter(([, , w]) => w > 60);
    const width = Math.ceil(Math.max(...geoms.map(([x, , w]) => x + w))) + 48;
    const height = Math.ceil(Math.max(...geoms.map(([, y, , h]) => y + h))) + 48;
    const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: Math.min(2, 16000 / Math.max(width, height)) });
    page.on('pageerror', e => console.error('page error:', e.message));
    await page.setContent(`<body style="margin:0;background:#fff"><div id="d"></div><script src="${VIEWER}"></script></body>`, { waitUntil: 'load' });
    await page.waitForFunction(() => typeof GraphViewer !== 'undefined', null, { timeout: 30000 });
    await page.evaluate(x => {
      const d = document.getElementById('d'); d.className = 'mxgraph';
      d.setAttribute('data-mxgraph', JSON.stringify({ xml: x, border: 16, toolbar: '', nav: false }));
      GraphViewer.processElements();
    }, xml);
    await page.waitForTimeout(1500);
    const svg = await page.$('#d svg');
    if (!svg) throw new Error(`${path.basename(file)}: the viewer drew nothing (is VIEWER reachable?)`);
    const png = await svg.screenshot();
    const out = file.replace(/\.drawio$/, '.png');
    fs.writeFileSync(out, embed(Buffer.from(png), xml));
    console.log('wrote', path.relative(process.cwd(), out));
    await page.close();
  }
  await browser.close();
})();
