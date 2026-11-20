// Mass vs tip-deflection scatter plot on a canvas (no external library).
const COLORS = { feas: '#1f8a4c', fdef: '#b9bfcb', fstr: '#e39b3b', cur: '#2457c5' };

function niceTicks(min, max, n = 6) {
  const span = max - min || Math.abs(max) || 1;
  const step0 = span / n;
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => span / s <= n) || 10 * mag;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) ticks.push(+v.toPrecision(12));
  return ticks;
}

function logTicks(min, max) {
  const t = [];
  for (let e = Math.floor(Math.log10(min)); e <= Math.ceil(Math.log10(max)); e++) {
    for (const m of [1, 2, 5]) { const v = m * Math.pow(10, e); if (v >= min * 0.999 && v <= max * 1.001) t.push(v); }
  }
  return t;
}

const fmt = v => Number(v.toPrecision(3)).toString();

export class ScatterPlot {
  constructor(canvas, tooltip, onSelect) {
    this.c = canvas; this.tip = tooltip; this.onSelect = onSelect;
    this.ctx = canvas.getContext('2d');
    this.data = null;
    new ResizeObserver(() => this.draw()).observe(canvas);
    canvas.addEventListener('mousemove', e => this.hover(e));
    canvas.addEventListener('mouseleave', () => { this.tip.hidden = true; });
    canvas.addEventListener('click', e => { const p = this.pick(e); if (p) this.onSelect(p.id); });
  }

  setData(d) { this.data = d; this.draw(); }

  status(c) {
    if (c.feasible) return 'feas';
    const defl = c.checks.find(k => k.name === 'tip_deflection');
    return defl && !defl.passed ? 'fdef' : 'fstr';
  }

  draw() {
    const c = this.c, dpr = window.devicePixelRatio || 1;
    const W = c.clientWidth, H = c.clientHeight;
    if (!W || !H) return;
    c.width = W * dpr; c.height = H * dpr;
    const g = this.ctx; g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    if (!this.data) return;
    const { cands, current, limit, selectedId } = this.data;
    const pts = [...cands];
    const all = pts.concat([current]);
    let logy = this.data.logy && all.every(p => p.deflection_mm > 0);
    this.logyActive = logy;
    const m = { l: 58, r: 12, t: 10, b: 40 };
    const xs = all.map(p => p.mass_g), ys = all.map(p => p.deflection_mm).concat([limit]);
    let x0 = Math.min(...xs), x1 = Math.max(...xs);
    const xp = (x1 - x0) * 0.04 || 1; x0 = Math.max(0, x0 - xp); x1 += xp;
    let y0 = Math.min(...ys), y1 = Math.max(...ys);
    if (logy) { y0 /= 1.4; y1 *= 1.4; } else { const yp = (y1 - y0) * 0.05 || 1; y0 = Math.max(0, y0 - yp); y1 += yp; }
    const X = v => m.l + (v - x0) / (x1 - x0) * (W - m.l - m.r);
    const Y = logy
      ? v => H - m.b - (Math.log10(v) - Math.log10(y0)) / (Math.log10(y1) - Math.log10(y0)) * (H - m.t - m.b)
      : v => H - m.b - (v - y0) / (y1 - y0) * (H - m.t - m.b);
    this.X = X; this.Y = Y;

    // grid + axes
    g.font = '11px system-ui'; g.fillStyle = '#5b6475'; g.strokeStyle = '#e3e7ee'; g.lineWidth = 1;
    for (const t of niceTicks(x0, x1)) {
      const x = X(t); g.beginPath(); g.moveTo(x, m.t); g.lineTo(x, H - m.b); g.stroke();
      g.textAlign = 'center'; g.fillText(fmt(t), x, H - m.b + 14);
    }
    for (const t of (logy ? logTicks(y0, y1) : niceTicks(y0, y1))) {
      const y = Y(t); g.beginPath(); g.moveTo(m.l, y); g.lineTo(W - m.r, y); g.stroke();
      g.textAlign = 'right'; g.fillText(fmt(t), m.l - 5, y + 4);
    }
    g.strokeStyle = '#8a93a6'; g.beginPath(); g.moveTo(m.l, m.t); g.lineTo(m.l, H - m.b); g.lineTo(W - m.r, H - m.b); g.stroke();
    g.fillStyle = '#1c2230'; g.textAlign = 'center'; g.fillText('Mass [g]', m.l + (W - m.l - m.r) / 2, H - 6);
    g.save(); g.translate(13, m.t + (H - m.t - m.b) / 2); g.rotate(-Math.PI / 2);
    g.fillText('Tip deflection [mm]' + (logy ? ' (log)' : ''), 0, 0); g.restore();

    // limit line
    g.strokeStyle = '#c23a3a'; g.setLineDash([6, 4]); g.lineWidth = 1.5;
    g.beginPath(); g.moveTo(m.l, Y(limit)); g.lineTo(W - m.r, Y(limit)); g.stroke(); g.setLineDash([]);
    g.fillStyle = '#c23a3a'; g.textAlign = 'right'; g.fillText(`limit ${fmt(limit)} mm`, W - m.r - 2, Y(limit) - 4);

    // points (infeasible first, then feasible on top)
    const order = { fdef: 0, fstr: 1, feas: 2 };
    pts.sort((a, b) => order[this.status(a)] - order[this.status(b)]);
    for (const p of pts) {
      g.fillStyle = COLORS[this.status(p)]; g.globalAlpha = 0.85;
      g.beginPath(); g.arc(X(p.mass_g), Y(p.deflection_mm), 3.2, 0, 2 * Math.PI); g.fill();
    }
    g.globalAlpha = 1;
    // current design
    const cx = X(current.mass_g), cy = Y(current.deflection_mm);
    g.fillStyle = COLORS.cur; g.strokeStyle = '#fff'; g.lineWidth = 1.5;
    g.beginPath(); g.moveTo(cx, cy - 7); g.lineTo(cx + 7, cy); g.lineTo(cx, cy + 7); g.lineTo(cx - 7, cy); g.closePath(); g.fill(); g.stroke();
    // selected
    const sel = selectedId ? cands.find(p => p.id === selectedId) : null;
    if (sel) {
      g.strokeStyle = '#111'; g.lineWidth = 2;
      g.beginPath(); g.arc(X(sel.mass_g), Y(sel.deflection_mm), 7.5, 0, 2 * Math.PI); g.stroke();
    }
    this.pts = pts;
  }

  pick(e) {
    if (!this.pts) return null;
    const r = this.c.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    let best = null, bd = 64;
    for (const p of this.pts) {
      const d = (this.X(p.mass_g) - mx) ** 2 + (this.Y(p.deflection_mm) - my) ** 2;
      if (d < bd) { bd = d; best = p; }
    }
    return best;
  }

  hover(e) {
    const p = this.pick(e);
    if (!p) { this.tip.hidden = true; return; }
    const r = this.c.getBoundingClientRect();
    this.tip.hidden = false;
    this.tip.innerHTML = `b = ${fmt(p.b_mm)} mm, h = ${fmt(p.h_mm)} mm<br>mass ${fmt(p.mass_g)} g · δ ${fmt(p.deflection_mm)} mm · σ ${fmt(p.stress_MPa)} MPa<br>${p.feasible ? 'feasible' + (p.rank ? ' (rank ' + p.rank + ')' : '') : 'rejected'} — click to select`;
    const x = e.clientX - r.left + 12, y = e.clientY - r.top + 12;
    this.tip.style.left = Math.min(x, r.width - 230) + 'px';
    this.tip.style.top = Math.min(y, r.height - 60) + 'px';
  }
}
