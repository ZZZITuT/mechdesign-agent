// Record the README demo (docs/images/demo.gif) and the close-up screenshots
// (assistant-proposal.png, scatter.png, view-3d.png, crosscheck.png).
//
// Usage (with the app running at http://127.0.0.1:8000 and no LLM key):
//     node scripts/record_demo.mjs
// Needs: Node >= 22, a Chromium-based browser (CHROME_PATH) and ffmpeg on PATH.
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const IMAGES = join(ROOT, 'docs', 'images');
const APP = process.env.APP_URL || 'http://127.0.0.1:8000';
const REQUEST = 'Make it 30% stiffer without increasing its width, and keep h/b at most 3.';
const W = 1600, H = 1000, PORT = 9334;
const chromePath = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
].filter(Boolean).find(p => existsSync(p));
if (!chromePath) { console.error('No Chrome/Chromium found; set CHROME_PATH.'); process.exit(1); }

const FRAMES = mkdtempSync(join(tmpdir(), 'mechdesign-demo-'));
const chrome = spawn(chromePath, [
  '--headless=new', `--remote-debugging-port=${PORT}`, '--hide-scrollbars', '--use-angle=swiftshader',
  '--enable-unsafe-swiftshader', '--no-first-run', `--user-data-dir=${join(FRAMES, 'profile')}`, 'about:blank',
], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));

let wsUrl;
for (let i = 0; i < 50 && !wsUrl; i++) {
  try { wsUrl = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find(t => t.type === 'page')?.webSocketDebuggerUrl; } catch { /* not up yet */ }
  if (!wsUrl) await sleep(200);
}
if (!wsUrl) throw new Error('Could not connect to the browser');
const ws = new WebSocket(wsUrl);
await new Promise(r => ws.addEventListener('open', r, { once: true }));
let nextId = 1;
const pending = new Map();
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = nextId++;
  pending.set(id, m => (m.error ? reject(new Error(`${method}: ${m.error.message}`)) : resolve(m.result)));
  ws.send(JSON.stringify({ id, method, params }));
});
const evaluate = async expr => {
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(`${expr.slice(0, 80)} -> ${r.exceptionDetails.text}`);
  return r.result.value;
};
const metrics = dsf => send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: dsf, mobile: false });
const ease = t => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);

// ---- frame and still capture
let frame = 0;
const concat = [];
async function snap(seconds) {
  const { data } = await send('Page.captureScreenshot', { format: 'png' });
  const name = `f${String(++frame).padStart(4, '0')}.png`;
  writeFileSync(join(FRAMES, name), Buffer.from(data, 'base64'));
  concat.push(`file '${name}'`, `duration ${seconds}`);
}
async function still(name, elementsExpr, pad = 8) {
  await evaluate(`document.getElementById('__cur').style.display = 'none'`);
  await metrics(2); await sleep(900);
  const r = await evaluate(`(() => { const b = (${elementsExpr}).map(e => e.getBoundingClientRect());
    const x = Math.min(...b.map(v => v.left)), y = Math.min(...b.map(v => v.top));
    return { x, y, w: Math.max(...b.map(v => v.right)) - x, h: Math.max(...b.map(v => v.bottom)) - y }; })()`);
  const clip = { x: Math.max(0, r.x - pad), y: Math.max(0, r.y - pad), width: r.w + 2 * pad, height: r.h + 2 * pad, scale: 1 };
  const { data } = await send('Page.captureScreenshot', { format: 'png', clip });
  writeFileSync(join(IMAGES, name), Buffer.from(data, 'base64'));
  console.log('wrote', join(IMAGES, name));
  await metrics(1); await sleep(900);
  await evaluate(`document.getElementById('__cur').style.display = 'block'`);
}

// ---- a visible cursor (headless Chrome has none)
let cx = 1180, cy = 620;
const centre = sel => evaluate(`(() => { const e = ${sel}; e.scrollIntoView({ block: 'nearest' });
  const b = e.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; })()`);
async function moveTo(x, y, steps = 8) {
  const x0 = cx, y0 = cy;
  for (let i = 1; i <= steps; i++) {
    cx = x0 + (x - x0) * ease(i / steps); cy = y0 + (y - y0) * ease(i / steps);
    await evaluate(`__cursor(${cx}, ${cy}, false)`); await snap(0.04);
  }
}
async function clickOn(sel, waitMs = 600, hold = 0.35) {
  const p = await centre(sel);
  await moveTo(p.x, p.y);
  await evaluate(`__cursor(${cx}, ${cy}, true)`); await snap(0.12);
  await evaluate(`(${sel}).click()`); await sleep(waitMs);
  await evaluate(`__cursor(${cx}, ${cy}, false)`); await snap(hold);
}
async function scrollTo(target, to, steps = 8) {
  const from = await evaluate(`${target}.scrollTop`);
  for (let i = 1; i <= steps; i++) { await evaluate(`${target}.scrollTop = ${from + (to - from) * ease(i / steps)}`); await snap(0.05); }
}

