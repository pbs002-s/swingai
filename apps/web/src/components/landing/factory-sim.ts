/**
 * The isometric factory line: machines sew garments, a belt carries them to packing,
 * cartons roll to a truck, the truck leaves for export. Pure functions: step() advances
 * the world, draw() returns polygons for React to render.
 */

export type P3 = [number, number, number];
export type Poly = { pts: string; fill: string; stroke?: string; strokeWidth?: number; dim?: boolean };

const K = Math.cos(Math.PI / 6);
export const prj = ([x, y, z]: P3): [number, number] => [(x - y) * K, (x + y) * 0.5 - z];
const pt = (p: P3) => {
  const [a, b] = prj(p);
  return `${a.toFixed(1)},${b.toFixed(1)}`;
};
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const clamp01 = (t: number) => Math.max(0, Math.min(1, t));
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export const DEFAULT_CLOTH = ["#1e4fd8", "#e4572e", "#f2c14e", "#2f9e66", "#8a5a3b"];
let CLOTH: string[] = [...DEFAULT_CLOTH];
/** Change the cloth colours the machines sew with; garments already made keep their slot index. */
export function setCloth(colors: string[]) {
  if (colors.length) CLOTH = colors.filter((c) => /^#[0-9a-f]{6}$/i.test(c));
}
const FACE_T = "var(--surface)";
const FACE_L = "color-mix(in srgb, var(--surface) 90%, var(--ink))";
const FACE_R = "color-mix(in srgb, var(--surface) 80%, var(--ink))";
const shade = (c: string, k: number) => `color-mix(in srgb, ${c} ${k}%, #000)`;

function box(out: Poly[], x: number, y: number, z: number, w: number, d: number, h: number, c?: string) {
  const A: P3 = [x, y, z + h], B: P3 = [x + w, y, z + h], C: P3 = [x + w, y + d, z + h], D: P3 = [x, y + d, z + h];
  const E: P3 = [x, y + d, z], F: P3 = [x + w, y + d, z], G: P3 = [x + w, y, z];
  out.push({ pts: [A, B, C, D].map(pt).join(" "), fill: c ?? FACE_T });
  out.push({ pts: [D, C, F, E].map(pt).join(" "), fill: c ? shade(c, 82) : FACE_L });
  out.push({ pts: [B, G, F, C].map(pt).join(" "), fill: c ? shade(c, 66) : FACE_R });
}

function disc(out: Poly[], axis: "x" | "y", k: number, cu: number, cz: number, r: number, fill: string) {
  const pts: P3[] = [];
  for (let i = 0; i < 18; i++) {
    const a = (i / 18) * Math.PI * 2, u = cu + r * Math.cos(a), z = cz + r * Math.sin(a);
    pts.push(axis === "x" ? [k, u, z] : [u, k, z]);
  }
  out.push({ pts: pts.map(pt).join(" "), fill });
}

function garment(out: Poly[], x: number, y: number, z: number, ci: number) {
  box(out, x, y, z, 20, 14, 3, CLOTH[ci % CLOTH.length]);
  const t = z + 3;
  out.push({ pts: [[x + 2, y + 4, t], [x + 5, y + 7, t], [x + 2, y + 10, t]].map((p) => pt(p as P3)).join(" "), fill: "none", strokeWidth: 0.6 });
}

// ---------- world ----------
type G = { ci: number; state: "chute" | "belt" | "drop"; t: number; from: P3; to: P3; x: number; y: number; z: number; done?: boolean };
type M = { x: number; state: "sew" | "ready"; timer: number; ci: number };
export type World = {
  t: number; phase: number; next: number; made: number; packed: number; shipped: number;
  machines: M[]; garments: G[];
  pack: { state: "open" | "closing" | "waiting" | "arrive"; items: number[]; incoming: number; t: number };
  roller: { items: number[]; x: number }[];
  move: { items: number[]; cell: P3; t: number } | null;
  truck: { state: "loading" | "leaving" | "arriving"; dx: number; t: number; load: { items: number[]; cell: P3 }[] };
};

const SEW = 3.2, BELT_V = 42, CAP = 3, PACK: P3 = [260, -3, 14], SLOTS = [330, 300], BELT_END = 234;
const CELLS: P3[] = [];
for (const z of [14, 26]) for (const x of [424, 396, 368]) for (const y of [-14, 8]) CELLS.push([x, y, z]);
const MACHINES = [18, 92, 166];

export function newWorld(): World {
  return {
    t: 0, phase: 0, next: MACHINES.length, made: 0, packed: 0, shipped: 0,
    machines: MACHINES.map((x, i) => ({ x, state: "sew", timer: (i * SEW) / MACHINES.length, ci: i })),
    garments: [], pack: { state: "open", items: [], incoming: 0, t: 0 }, roller: [], move: null,
    truck: { state: "loading", dx: 0, t: 0, load: [] },
  };
}

export function step(w: World, dt: number) {
  w.t += dt;
  w.phase = (w.phase + BELT_V * dt) % 14;
  const clear = (lx: number) => w.garments.every((g) => g.state === "drop" || Math.abs((g.state === "chute" ? g.to[0] : g.x) - lx) >= 24);
  for (const m of w.machines) {
    if (m.state === "sew") { m.timer += dt; if (m.timer >= SEW) m.state = "ready"; continue; }
    const lx = m.x + 6;
    if (!clear(lx)) continue;
    w.garments.push({ ci: m.ci, state: "chute", t: 0, from: [m.x + 7, -42, 34], to: [lx, -1, 30], x: m.x + 7, y: -42, z: 34 });
    w.made++; m.state = "sew"; m.timer = 0; m.ci = w.next++;
  }
  const accepts = () => w.pack.state === "open" && w.pack.items.length + w.pack.incoming < CAP;
  const onBelt = w.garments.filter((g) => g.state === "belt").sort((a, b) => b.x - a.x);
  let limit = BELT_END;
  for (const g of onBelt) {
    g.x = Math.min(g.x + BELT_V * dt, limit);
    if (g === onBelt[0] && g.x >= BELT_END - 0.01 && accepts()) {
      const k = w.pack.items.length + w.pack.incoming++;
      Object.assign(g, { state: "drop", t: 0, from: [g.x, g.y, g.z], to: [PACK[0] + 3, PACK[1] + 3, PACK[2] + 1 + k * 3] });
    }
    limit = g.x - 23;
  }
  for (const g of w.garments) {
    if (g.state === "belt") continue;
    g.t += dt / (g.state === "chute" ? 0.6 : 0.35);
    const e = ease(clamp01(g.t));
    g.x = lerp(g.from[0], g.to[0], e); g.y = lerp(g.from[1], g.to[1], e);
    g.z = lerp(g.from[2], g.to[2], e) + (g.state === "chute" ? Math.sin(Math.PI * e) * 6 : 0);
    if (g.t < 1) continue;
    if (g.state === "chute") { g.state = "belt"; g.z = 30; } else { g.done = true; w.pack.items.push(g.ci); w.pack.incoming--; }
  }
  w.garments = w.garments.filter((g) => !g.done);
  const p = w.pack;
  if (p.state === "open" && p.items.length === CAP) Object.assign(p, { state: "closing", t: 0 });
  p.t += dt;
  if (p.state === "arrive" && p.t >= 0.5) Object.assign(p, { state: "open", t: 0 });
  if (p.state === "closing" && p.t >= 0.4) Object.assign(p, { state: "waiting", t: 0 });
  if (p.state === "waiting" && w.roller.length < SLOTS.length) {
    w.roller.push({ items: p.items, x: PACK[0] }); w.packed++;
    Object.assign(p, { state: "arrive", items: [], incoming: 0, t: 0 });
  }
  w.roller.forEach((c, i) => { c.x = Math.min(c.x + 80 * dt, SLOTS[i]); });
  const tr = w.truck, r0 = w.roller[0];
  if (tr.state === "loading" && !w.move && r0 && r0.x >= SLOTS[0] && tr.load.length < CELLS.length) {
    w.move = { items: r0.items, cell: CELLS[tr.load.length], t: 0 }; w.roller.shift();
  }
  if (w.move) {
    w.move.t += dt / 0.9;
    if (w.move.t >= 1) {
      tr.load.push({ items: w.move.items, cell: w.move.cell }); w.move = null;
      if (tr.load.length === CELLS.length) Object.assign(tr, { state: "leaving", t: 0 });
    }
  }
  tr.t += dt;
  if (tr.state === "leaving") {
    tr.dx = ease(clamp01(tr.t / 2.2)) * 380;
    if (tr.t >= 2.2) { w.shipped++; Object.assign(tr, { state: "arriving", t: 0, load: [] }); }
  } else if (tr.state === "arriving") {
    tr.dx = (1 - ease(clamp01(tr.t / 2))) * 380;
    if (tr.t >= 2) Object.assign(tr, { state: "loading", dx: 0 });
  }
}

// ---------- drawing ----------
function machine(out: Poly[], m: M, t: number) {
  const x = m.x, c = CLOTH[m.ci % CLOTH.length];
  box(out, x - 4, -50, 0, 46, 36, 30);
  box(out, x, -44, 30, 34, 14, 4);
  if (m.state === "sew") box(out, x + 3 + (m.timer / SEW) * 6, -43, 34, 16, 12, 1, c);
  else garment(out, x + 7, -42, 34, m.ci);
  const bob = m.state === "sew" ? 4 + 2 * Math.sin(t * 22 + x) : 2;
  box(out, x + 2, -42.5, 41, 8, 10, 16);
  out.push({ pts: `${pt([x + 6, -37.5, 41])} ${pt([x + 6, -37.5, 41 - bob])}`, fill: "none" });
  box(out, x + 26, -42, 34, 7, 9, 18);
  box(out, x + 4, -43, 50, 30, 11, 7);
  disc(out, "x", x + 34.5, -37.5, 52, 5, FACE_R);
  // thread cone in the cloth colour
  const base: [number, number][] = [];
  for (let i = 0; i < 12; i++) { const a = (i / 12) * Math.PI * 2; base.push(prj([x + 18 + 3.6 * Math.cos(a), -37.5 + 3.6 * Math.sin(a), 57])); }
  const apex = prj([x + 18, -37.5, 68]);
  const left = base.reduce((a, b) => (b[0] < a[0] ? b : a)), right = base.reduce((a, b) => (b[0] > a[0] ? b : a));
  const front = base.filter((q) => q[1] >= Math.min(left[1], right[1])).sort((a, b) => a[0] - b[0]);
  out.push({ pts: [apex, ...[left, ...front, right]].map((q) => `${q[0].toFixed(1)},${q[1].toFixed(1)}`).join(" "), fill: c });
}

function cartonOpen(out: Poly[], x: number, y: number, z: number, items: number[], dropping: G[]) {
  const w = 26, d = 20, top = z + 12, card = "var(--carton, #d9b382)";
  out.push({ pts: [[x, y, top], [x - 6, y, top + 5], [x - 6, y + d, top + 5], [x, y + d, top]].map((p) => pt(p as P3)).join(" "), fill: shade(card, 66) });
  out.push({ pts: [[x, y, top], [x + w, y, top], [x + w, y + d, top], [x, y + d, top]].map((p) => pt(p as P3)).join(" "), fill: shade(card, 52) });
  items.forEach((ci, k) => garment(out, x + 3, y + 3, z + 1 + k * 3, ci));
  dropping.forEach((g) => garment(out, g.x, g.y, g.z, g.ci));
  const D: P3 = [x, y + d, top], C: P3 = [x + w, y + d, top], F: P3 = [x + w, y + d, z], E: P3 = [x, y + d, z], B: P3 = [x + w, y, top], Gp: P3 = [x + w, y, z];
  out.push({ pts: [D, C, F, E].map(pt).join(" "), fill: shade(card, 82) });
  out.push({ pts: [B, Gp, F, C].map(pt).join(" "), fill: shade(card, 66) });
  out.push({ pts: [[x + w, y, top], [x + w, y + d, top], [x + w + 6, y + d, top + 5], [x + w + 6, y, top + 5]].map((p) => pt(p as P3)).join(" "), fill: shade(card, 66) });
}

function cartonClosed(out: Poly[], x: number, y: number, z: number, items: number[]) {
  box(out, x, y, z, 26, 20, 12, "var(--carton, #d9b382)");
  out.push({ pts: `${pt([x, y + 10, z + 12])} ${pt([x + 26, y + 10, z + 12])}`, fill: "none", stroke: "#a8814f", strokeWidth: 2 });
  items.forEach((ci, k) => {
    const tx = x + 3 + k * 6, f = y + 20;
    out.push({ pts: [[tx, f, z + 3], [tx + 4, f, z + 3], [tx + 4, f, z + 7], [tx, f, z + 7]].map((p) => pt(p as P3)).join(" "), fill: CLOTH[ci % CLOTH.length] });
  });
}

export function draw(w: World): Poly[] {
  const out: Poly[] = [];
  out.push({ pts: [[-30, -62, 0], [500, -62, 0], [500, 44, 0], [-30, 44, 0]].map((p) => pt(p as P3)).join(" "), fill: "var(--bg)", dim: true });
  for (const m of w.machines) machine(out, m, w.t);
  box(out, 0, -8, 0, 252, 28, 28);
  box(out, 0, -8, 28, 252, 28, 2, "#3a3d42");
  for (let k = 0; k < 18; k++) {
    const sx = (k * 14 + w.phase) % 252;
    out.push({ pts: `${pt([sx, -8, 30])} ${pt([sx, 20, 30])}`, fill: "none", stroke: "#6e7176", strokeWidth: 0.6 });
  }
  w.garments.filter((g) => g.state !== "drop").sort((a, b) => a.x + a.y - (b.x + b.y)).forEach((g) => garment(out, g.x, g.y, g.z, g.ci));
  box(out, 254, -6, 0, 40, 26, 14);
  const p = w.pack;
  const py = p.state === "arrive" ? PACK[1] + 40 * (1 - ease(clamp01(p.t / 0.5))) : PACK[1];
  if (p.state === "closing" || p.state === "waiting") cartonClosed(out, PACK[0], py, PACK[2], p.items);
  else cartonOpen(out, PACK[0], py, PACK[2], p.items, w.garments.filter((g) => g.state === "drop"));
  box(out, 296, -6, 0, 68, 26, 14);
  for (let x = 300; x < 364; x += 6) out.push({ pts: `${pt([x, -6, 14])} ${pt([x, 20, 14])}`, fill: "none", dim: true });
  [...w.roller].reverse().forEach((c) => cartonClosed(out, c.x, PACK[1], PACK[2], c.items));
  const dx = w.truck.dx, truck = "var(--brand)";
  box(out, 370 + dx, -10, 3, 86, 34, 5, "#26292e");
  box(out, 366 + dx, -16, 8, 90, 46, 6, truck);
  for (const wx of [384, 432]) disc(out, "y", 30.5, wx + dx, 7, 7, "#1d1f23");
  [...w.truck.load].sort((a, b) => a.cell[0] + a.cell[1] - (b.cell[0] + b.cell[1]) || a.cell[2] - b.cell[2])
    .forEach((L) => cartonClosed(out, L.cell[0] + dx, L.cell[1], L.cell[2], L.items));
  if (w.move) {
    const e = ease(clamp01(w.move.t)), c = w.move.cell;
    cartonClosed(out, lerp(SLOTS[0], c[0], e), lerp(PACK[1], c[1], e), lerp(PACK[2], c[2], e) + Math.sin(Math.PI * e) * 16, w.move.items);
  }
  box(out, 458 + dx, -16, 6, 28, 46, 38, truck);
  out.push({ pts: [[486 + dx, -11, 30], [486 + dx, 25, 30], [486 + dx, 25, 40], [486 + dx, -11, 40]].map((q) => pt(q as P3)).join(" "), fill: "color-mix(in srgb, var(--brand) 25%, #fff)" });
  disc(out, "y", 30.5, 472 + dx, 7, 7, "#1d1f23");
  return out;
}

export function viewBox(): string {
  const c = ([[-30, -62, 0], [500, -62, 0], [500, 44, 0], [-30, 44, 0], [18, -50, 70], [458, -16, 46]] as P3[]).map(prj);
  const xs = c.map((q) => q[0]), ys = c.map((q) => q[1]), pad = 10;
  const x0 = Math.min(...xs) - pad, y0 = Math.min(...ys) - pad;
  return `${x0.toFixed(0)} ${y0.toFixed(0)} ${(Math.max(...xs) - x0 + pad).toFixed(0)} ${(Math.max(...ys) - y0 + pad).toFixed(0)}`;
}
