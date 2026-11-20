// 3D cantilever viewer (Three.js). Visualisation only: the deflection shape and
// tip deflection come from the backend mechanics engine.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

function label(text, cls) {
  const d = document.createElement('div');
  d.className = 'lbl ' + (cls || '');
  d.textContent = text;
  return new CSS2DObject(d);
}

export class BeamViewer {
  constructor(el) {
    this.el = el;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(38, 1, 0.05, 500);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(this.renderer.domElement);
    this.labels = new CSS2DRenderer();
    this.labels.domElement.style.position = 'absolute';
    this.labels.domElement.style.top = '0';
    this.labels.domElement.style.pointerEvents = 'none';
    el.appendChild(this.labels.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x8a93a6, 1.6));
    const dl = new THREE.DirectionalLight(0xffffff, 1.6);
    dl.position.set(6, 10, 8);
    this.scene.add(dl);

    this.group = new THREE.Group();
    this.scene.add(this.group);
    this.cameraSet = false;

    this.renderer.domElement.addEventListener('dblclick', () => this.fit());
    new ResizeObserver(() => this.resize()).observe(el);
    this.resize();
    const loop = () => { this.controls.update(); this.render(); requestAnimationFrame(loop); };
    loop();
  }

  resize() {
    const w = this.el.clientWidth, h = this.el.clientHeight;
    if (!w || !h) return;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
    this.labels.setSize(w, h);
  }

  render() { this.renderer.render(this.scene, this.camera); this.labels.render(this.scene, this.camera); }

  clear() {
    for (const c of [...this.group.children]) {
      this.group.remove(c);
      c.traverse?.(o => { o.geometry?.dispose?.(); o.material?.dispose?.(); if (o.isCSS2DObject) o.element.remove(); });
    }
  }

  /**
   * @param p {L,b,h (mm), F (N), delta (mm, from engine), mag (number), shape {xi:[], v:[]} normalised v/v_tip, showU, showD}
   */
  update(p) {
    this.clear();
    const S = 10 / p.L;                 // scene units per mm (beam length = 10 units)
    const Ls = p.L * S, hs = p.h * S, bs = p.b * S;
    const disp = (xi) => {               // magnified displacement in scene units (downward)
      const { xi: X, v: V } = p.shape;
      let i = Math.min(X.length - 2, Math.max(0, Math.floor(xi * (X.length - 1))));
      const t = (xi - X[i]) / (X[i + 1] - X[i]);
      return (V[i] + t * (V[i + 1] - V[i])) * p.delta * p.mag * S;
    };

    // Fixed support (wall)
    const wallH = Math.max(hs * 4, 2.5), wallB = Math.max(bs * 2.2, 2.5);
    const wall = new THREE.Mesh(new THREE.BoxGeometry(0.35, wallH, wallB),
      new THREE.MeshStandardMaterial({ color: 0x5b6475, roughness: 0.9 }));
    wall.position.set(-0.175, 0, 0);
    this.group.add(wall);
    const hatch = [];
    // Hatching on the front face of the support (conventional "fixed" symbol)
    for (let k = -7; k <= 7; k++) {
      const y0 = k * wallH / 10, y1 = y0 + 0.35;
      if (y1 > wallH / 2 || y0 < -wallH / 2) continue;
      hatch.push(-0.35, y0, wallB / 2 + 0.002, 0, y1, wallB / 2 + 0.002);
    }
    const hg = new THREE.BufferGeometry();
    hg.setAttribute('position', new THREE.Float32BufferAttribute(hatch, 3));
    this.group.add(new THREE.LineSegments(hg, new THREE.LineBasicMaterial({ color: 0xd8dde6 })));
    const wl = label('Fixed end (ideal clamp)', 'fixed');
    wl.position.set(-0.2, wallH / 2 + 0.3, 0);
    this.group.add(wl);

    // Undeformed outline
    if (p.showU) {
      const ug = new THREE.BoxGeometry(Ls, hs, bs);
      ug.translate(Ls / 2, 0, 0);
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(ug),
        new THREE.LineDashedMaterial({ color: 0x4b5563, dashSize: 0.15, gapSize: 0.08 }));
      edges.computeLineDistances();
      this.group.add(edges);
      const um = new THREE.Mesh(ug, new THREE.MeshStandardMaterial({ color: 0x9aa3b2, transparent: true, opacity: p.showD ? 0.18 : 0.6 }));
      this.group.add(um);
    }

    // Deformed (magnified) shape
    const tipDrop = disp(1);
    if (p.showD) {
      const nx = 80;
      const dg = new THREE.BoxGeometry(Ls, hs, bs, nx, 1, 1);
      dg.translate(Ls / 2, 0, 0);
      const pos = dg.attributes.position;
      for (let i = 0; i < pos.count; i++) {
        const xi = Math.min(1, Math.max(0, pos.getX(i) / Ls));
        pos.setY(i, pos.getY(i) - disp(xi));
      }
      dg.computeVertexNormals();
      const dm = new THREE.Mesh(dg, new THREE.MeshStandardMaterial({ color: 0xe07b39, roughness: 0.55, transparent: true, opacity: 0.92 }));
      this.group.add(dm);
      this.group.add(new THREE.LineSegments(new THREE.EdgesGeometry(dg, 30), new THREE.LineBasicMaterial({ color: 0x8a3d12 })));
    }

    // Load arrow at the free end, pointing in the load direction (-y)
    const yTipTop = (p.showD ? -tipDrop : 0) + hs / 2;
    const aLen = 2.2;
    if (p.F > 0) {
      const mat = new THREE.MeshStandardMaterial({ color: 0xc23a3a });
      const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, aLen - 0.55, 16), mat);
      shaft.position.set(Ls, yTipTop + 0.55 + (aLen - 0.55) / 2, 0);
      const head = new THREE.Mesh(new THREE.ConeGeometry(0.22, 0.55, 20), mat);
      head.rotation.z = Math.PI;               // point down (load direction)
      head.position.set(Ls, yTipTop + 0.275, 0);
      this.group.add(shaft, head);
    }
    const fl = label(p.F > 0 ? `F = ${fmt(p.F)} N` : 'F = 0 N (no load)', 'load');
    fl.position.set(Ls, yTipTop + aLen + 0.35, 0);
    this.group.add(fl);

    const lL = label(`L = ${fmt(p.L)} mm`);
    lL.position.set(Ls / 2, -Math.max(hs, 0.3) / 2 - 0.5 - (p.showD ? tipDrop / 2 : 0), bs / 2);
    this.group.add(lL);
    const lb = label(`b = ${fmt(p.b)} mm, h = ${fmt(p.h)} mm`);
    lb.position.set(Ls * 0.55, hs / 2 + 0.55, -bs / 2);
    this.group.add(lb);

    this.Ls = Ls;
    if (!this.cameraSet) { this.fit(); this.cameraSet = true; }
  }

  /** Frame the whole beam + support + load arrow (double-click the view to reset). */
  fit() {
    const Ls = this.Ls || 10;
    const vfov = THREE.MathUtils.degToRad(this.camera.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * Math.max(this.camera.aspect, 0.3));
    const span = Ls + 4;
    const dist = Math.max(1.15 * span / (2 * Math.tan(hfov / 2)), 1.15 * 7 / (2 * Math.tan(vfov / 2)));
    const dir = new THREE.Vector3(0.32, 0.38, 1).normalize();
    const target = new THREE.Vector3(Ls * 0.45, -0.3, 0);
    this.controls.target.copy(target);
    this.camera.position.copy(target.clone().addScaledVector(dir, dist));
    this.controls.update();
  }
}

function fmt(v) { return Number(v.toPrecision(4)).toString(); }