try {
  await send('Page.enable');
  await metrics(1);
  await send('Page.navigate', { url: APP });
  await sleep(4500);
  await evaluate(`(() => {
    const c = document.createElement('div'); c.id = '__cur';
    c.style.cssText = 'position:fixed;left:0;top:0;z-index:99999;pointer-events:none;width:0;height:0';
    c.innerHTML = '<div id="__ring" style="position:absolute;left:-15px;top:-15px;width:30px;height:30px;border-radius:50%;background:rgba(37,99,235,.28);border:2px solid rgba(37,99,235,.85);display:none"></div>' +
      '<svg width="26" height="26" viewBox="0 0 24 24" style="position:absolute;left:-3px;top:-2px"><path d="M4 2 L4 19 L8.6 14.9 L11.6 21.6 L14.4 20.4 L11.4 13.8 L17.6 13.8 Z" fill="#111827" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
    document.body.appendChild(c);
    window.__cursor = (x, y, down) => { c.style.transform = 'translate(' + x + 'px,' + y + 'px)'; document.getElementById('__ring').style.display = down ? 'block' : 'none'; };
    __cursor(${cx}, ${cy}, false);
  })()`);
  await snap(1.8);

  // 1. Type a request.
  await clickOn(`document.querySelector('#chat-input')`, 100, 0.1);
  await evaluate(`document.querySelector('#chat-input').focus()`);
  for (let i = 0; i < REQUEST.length; i += 3) { await send('Input.insertText', { text: REQUEST.slice(i, i + 3) }); await snap(0.045); }
  await snap(0.5);

  // 2. Interpret it and review the proposal.
  await clickOn(`document.querySelector('#chat-form button[type=submit]')`, 900, 0.2);
  const top = await evaluate(`(() => { const m = [...document.querySelectorAll('#chat .msg')].at(-1);
    return m.offsetTop - document.querySelector('#chat').offsetTop - 6; })()`);
  await scrollTo(`document.querySelector('#chat')`, top);
  await snap(2.6);
  await still('assistant-proposal.png', `[[...document.querySelectorAll('#chat .msg')].at(-1)]`);
  await scrollTo(`document.querySelector('#chat')`, 1e5);
  await snap(0.6);

  // 3. Apply and recalculate.
  await clickOn(`[...document.querySelectorAll('.btn-apply')].at(-1)`, 1600, 1.9);

  // 4. Select the lightest feasible design in the table.
  await scrollTo(`document.scrollingElement`, 420, 10);
  await snap(0.7);
  await clickOn(`document.querySelector('#cand-table tbody tr')`, 700, 0.6);
  await scrollTo(`document.scrollingElement`, 0, 10);
  await snap(0.8);
  await still('scatter.png', `[document.querySelector('.vizplot')]`);
  await still('view-3d.png', `[document.querySelector('.viz3d')]`);

  // 5. Swing the 3D view out and back.
  const v = await centre(`document.querySelector('#view3d')`);
  await moveTo(v.x - 60, v.y + 30);
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: cx, y: cy });
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: cx, y: cy, button: 'left', buttons: 1, clickCount: 1 });
  await evaluate(`__cursor(${cx}, ${cy}, true)`);
  for (const [dx, dy] of [...Array(14).fill([9, -1.6]), ...Array(14).fill([-9, 1.6])]) {
    cx += dx; cy += dy;
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: cx, y: cy, button: 'left', buttons: 1 });
    await evaluate(`__cursor(${cx}, ${cy}, true)`); await sleep(30); await snap(0.06);
  }
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: cx, y: cy, button: 'left', buttons: 0, clickCount: 1 });
  await evaluate(`__cursor(${cx}, ${cy}, false)`); await snap(0.8);

  // 6. Independent FE cross-check.
  await clickOn(`document.querySelector('#btn-crosscheck')`, 2500, 3.2);
  await still('crosscheck.png', `[document.querySelector('#sel-numbers'), document.querySelector('#sel-checks'), document.querySelector('#crosscheck')]`);
} finally {
  ws.close();
  chrome.kill();
}

// ---- encode the GIF (the concat demuxer needs the last frame repeated to honour its duration)
concat.push(`file 'f${String(frame).padStart(4, '0')}.png'`);
writeFileSync(join(FRAMES, 'frames.txt'), concat.join('\n') + '\n');
mkdirSync(IMAGES, { recursive: true });
const gif = join(IMAGES, 'demo.gif');
const r = spawnSync('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', join(FRAMES, 'frames.txt'),
  '-vf', 'fps=20,scale=1200:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=256:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle',
  '-loop', '0', gif], { stdio: 'inherit' });
if (r.status !== 0) { console.error('ffmpeg failed; frames kept in', FRAMES); process.exit(1); }
console.log('wrote', gif, `(${frame} frames)`);
rmSync(FRAMES, { recursive: true, force: true });
