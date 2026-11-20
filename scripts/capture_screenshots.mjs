// Regenerate the documentation screenshots in docs/images/.
//
// Usage (with the app running at http://127.0.0.1:8000 and no LLM key, so the
// rule-based fallback is shown):
//     node scripts/capture_screenshots.mjs
// Environment: CHROME_PATH (browser executable), APP_URL (default http://127.0.0.1:8000)
//
// Dependency-free: Node >= 22 (global WebSocket/fetch) + a Chromium-based browser.
import { spawn } from 'node:child_process';
import { mkdtempSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const APP = process.env.APP_URL || 'http://127.0.0.1:8000';
const PORT = 9333;
const CANDIDATES = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
].filter(Boolean);
const chromePath = CANDIDATES.find(p => existsSync(p));
if (!chromePath) { console.error('No Chrome/Chromium found; set CHROME_PATH.'); process.exit(1); }

const sleep = ms => new Promise(r => setTimeout(r, ms));
const chrome = spawn(chromePath, [
  '--headless=new', `--remote-debugging-port=${PORT}`, '--hide-scrollbars',
  '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--no-first-run',
  `--user-data-dir=${mkdtempSync(join(tmpdir(), 'mechdesign-shots-'))}`, 'about:blank',
], { stdio: 'ignore' });

async function connect() {
  for (let i = 0; i < 50; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const page = list.find(t => t.type === 'page');
      if (page) return page.webSocketDebuggerUrl;
    } catch { /* not up yet */ }
    await sleep(200);
  }
  throw new Error('Could not connect to the browser');
}

const ws = new WebSocket(await connect());
await new Promise(r => ws.addEventListener('open', r, { once: true }));
let nextId = 1;
const pending = new Map();
ws.addEventListener('message', ev => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = nextId++;
  pending.set(id, m => (m.error ? reject(new Error(m.error.message)) : resolve(m.result)));
  ws.send(JSON.stringify({ id, method, params }));
});
const evaluate = async expr => {
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text);
  return r.result.value;
};
async function shot(name, height = 1080) {
  await send('Emulation.setDeviceMetricsOverride', { width: 1600, height, deviceScaleFactor: 1, mobile: false });
  await sleep(800);
  const { data } = await send('Page.captureScreenshot', { format: 'png' });
  const out = join(ROOT, 'docs', 'images', name);
  writeFileSync(out, Buffer.from(data, 'base64'));
  console.log('wrote', out);
}

try {
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1080, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: APP });
  await sleep(4000);
  await shot('app.png');

  // Assistant workflow: request -> fill the missing requirement -> apply -> select the top candidate.
  await evaluate(`(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    [...document.querySelectorAll('.chip')].find(c => c.textContent.includes('stiffer')).click();
    await wait(800);
    const inp = document.querySelector('#chat input[data-missing]');
    inp.value = '0.4'; inp.dispatchEvent(new Event('input', { bubbles: true }));
    [...document.querySelectorAll('.btn-apply')].at(-1).click();
    await wait(1500);
    document.querySelector('#cand-table tbody tr').click();
    await wait(300);
    document.querySelector('#btn-crosscheck').click();
    await wait(1500);
    document.querySelector('#chat').scrollTop = 0;
    window.scrollTo(0, 0);
  })()`);
  await shot('assistant-workflow.png', 1180);
} finally {
  ws.close();
  chrome.kill();
}
