#!/usr/bin/env node
// Build the pitch slideshow from its slide sources: web_docs/deck/slides/NN-<id>.html, one <section> per slide with
// the speaker notes in its <aside>. Writes:
//   web_docs/static/deck/index.html               a reveal.js slideshow (arrow keys or swipe to page, N for notes,
//                                                 S for the speaker view), served at /docs/deck/ in production
//   web_docs/docs/pitch/full-text-and-notes.md    every slide's text and notes, for reading or search
//
//   node web_docs/scripts/build-deck.mjs           build
//   node web_docs/scripts/build-deck.mjs --check   exit 1 if the built files are out of date (CI)
//
// Pattern from healthtransformationlab/health-transformation-lab-nlp (docs/build_decks.py). No dependencies.

import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const WEB_DOCS = join(dirname(fileURLToPath(import.meta.url)), '..')
const SLIDES = join(WEB_DOCS, 'deck', 'slides')
const OUT_HTML = join(WEB_DOCS, 'static', 'deck', 'index.html')
const OUT_MD = join(WEB_DOCS, 'docs', 'pitch', 'full-text-and-notes.md')

const TITLE = 'CommunityOne · Open Navigator: the pitch'
const NOTE = 'Open-source project of CommunityOne, a 501(c)(3) nonprofit. Every figure is cited on its slide; ' +
  'examples marked illustrative are not records.'
const SITE = 'https://www.communityone.com'
const DOCS = 'https://www.communityone.com/docs'
const REPO = 'https://github.com/getcommunityone/open-navigator'
const REVEAL = 'https://cdn.jsdelivr.net/npm/reveal.js@5.1.0'
// Subresource integrity (sha384 of the npm package's own files): a changed file is refused
const SRI = {
  css: 'sha384-YgvgKeZJykuztG+iQPoZHNZENTFZvOcOJ/uRzmJTje6GHYN9zAw+y5rx/L8MQKA/',
  js: 'sha384-M/JtqCVlLcK9lwVnBnMXP0V577CBULkjodKsR/PITOe4MSKNbbwqCemEyluOw0+5',
  notes: 'sha384-vGIe90H8q0nlnrw/zr9vn+r39OtjvzBfai9voOybn5Bx+KmKLtSxhM+YIfcrsfI3',
}

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const unesc = (s) => s.replace(/&nbsp;/g, ' ').replace(/&middot;/g, '·').replace(/&rarr;/g, '→').replace(/&mdash;/g, '—')
  .replace(/&ndash;/g, '–').replace(/&rsquo;/g, '’').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
  .replace(/&#39;/g, "'").replace(/&amp;/g, '&')

function slides() {
  return readdirSync(SLIDES).filter((f) => /^\d\d-.+\.html$/.test(f)).sort().map((f) => {
    const src = readFileSync(join(SLIDES, f), 'utf8')
    const notes = src.match(/<aside>([\s\S]*?)<\/aside>/)
    return { id: f.slice(3, -5), section: src.replace(/\s*<aside>[\s\S]*?<\/aside>/, '').trim(),
      notes: notes ? notes[1].trim() : '' }
  })
}

function heading({ id, section }) {
  const m = section.match(/<h[12][^>]*>([\s\S]*?)<\/h[12]>/)
  return m ? unesc(m[1].replace(/<[^>]+>/g, '')).trim() : id
}

function visibleText(section) {
  return section.replace(/<svg[\s\S]*?<\/svg>/g, '').split(/<[^>]+>/).map((p) => unesc(p).trim()).filter(Boolean)
}

// Docusaurus reads the page as CommonMark (format: md), but escape the characters MDX would choke on anyway
const mdSafe = (s) => s.replace(/[{}<>]/g, (c) => `\\${c}`)

const CSS = `html,body{height:100%}body{margin:0;background:#292524;font-family:'Source Sans 3',Arial,sans-serif}*{box-sizing:border-box;margin:0}
.topnav{position:fixed;top:0;left:0;right:0;z-index:50;height:56px;background:#1c1917;border-bottom:1px solid rgba(250,250,249,.12);display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 16px}
.home{display:flex;align-items:center;gap:10px;font:700 16px 'Playfair Display',Georgia,serif;color:#fafaf9;text-decoration:none;white-space:nowrap}
.home .mark{display:grid;place-items:center;width:28px;height:28px;border-radius:8px;background:#0d9488;color:#fafaf9;font-size:15px}
.links{display:flex;flex:1 1 auto;justify-content:flex-end;align-items:center;gap:4px;min-width:0}
.links a,.topnav button{color:#d6d3d1;text-decoration:none;font:600 14px 'Source Sans 3',Arial,sans-serif;padding:7px 11px;border-radius:8px;background:none;border:0;cursor:pointer;white-space:nowrap}
.links a:hover,.topnav button:hover{color:#fafaf9;background:rgba(255,255,255,.07)}.topnav button[aria-pressed=true]{color:#5eead4}
.links a.cta{background:#0d9488;color:#fafaf9;margin-left:6px}.links a.cta:hover{background:#14b8a6}
.pager{display:flex;align-items:center;gap:4px;min-width:0}.pager button{background:#0d9488;color:#fafaf9}.pager button:disabled{opacity:.35;cursor:default}
.topnav select{width:280px;max-width:280px;min-width:72px;font:600 14px 'Source Sans 3',Arial,sans-serif;color:#fafaf9;background:#292524;border:1px solid rgba(250,250,249,.3);border-radius:8px;padding:6px 8px}
.topnav button:focus-visible,.topnav select:focus-visible{outline:2px solid #fafaf9;outline-offset:2px}
.disclaimer{position:fixed;top:56px;left:0;right:0;z-index:40;padding:6px 16px;background:#292524;color:#d6d3d1;font:13px/1.45 'Source Sans 3',Arial,sans-serif}
.reveal-viewport,.reveal{background:#292524}.reveal{position:fixed;top:84px;left:0;right:0;bottom:0;width:auto;height:auto}
.reveal .slides{text-align:left}.reveal .progress{color:#14b8a6}
.reveal .controls{color:#14b8a6}.reveal .slide-number{font:600 14px 'Source Sans 3',Arial,sans-serif;background:rgba(28,25,23,.8);color:#fafaf9}
.notes-panel{position:fixed;left:0;right:0;bottom:0;z-index:45;max-height:35vh;overflow:auto;background:#f5f5f4;color:#1c1917;padding:16px 20px 28px;font-size:16px;line-height:1.5;box-shadow:0 -8px 24px rgba(0,0,0,.3)}
.notes-panel[hidden]{display:none}
@media (max-width:1100px){.home .name,.links a.doc{display:none}}
@media (max-width:560px){.pager .lbl,.links a.cta{display:none}}
/* slide styles: every slide is 1920 x 1080 */
.reveal .slides>section.s{height:1080px;padding:112px 128px 150px;background:#fafaf9;color:#1c1917;display:flex;flex-direction:column;gap:40px;font-family:'Source Sans 3',Arial,sans-serif}
.reveal .slides>section.s.dark{background:#1c1917;color:#fafaf9;justify-content:space-between}
.s .eyebrow{font:700 24px 'IBM Plex Mono',monospace;letter-spacing:3px;text-transform:uppercase;color:#0f766e}
.s.dark .eyebrow{color:#5eead4}
.s h1{font:700 88px/1.1 'Playfair Display',Georgia,serif}.s h1.accent{color:#5eead4}
.s h2{font:700 60px/1.12 'Playfair Display',Georgia,serif}
.s h3{font:700 40px/1.2 'Playfair Display',Georgia,serif;color:#0f766e}
.s p,.s li{font-size:34px;line-height:1.4}.s .lead{font-size:40px;line-height:1.3;color:#44403c;max-width:1560px}
.s.dark .lead{color:#d6d3d1}.s b{font-weight:700}
.s .row{display:flex;gap:32px;align-items:stretch}
.s .card{flex:1;display:flex;flex-direction:column;gap:16px;background:#fff;border:1px solid #e7e5e4;border-left:8px solid #0d9488;border-radius:16px;padding:36px}
.s .card p{font-size:32px}
.s table{border-collapse:collapse;font-size:32px;line-height:1.3;background:#fff;border:1px solid #e7e5e4}
.s th{background:#1c1917;color:#fafaf9;text-align:left}.s th,.s td{padding:16px 20px;border-bottom:1px solid #e7e5e4;vertical-align:top}
.s .flow{display:flex;gap:16px;align-items:stretch}.s .flow .card{border-left-width:1px;border-top:8px solid #0d9488;padding:28px}.s .flow .card p{font-size:28px}
.s .flow .arrow{align-self:center;font-size:48px;color:#0d9488}
.s .callout{font-size:34px;line-height:1.4;background:#0f766e;color:#fafaf9;border-radius:16px;padding:24px 40px}
.s .tag{display:inline-block;font:700 22px 'IBM Plex Mono',monospace;letter-spacing:2px;text-transform:uppercase;background:#0d9488;color:#fafaf9;border-radius:8px;padding:8px 20px}
.s .foot{position:absolute;left:128px;bottom:56px;width:1664px;font-size:22px;color:#78716c}
.s.dark .foot{position:static;color:#a8a29e}
.s ul{padding-left:1.1em;display:flex;flex-direction:column;gap:14px}`

function render() {
  const all = slides()
  const options = all.map((s, i) => `<option value="${s.id}">${i + 1}. ${esc(heading(s))}</option>`).join('')
  const head = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(TITLE)}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Source+Sans+3:wght@400..700&family=IBM+Plex+Mono:wght@700&display=swap">
<link rel="stylesheet" href="${REVEAL}/dist/reveal.css" integrity="${SRI.css}" crossorigin="anonymous">
<style>${CSS}</style></head><body>
<!-- Built by web_docs/scripts/build-deck.mjs from web_docs/deck/slides/. Edit the slides, then rebuild. -->
<nav class="topnav" aria-label="Main">
<a class="home" href="${SITE}/" title="Back to CommunityOne"><span class="mark" aria-hidden="true">←</span><span class="name">CommunityOne</span></a>
<div class="links"><a class="doc" href="${DOCS}/">Docs</a><span class="pager"><button id="deck-prev" aria-label="Previous slide" title="Previous slide (←)">‹<span class="lbl"> Previous</span></button>
<select id="deck-jump" aria-label="Go to slide">${options}</select>
<button id="deck-next" aria-label="Next slide" title="Next slide (→)"><span class="lbl">Next </span>›</button></span>
<button id="deck-notes-btn" aria-pressed="false" title="Speaker notes (N)">Notes</button>
<a class="cta" href="${REPO}" target="_blank" rel="noopener">GitHub ↗</a></div></nav>
<p class="disclaimer" id="deck-disclaimer">${esc(NOTE)}</p>
<div class="reveal"><div class="slides">
`
  const body = all.map((s) => s.section.replace('</section>', `<aside class="notes">${s.notes}</aside>\n</section>`) + '\n').join('\n')
  const tail = `</div></div>
<div class="notes-panel" id="deck-notes" hidden></div>
<script src="${REVEAL}/dist/reveal.js" integrity="${SRI.js}" crossorigin="anonymous"></script><script src="${REVEAL}/plugin/notes/notes.js" integrity="${SRI.notes}" crossorigin="anonymous"></script>
<script>
document.querySelectorAll('.slides a[href^="http"]').forEach(a=>{a.target='_blank';a.rel='noopener'})
var jump=document.getElementById('deck-jump'),prev=document.getElementById('deck-prev'),next=document.getElementById('deck-next'),panel=document.getElementById('deck-notes'),btn=document.getElementById('deck-notes-btn'),bar=document.getElementById('deck-disclaimer'),deck=document.querySelector('.reveal')
function sync(){var s=Reveal.getCurrentSlide();if(!s)return;var i=Reveal.getIndices().h;jump.selectedIndex=i;prev.disabled=Reveal.isFirstSlide();next.disabled=Reveal.isLastSlide();var n=s.querySelector('aside.notes');panel.innerHTML='<b>Slide '+(i+1)+' notes:</b> '+(n?n.innerHTML:'');if(!panel.hidden)fit()}
function fit(){deck.style.top=(56+bar.offsetHeight)+'px';deck.style.bottom=(panel.hidden?0:panel.offsetHeight)+'px';if(Reveal.isReady())Reveal.layout()}
function toggleNotes(){var on=panel.hidden;panel.hidden=!on;btn.setAttribute('aria-pressed',on);fit()}
jump.addEventListener('change',()=>{Reveal.slide(jump.selectedIndex);jump.blur()})
btn.addEventListener('click',toggleNotes)
prev.addEventListener('click',e=>{Reveal.prev();if(e.detail)prev.blur()})
next.addEventListener('click',e=>{Reveal.next();if(e.detail)next.blur()})
fit()
Reveal.initialize({width:1920,height:1080,margin:0.03,center:false,display:'flex',hash:true,history:false,slideNumber:'c/t',scrollActivationWidth:null,
  controls:true,controlsLayout:'edges',controlsTutorial:false,progress:true,transition:'fade',transitionSpeed:'fast',
  keyboard:{78:toggleNotes},keyboardCondition:e=>!e.target.closest('.topnav'),plugins:[RevealNotes]}).then(sync)
Reveal.on('slidechanged',sync)
addEventListener('resize',fit)
</script></body></html>
`
  const md = ['---', 'title: The pitch, full text and notes', 'sidebar_label: Pitch (full text)', 'format: md', '---', '',
    '# CommunityOne · Open Navigator: the pitch, full text and notes', '',
    `${NOTE} [Open the slideshow](${DOCS}/deck/). Built from \`web_docs/deck/slides/\` by ` +
    '`web_docs/scripts/build-deck.mjs`; edit the slides, then rebuild.', '']
  all.forEach((s, i) => {
    md.push(`## Slide ${i + 1}: ${mdSafe(heading(s))}`, '', ...visibleText(s.section).map(mdSafe).map((l) => `${l}  `), '')
    if (s.notes) md.push(`**Speaker notes:** ${mdSafe(unesc(s.notes.replace(/<[^>]+>/g, '')))}`, '')
  })
  return { html: head + body + tail, md: md.join('\n') }
}

const { html, md } = render()
if (process.argv.includes('--check')) {
  const stale = [[OUT_HTML, html], [OUT_MD, md]].filter(([p, want]) => !existsSync(p) || readFileSync(p, 'utf8') !== want)
  if (stale.length) {
    console.error(`deck out of date: ${stale.map(([p]) => p.slice(WEB_DOCS.length + 1)).join(', ')}. ` +
      'Run: node web_docs/scripts/build-deck.mjs')
    process.exit(1)
  }
  console.log('deck up to date')
} else {
  for (const [p, text] of [[OUT_HTML, html], [OUT_MD, md]]) {
    mkdirSync(dirname(p), { recursive: true })
    writeFileSync(p, text)
  }
  console.log(`built ${slides().length} slides: static/deck/index.html, docs/pitch/full-text-and-notes.md`)
}
